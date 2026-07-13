"""Ashby ATS apply adapter."""

from __future__ import annotations

import structlog
from playwright.sync_api import BrowserContext
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from jobs_applier.apply.form_filler import FormFiller, human_delay
from jobs_applier.config.profile import ApplicantProfile
from jobs_applier.config.settings import Settings
from jobs_applier.models.job import ApplicationResult, ApplicationStatus, ApplyTarget, JobListing
from jobs_applier.profile.qa_cache import QuestionCache

logger = structlog.get_logger(__name__)


class AshbyAdapter:
    """Apply to Ashby-hosted job applications (jobs.ashbyhq.com)."""

    def can_apply(self, job: JobListing) -> bool:
        return job.apply_target() == ApplyTarget.ASHBY

    def apply(
        self,
        job: JobListing,
        context: BrowserContext,
        profile: ApplicantProfile,
        qa_cache: QuestionCache,
        settings: Settings,
        dry_run: bool = False,
    ) -> ApplicationResult:
        page = context.new_page()
        try:
            url = job.apply_url or job.job_url
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            human_delay(1000, 2000)

            apply_btn = page.locator(
                "a:has-text('Apply for this Job'), button:has-text('Apply for this Job'), "
                "a:has-text('Apply'), button:has-text('Apply')"
            ).first
            if apply_btn.is_visible(timeout=4000):
                apply_btn.click()
                human_delay(1000, 2000)

            filler = FormFiller(page, qa_cache, settings.resume_path)
            unanswered = filler.fill_all()

            if unanswered:
                return ApplicationResult(
                    job_fingerprint=job.fingerprint,
                    status=ApplicationStatus.FAILED,
                    apply_target=ApplyTarget.ASHBY,
                    message=f"Unanswered fields: {', '.join(unanswered)}",
                    job_title=job.title,
                    job_company=job.company,
                )

            if dry_run:
                return ApplicationResult(
                    job_fingerprint=job.fingerprint,
                    status=ApplicationStatus.DRY_RUN,
                    apply_target=ApplyTarget.ASHBY,
                    message="Dry run — form filled",
                    job_title=job.title,
                    job_company=job.company,
                )

            submit = page.locator(
                "button[type='submit']:has-text('Submit'), "
                "button:has-text('Submit Application'), "
                "button:has-text('Submit application')"
            ).first
            if submit.is_visible(timeout=3000):
                submit.click()
                human_delay(2000, 3000)
                return ApplicationResult(
                    job_fingerprint=job.fingerprint,
                    status=ApplicationStatus.APPLIED,
                    apply_target=ApplyTarget.ASHBY,
                    message="Submitted via Ashby",
                    job_title=job.title,
                    job_company=job.company,
                )

            return ApplicationResult(
                job_fingerprint=job.fingerprint,
                status=ApplicationStatus.FAILED,
                apply_target=ApplyTarget.ASHBY,
                message="Submit button not found",
                job_title=job.title,
                job_company=job.company,
            )

        except PlaywrightTimeout as exc:
            return ApplicationResult(
                job_fingerprint=job.fingerprint,
                status=ApplicationStatus.FAILED,
                apply_target=ApplyTarget.ASHBY,
                message=f"Timeout: {exc}",
                job_title=job.title,
                job_company=job.company,
            )
        except Exception as exc:
            logger.error("ashby_apply_error", job=job.title, error=str(exc))
            return ApplicationResult(
                job_fingerprint=job.fingerprint,
                status=ApplicationStatus.FAILED,
                apply_target=ApplyTarget.ASHBY,
                message=str(exc),
                job_title=job.title,
                job_company=job.company,
            )
        finally:
            page.close()
