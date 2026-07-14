"""Pipeline orchestrator: scrape → filter → apply → notify."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

import structlog

from jobs_applier.apply.browser import BrowserSession
from jobs_applier.apply.router import ApplyRouter
from jobs_applier.config.profile import AppConfig, ApplicantProfile, load_app_config, load_profile
from jobs_applier.config.settings import Settings, get_settings
from jobs_applier.filters.engine import FilterEngine
from jobs_applier.models.job import (
    ApplicationResult,
    ApplicationStatus,
    ApplyTarget,
    JobListing,
    PipelineStats,
)
from jobs_applier.notifications.email import EmailNotifier
from jobs_applier.profile.qa_cache import QuestionCache
from jobs_applier.scrapers.apify_client import ApifyUsageLimitError
from jobs_applier.scrapers.multi import MultiSourceScraper
from jobs_applier.storage.db import init_db
from jobs_applier.storage.repositories import JobRepository

logger = structlog.get_logger(__name__)


def _result(
    job: JobListing,
    status: ApplicationStatus,
    apply_target: ApplyTarget,
    message: str,
) -> ApplicationResult:
    return ApplicationResult(
        job_fingerprint=job.fingerprint,
        status=status,
        apply_target=apply_target,
        message=message,
        job_title=job.title,
        job_company=job.company,
    )


class PipelineRunner:
    """Run the full job pipeline."""

    def __init__(
        self,
        settings: Settings | None = None,
        app_config: AppConfig | None = None,
        profile: ApplicantProfile | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._settings.ensure_directories()

        if app_config is None:
            app_config = load_app_config(self._settings.config_path)
        if profile is None:
            profile = load_profile(self._settings.profile_path)

        self._app_config = app_config
        self._profile = profile
        self._session_factory = init_db(self._settings.database_path)
        self._router = ApplyRouter()
        self._notifier = EmailNotifier(self._settings)
        self._last_scrape_notes = ""

    def scrape_only(self) -> PipelineStats:
        stats = PipelineStats()
        jobs = self._scrape_safe()
        stats.scraped = len(jobs)
        passed, _ = FilterEngine(self._app_config, self._profile).filter_jobs(jobs)
        stats.filtered = len(passed)
        stats.new_jobs = passed
        self._persist_jobs(passed)
        return stats

    def run(self, dry_run: bool | None = None) -> PipelineStats:
        dry_run = self._settings.dry_run if dry_run is None else dry_run
        stats = PipelineStats()
        started = datetime.utcnow()
        engine = FilterEngine(self._app_config, self._profile)

        jobs = self._scrape_safe()
        stats.scraped = len(jobs)
        stats.scrape_notes = self._last_scrape_notes

        if not jobs:
            backlog = self._load_backlog_jobs()
            if backlog:
                logger.info("using_backlog_jobs", count=len(backlog))
                jobs = backlog
                stats.scraped = len(backlog)
                if stats.scrape_notes:
                    stats.scrape_notes += " | backlog"
                else:
                    stats.scrape_notes = "backlog"

        passed, rejected = engine.filter_jobs(jobs)
        stats.filtered = len(passed)
        reason_counts = dict(Counter(reason for _, reason in rejected).most_common(8))
        logger.info(
            "filter_complete",
            passed=len(passed),
            rejected=len(rejected),
            reject_reasons=reason_counts,
        )

        session = self._session_factory()
        try:
            repo = JobRepository(session)

            eligible: list[JobListing] = []
            for job in passed:
                if repo.has_applied(job.fingerprint):
                    continue
                repo.save_job(job)
                eligible.append(job)

            stats.new_jobs = eligible
            repo.commit()

            if not eligible:
                logger.info("no_new_jobs_to_apply")
                self._notifier.send_run_summary(stats)
                return stats

            auto_jobs: list[JobListing] = []
            manual_all: list[JobListing] = []
            for job in eligible:
                if self._router.get_target(job) == ApplyTarget.UNSUPPORTED:
                    manual_all.append(job)
                else:
                    auto_jobs.append(job)

            manual_jobs = engine.select_for_email(manual_all)
            skipped_manual = [j for j in manual_all if j not in manual_jobs]
            logger.info(
                "manual_digest_selected",
                selected=len(manual_jobs),
                skipped_lower_relevance=len(skipped_manual),
                cap=self._app_config.filters.max_email_jobs,
            )

            for job in skipped_manual:
                result = _result(
                    job,
                    ApplicationStatus.SKIPPED,
                    ApplyTarget.UNSUPPORTED,
                    "Below email relevance / digest cap",
                )
                stats.skipped += 1
                stats.results.append(result)
                repo.save_application(result)
            if skipped_manual:
                repo.commit()

            if manual_jobs:
                emailed_ok = self._notifier.send_manual_apply_digest(manual_jobs)
                for job in manual_jobs:
                    result = _result(
                        job,
                        ApplicationStatus.EMAILED if emailed_ok else ApplicationStatus.FAILED,
                        ApplyTarget.UNSUPPORTED,
                        (
                            "Queued for manual apply in summary email"
                            if emailed_ok
                            else "Failed to queue manual-apply job (email disabled?)"
                        ),
                    )
                    if emailed_ok:
                        stats.emailed += 1
                    else:
                        stats.failed += 1
                    stats.manual_jobs.append(job)
                    stats.results.append(result)
                    repo.save_application(result)
                repo.commit()

            applies_today = repo.count_applications_today()
            remaining_cap = max(0, self._settings.daily_apply_cap - applies_today)
            if remaining_cap == 0 and auto_jobs:
                stats.cap_reached = True
                logger.info("daily_cap_reached", cap=self._settings.daily_apply_cap)
                self._notifier.send_run_summary(stats)
                return stats

            if not auto_jobs:
                self._save_run(repo, started, stats)
                self._notifier.send_run_summary(stats)
                return stats

            qa_cache = QuestionCache(self._settings.questions_cache_path, self._profile)
            fallback_manual: list[JobListing] = []

            with BrowserSession(self._settings.browser_user_data_dir) as context:
                for job in auto_jobs[:remaining_cap]:
                    target = self._router.get_target(job)
                    adapter = self._router.get_adapter(job)
                    logger.info("applying", job=job.title, company=job.company, target=target.value)
                    try:
                        assert adapter is not None
                        result = adapter.apply(
                            job, context, self._profile, qa_cache, self._settings, dry_run
                        )
                    except Exception as exc:
                        logger.error("apply_exception", job=job.title, error=str(exc))
                        result = _result(job, ApplicationStatus.FAILED, target, str(exc))

                    if result.status == ApplicationStatus.APPLIED:
                        stats.applied += 1
                    elif result.status == ApplicationStatus.DRY_RUN:
                        stats.dry_run += 1
                    elif result.status == ApplicationStatus.SKIPPED:
                        fallback_manual.append(job)
                        continue
                    else:
                        stats.failed += 1

                    stats.results.append(result)
                    repo.save_application(result)
                    repo.commit()

            if fallback_manual:
                to_email = engine.select_for_email(fallback_manual)
                emailed_ok = (
                    self._notifier.send_manual_apply_digest(to_email) if to_email else False
                )
                for job in fallback_manual:
                    if job in to_email and emailed_ok:
                        status = ApplicationStatus.EMAILED
                        message = "Auto-apply skipped; included in summary email"
                        stats.emailed += 1
                        stats.manual_jobs.append(job)
                    else:
                        status = ApplicationStatus.SKIPPED
                        message = "Auto-apply skipped"
                        stats.skipped += 1
                    result = _result(job, status, self._router.get_target(job), message)
                    stats.results.append(result)
                    repo.save_application(result)
                repo.commit()

            self._save_run(repo, started, stats)
            self._notifier.send_run_summary(stats)
            logger.info(
                "pipeline_complete",
                scraped=stats.scraped,
                applied=stats.applied,
                emailed=stats.emailed,
                failed=stats.failed,
                skipped=stats.skipped,
            )
            return stats
        finally:
            session.close()

    def _save_run(self, repo: JobRepository, started: datetime, stats: PipelineStats) -> None:
        repo.save_run(
            {
                "started_at": started,
                "finished_at": datetime.utcnow(),
                "scraped": stats.scraped,
                "filtered": stats.filtered,
                "applied": stats.applied,
                "skipped": stats.skipped,
                "failed": stats.failed,
                "emailed": stats.emailed,
                "notes": stats.scrape_notes[:1000],
            }
        )
        repo.commit()

    def _scrape_safe(self) -> list[JobListing]:
        """Scrape via multi-source stack; never abort the pipeline on scrape errors."""
        scraper = MultiSourceScraper(self._settings, self._app_config)
        try:
            jobs = scraper.scrape()
            notes = self._scrape_notes(scraper)
            self._last_scrape_notes = notes
            return jobs
        except ApifyUsageLimitError as exc:
            logger.error("scrape_aborted_apify_quota", error=str(exc))
            self._last_scrape_notes = f"apify_quota: {exc}"
            return []
        except Exception as exc:
            logger.error("scrape_aborted", error=str(exc))
            self._last_scrape_notes = f"scrape_error: {exc}"
            return []

    @staticmethod
    def _scrape_notes(scraper: MultiSourceScraper) -> str:
        parts: list[str] = []
        if scraper.last_sources_hit:
            parts.append("hit=" + ",".join(scraper.last_sources_hit))
        elif scraper.last_sources_tried:
            parts.append("tried=" + ",".join(scraper.last_sources_tried) + " (empty)")
        if scraper.last_errors:
            parts.append("errors=" + "; ".join(scraper.last_errors[:3]))
        return " | ".join(parts)

    def _load_backlog_jobs(self) -> list[JobListing]:
        session = self._session_factory()
        try:
            return JobRepository(session).unapplied_jobs(limit=40)
        finally:
            session.close()

    def _persist_jobs(self, jobs: list[JobListing]) -> None:
        session = self._session_factory()
        try:
            repo = JobRepository(session)
            for job in jobs:
                repo.save_job(job)
            repo.commit()
        finally:
            session.close()
