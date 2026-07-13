"""Job filtering engine."""

from __future__ import annotations

from datetime import datetime, timedelta

from jobs_applier.config.profile import AppConfig, ApplicantProfile
from jobs_applier.models.job import JobListing

_ONSITE_MARKERS = (
    "on-site",
    "onsite",
    "in-office",
    "in office",
    "hybrid",
)


class FilterEngine:
    """Apply configurable filters to job listings."""

    def __init__(self, app_config: AppConfig, profile: ApplicantProfile) -> None:
        self._filters = app_config.filters
        self._search = app_config.search
        self._profile = profile

    def _matches_keywords(self, text: str, keywords: list[str]) -> bool:
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def _looks_remote(self, job: JobListing) -> bool:
        if job.is_remote:
            return True
        blob = f"{job.location} {job.title} {job.description[:500]}".lower()
        if "remote" in blob or "work from home" in blob or "wfh" in blob:
            return True
        # Worldwide remote searches often return empty location — treat as remote
        # unless clearly onsite/hybrid.
        if not job.location.strip():
            return True
        return not any(marker in blob for marker in _ONSITE_MARKERS)

    def passes(self, job: JobListing) -> tuple[bool, str]:
        """Return (passes, reason) for a job listing."""
        title = job.title.lower()
        description = job.description.lower()
        company = job.company.lower()

        for blocked in self._profile.blocklist.companies:
            if blocked.lower() in company:
                return False, f"blocked company: {blocked}"
        for kw in self._profile.blocklist.keywords:
            if kw.lower() in title or kw.lower() in description:
                return False, f"blocked keyword: {kw}"

        for kw in self._filters.exclude_companies:
            if kw.lower() in company:
                return False, f"excluded company: {kw}"

        if self._filters.include_title_keywords and not self._matches_keywords(
            job.title, self._filters.include_title_keywords
        ):
            return False, "title missing required keywords"

        for kw in self._filters.exclude_title_keywords:
            if kw.lower() in title:
                return False, f"excluded title keyword: {kw}"

        for kw in self._filters.exclude_description_keywords:
            if kw.lower() in description:
                return False, f"excluded description keyword: {kw}"

        if self._filters.remote_only and not self._looks_remote(job):
            return False, "not remote"

        # Note: non-Easy-Apply jobs are NOT rejected here — pipeline emails them.

        if job.posted_at and self._filters.max_days_old:
            cutoff = datetime.utcnow() - timedelta(days=self._filters.max_days_old)
            if job.posted_at.replace(tzinfo=None) < cutoff:
                return False, "too old"

        if (
            self._filters.min_salary
            and job.salary_max
            and job.salary_max < self._filters.min_salary
        ):
            return False, "salary below minimum"

        return True, "passed"

    def filter_jobs(
        self, jobs: list[JobListing]
    ) -> tuple[list[JobListing], list[tuple[JobListing, str]]]:
        """Filter jobs, returning (passed, rejected_with_reasons)."""
        passed: list[JobListing] = []
        rejected: list[tuple[JobListing, str]] = []
        for job in jobs:
            ok, reason = self.passes(job)
            if ok:
                passed.append(job)
            else:
                rejected.append((job, reason))
        return passed, rejected
