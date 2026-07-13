"""LinkedIn Easy Apply automation adapter."""

from __future__ import annotations

import structlog
from playwright.sync_api import BrowserContext, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from jobs_applier.apply.form_filler import FormFiller, human_delay
from jobs_applier.config.profile import ApplicantProfile
from jobs_applier.config.settings import Settings
from jobs_applier.models.job import ApplicationResult, ApplicationStatus, ApplyTarget, JobListing
from jobs_applier.profile.qa_cache import QuestionCache

logger = structlog.get_logger(__name__)

MAX_MODAL_STEPS = 15


class LinkedInEasyApplyAdapter:
    """Apply to LinkedIn Easy Apply jobs."""

    def can_apply(self, job: JobListing) -> bool:
        return job.apply_target() == ApplyTarget.LINKEDIN_EASY_APPLY

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
            url = job.job_url or job.apply_url
            if not url:
                return self._result(job, ApplicationStatus.FAILED, "No job URL")

            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            human_delay(1000, 2000)

            easy_apply_btn = page.locator(
                "button.jobs-apply-button, button:has-text('Easy Apply'), "
                "button[aria-label*='Easy Apply']"
            ).first

            if not easy_apply_btn.is_visible(timeout=5000):
                return self._result(job, ApplicationStatus.SKIPPED, "Easy Apply button not found")

            easy_apply_btn.click()
            human_delay(800, 1500)

            filler = FormFiller(page, qa_cache, settings.resume_path)
            previous_content = ""
            stall_count = 0

            for _step in range(MAX_MODAL_STEPS):
                modal = page.locator(
                    "div.jobs-easy-apply-modal, div[role='dialog'], div.artdeco-modal"
                ).first

                if not modal.is_visible(timeout=3000):
                    break

                current_content = modal.inner_text()
                if current_content == previous_content:
                    stall_count += 1
                    if stall_count >= 2:
                        return self._result(
                            job,
                            ApplicationStatus.FAILED,
                            "Form stalled — unknown required field",
                        )
                else:
                    stall_count = 0
                previous_content = current_content

                unanswered = filler.fill_all()
                if unanswered:
                    logger.warning("unanswered_questions", job=job.title, questions=unanswered)

                if dry_run:
                    self._close_modal(page)
                    return self._result(job, ApplicationStatus.DRY_RUN, "Dry run — form filled")

                submit_btn = page.locator(
                    "button[aria-label='Submit application'], button:has-text('Submit application')"
                ).first
                if submit_btn.is_visible(timeout=2000):
                    submit_btn.click()
                    human_delay(1500, 2500)
                    if self._is_submitted(page):
                        return self._result(
                            job, ApplicationStatus.APPLIED, "Submitted via Easy Apply"
                        )
                    return self._result(
                        job, ApplicationStatus.FAILED, "Submit clicked but not confirmed"
                    )

                next_btn = page.locator(
                    "button[aria-label='Continue to next step'], "
                    "button[aria-label='Review your application'], "
                    "button:has-text('Next'), button:has-text('Review')"
                ).first
                if next_btn.is_visible(timeout=2000):
                    next_btn.click()
                    human_delay(800, 1500)
                    continue

                break

            return self._result(
                job, ApplicationStatus.FAILED, "Could not complete application modal"
            )

        except PlaywrightTimeout as exc:
            logger.error("linkedin_timeout", job=job.title, error=str(exc))
            return self._result(job, ApplicationStatus.FAILED, f"Timeout: {exc}")
        except Exception as exc:
            logger.error("linkedin_apply_error", job=job.title, error=str(exc))
            return self._result(job, ApplicationStatus.FAILED, str(exc))
        finally:
            page.close()

    def _is_submitted(self, page: Page) -> bool:
        success = page.locator("text=Application submitted, text=Your application was sent").first
        try:
            return success.is_visible(timeout=5000)
        except Exception:
            return False

    def _close_modal(self, page: Page) -> None:
        dismiss = page.locator("button[aria-label='Dismiss'], button.artdeco-modal__dismiss").first
        try:
            if dismiss.is_visible(timeout=2000):
                dismiss.click()
                human_delay()
        except Exception:
            pass

    def _result(
        self, job: JobListing, status: ApplicationStatus, message: str
    ) -> ApplicationResult:
        return ApplicationResult(
            job_fingerprint=job.fingerprint,
            status=status,
            apply_target=ApplyTarget.LINKEDIN_EASY_APPLY,
            message=message,
        )
