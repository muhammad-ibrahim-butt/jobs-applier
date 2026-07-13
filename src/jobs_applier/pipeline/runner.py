"""Pipeline orchestrator: scrape → filter → apply → notify."""

from __future__ import annotations

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
from jobs_applier.scrapers.apify_client import ApifyJobScraper
from jobs_applier.storage.db import init_db
from jobs_applier.storage.repositories import JobRepository

logger = structlog.get_logger(__name__)


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

    def scrape_only(self) -> PipelineStats:
        stats = PipelineStats()
        jobs = self._scrape()
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

        jobs = self._scrape()
        stats.scraped = len(jobs)

        passed, rejected = FilterEngine(self._app_config, self._profile).filter_jobs(jobs)
        stats.filtered = len(passed)
        logger.info("filter_complete", passed=len(passed), rejected=len(rejected))

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
            manual_jobs: list[JobListing] = []
            for job in eligible:
                target = self._router.get_target(job)
                if target == ApplyTarget.UNSUPPORTED:
                    manual_jobs.append(job)
                else:
                    auto_jobs.append(job)

            if manual_jobs:
                emailed_ok = self._notifier.send_manual_apply_digest(manual_jobs)
                for job in manual_jobs:
                    result = ApplicationResult(
                        job_fingerprint=job.fingerprint,
                        status=(
                            ApplicationStatus.EMAILED if emailed_ok else ApplicationStatus.FAILED
                        ),
                        apply_target=ApplyTarget.UNSUPPORTED,
                        message=(
                            "Emailed for manual apply"
                            if emailed_ok
                            else "Failed to email manual-apply job"
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
                self._notifier.send_run_summary(stats)
                self._save_run(repo, started, stats)
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
                        result = ApplicationResult(
                            job_fingerprint=job.fingerprint,
                            status=ApplicationStatus.FAILED,
                            apply_target=target,
                            message=str(exc),
                        )

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
                emailed_ok = self._notifier.send_manual_apply_digest(fallback_manual)
                for job in fallback_manual:
                    result = ApplicationResult(
                        job_fingerprint=job.fingerprint,
                        status=(
                            ApplicationStatus.EMAILED if emailed_ok else ApplicationStatus.SKIPPED
                        ),
                        apply_target=self._router.get_target(job),
                        message=(
                            "Auto-apply skipped; emailed for manual apply"
                            if emailed_ok
                            else "Auto-apply skipped"
                        ),
                    )
                    if emailed_ok:
                        stats.emailed += 1
                        stats.manual_jobs.append(job)
                    else:
                        stats.skipped += 1
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
                "skipped": stats.skipped + stats.emailed,
                "failed": stats.failed,
            }
        )
        repo.commit()

    def _scrape(self) -> list[JobListing]:
        scraper = ApifyJobScraper(self._settings, self._app_config)
        return scraper.scrape()

    def _persist_jobs(self, jobs: list[JobListing]) -> None:
        session = self._session_factory()
        try:
            repo = JobRepository(session)
            for job in jobs:
                repo.save_job(job)
            repo.commit()
        finally:
            session.close()
