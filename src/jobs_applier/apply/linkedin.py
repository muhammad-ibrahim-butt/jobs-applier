"""LinkedIn Easy Apply automation adapter."""

from __future__ import annotations

import re

import structlog
from playwright.sync_api import BrowserContext, Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from jobs_applier.apply.form_filler import FormFiller, human_delay
from jobs_applier.config.profile import ApplicantProfile
from jobs_applier.config.settings import Settings
from jobs_applier.models.job import (
    ApplicationResult,
    ApplicationStatus,
    ApplyTarget,
    JobListing,
    detect_ats_from_url,
)
from jobs_applier.profile.qa_cache import QuestionCache

logger = structlog.get_logger(__name__)

MAX_MODAL_STEPS = 15

# Shared patterns — kept as strings so unit tests can assert without Playwright.
EASY_APPLY_ROLE_PATTERN = re.compile(r"easy\s*apply", re.I)
SUBMIT_ROLE_PATTERN = re.compile(r"submit\s+application", re.I)
NEXT_ROLE_PATTERN = re.compile(r"^(next|continue|review)(\s|$)", re.I)
SUCCESS_TEXT_PATTERN = re.compile(
    r"(application\s+sent|application\s+submitted|your\s+application\s+was\s+sent|"
    r"you\s+applied|application\s+was\s+submitted)",
    re.I,
)


def find_easy_apply_button(page: Page) -> Locator | None:
    """Locate the Easy Apply CTA with several LinkedIn DOM variants."""
    candidates: list[Locator] = [
        page.get_by_role("button", name=EASY_APPLY_ROLE_PATTERN),
        page.locator("button.jobs-apply-button").filter(has_text=EASY_APPLY_ROLE_PATTERN),
        page.locator("button.jobs-s-apply__application-button").filter(
            has_text=EASY_APPLY_ROLE_PATTERN
        ),
        page.locator("button[aria-label*='Easy Apply' i]"),
        page.locator("button.jobs-apply-button--top-card").filter(has_text=EASY_APPLY_ROLE_PATTERN),
    ]
    for loc in candidates:
        btn = loc.first
        try:
            if btn.is_visible(timeout=2500):
                btn.scroll_into_view_if_needed()
                return btn
        except Exception:
            continue
    return None


def page_shows_already_applied(page: Page) -> bool:
    markers = (
        page.get_by_role("button", name=re.compile(r"^applied$", re.I)).first,
        page.locator("button.jobs-apply-button")
        .filter(has_text=re.compile(r"^applied$", re.I))
        .first,
        page.locator("[aria-label*='Applied' i]").first,
    )
    for btn in markers:
        try:
            if btn.is_visible(timeout=800):
                return True
        except Exception:
            continue
    return False


class LinkedInEasyApplyAdapter:
    """Apply to LinkedIn Easy Apply jobs; hand off to ATS adapters when possible."""

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
        page: Page | None = context.new_page()
        try:
            url = job.job_url or job.apply_url
            if not url:
                return self._result(job, ApplicationStatus.FAILED, "No job URL")

            assert page is not None
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            human_delay(1000, 2000)
            self._wait_for_job_detail(page)

            if page_shows_already_applied(page):
                return self._result(job, ApplicationStatus.SKIPPED, "Already applied on LinkedIn")

            easy_apply_btn = find_easy_apply_button(page)
            if easy_apply_btn is not None:
                return self._complete_easy_apply(
                    page, job, profile, qa_cache, settings, dry_run, easy_apply_btn
                )

            # No Easy Apply — follow company / external apply if it is a known ATS.
            external = self._resolve_external_apply_url(page)
            if external:
                ats = detect_ats_from_url(external)
                if ats is not None:
                    redirected = job.model_copy(
                        update={
                            "apply_url": external,
                            "job_url": external,
                            "is_easy_apply": False,
                        }
                    )
                    logger.info(
                        "linkedin_redirect_ats",
                        job=job.title,
                        ats=ats.value,
                        url=external,
                    )
                    page.close()
                    page = None
                    from jobs_applier.apply.router import ApplyRouter

                    adapter = ApplyRouter().get_adapter(redirected)
                    if adapter is None:
                        return self._result(
                            job,
                            ApplicationStatus.SKIPPED,
                            "Easy Apply not available; no supported ATS redirect",
                        )
                    return adapter.apply(
                        redirected, context, profile, qa_cache, settings, dry_run=dry_run
                    )

            return self._result(
                job,
                ApplicationStatus.SKIPPED,
                "Easy Apply not available; no supported ATS redirect",
            )

        except PlaywrightTimeout as exc:
            logger.error("linkedin_timeout", job=job.title, error=str(exc))
            return self._result(job, ApplicationStatus.FAILED, f"Timeout: {exc}")
        except Exception as exc:
            logger.error("linkedin_apply_error", job=job.title, error=str(exc))
            return self._result(job, ApplicationStatus.FAILED, str(exc))
        finally:
            if page is not None:
                page.close()

    def _wait_for_job_detail(self, page: Page) -> None:
        for sel in (
            "div.jobs-details",
            "div.job-view-layout",
            "div.jobs-unified-top-card",
            "main",
        ):
            try:
                page.wait_for_selector(sel, timeout=8000)
                return
            except PlaywrightTimeout:
                continue

    def _complete_easy_apply(
        self,
        page: Page,
        job: JobListing,
        profile: ApplicantProfile,
        qa_cache: QuestionCache,
        settings: Settings,
        dry_run: bool,
        easy_apply_btn: Locator,
    ) -> ApplicationResult:
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

            submit_btn = self._find_submit_button(page)
            if submit_btn is not None:
                submit_btn.click()
                human_delay(1500, 2500)
                if self._is_submitted(page):
                    return self._result(job, ApplicationStatus.APPLIED, "Submitted via Easy Apply")
                return self._result(
                    job, ApplicationStatus.FAILED, "Submit clicked but not confirmed"
                )

            next_btn = self._find_next_button(page)
            if next_btn is not None:
                next_btn.click()
                human_delay(800, 1500)
                continue

            break

        return self._result(job, ApplicationStatus.FAILED, "Could not complete application modal")

    def _find_submit_button(self, page: Page) -> Locator | None:
        candidates = (
            page.get_by_role("button", name=SUBMIT_ROLE_PATTERN),
            page.locator("button[aria-label*='Submit application' i]"),
            page.locator("button:has-text('Submit application')"),
        )
        for loc in candidates:
            btn = loc.first
            try:
                if btn.is_visible(timeout=1500):
                    return btn
            except Exception:
                continue
        return None

    def _find_next_button(self, page: Page) -> Locator | None:
        candidates = (
            page.get_by_role("button", name=re.compile(r"continue to next step", re.I)),
            page.get_by_role("button", name=re.compile(r"review your application", re.I)),
            page.get_by_role("button", name=NEXT_ROLE_PATTERN),
            page.locator("button[aria-label*='Continue' i], button[aria-label*='Review' i]"),
            page.locator("button:has-text('Next'), button:has-text('Review')"),
        )
        for loc in candidates:
            btn = loc.first
            try:
                if btn.is_visible(timeout=1500):
                    # Avoid clicking "Next" that is disabled.
                    if btn.is_disabled():
                        continue
                    return btn
            except Exception:
                continue
        return None

    def _resolve_external_apply_url(self, page: Page) -> str | None:
        """Find an off-LinkedIn apply URL on the job page (ATS handoff)."""
        selectors = (
            "a[href*='greenhouse.io']",
            "a[href*='lever.co']",
            "a[href*='ashbyhq.com']",
            "a.jobs-apply-button[href]",
            "a[data-control-name='jobdetails_topcard_inapply']",
            "a:has-text('Apply on company website')",
            "a:has-text('Apply')",
        )
        for sel in selectors:
            loc = page.locator(sel).first
            try:
                if not loc.is_visible(timeout=800):
                    continue
                href = (loc.get_attribute("href") or "").strip()
                if not href or href.startswith("#"):
                    continue
                if href.startswith("/"):
                    href = f"https://www.linkedin.com{href}"
                if "linkedin.com" in href.lower() and detect_ats_from_url(href) is None:
                    # May be a LinkedIn redirector — click and read final URL.
                    with page.context.expect_page(timeout=8000) as pop:
                        loc.click()
                    new_page = pop.value
                    human_delay(1000, 2000)
                    final = new_page.url
                    new_page.close()
                    if detect_ats_from_url(final) is not None:
                        return final
                    continue
                if detect_ats_from_url(href) is not None:
                    return href
                if "linkedin.com" not in href.lower():
                    return href
            except Exception:
                continue
        return None

    def _is_submitted(self, page: Page) -> bool:
        try:
            text = page.locator("body").inner_text(timeout=3000)
        except Exception:
            text = ""
        if SUCCESS_TEXT_PATTERN.search(text or ""):
            return True
        success = page.locator(
            "text=Application submitted, text=Your application was sent, text=Application sent"
        ).first
        try:
            return success.is_visible(timeout=3000)
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
            job_title=job.title,
            job_company=job.company,
        )
