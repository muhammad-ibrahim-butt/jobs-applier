"""Job filtering engine."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from jobs_applier.config.profile import AppConfig, ApplicantProfile
from jobs_applier.filters.relevance import RelevanceScorer
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
        self._scorer = RelevanceScorer(profile, self._filters.preferred_keywords)

    def score(self, job: JobListing) -> int:
        return self._scorer.score(job)

    def _matches_keywords(self, text: str, keywords: list[str]) -> bool:
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def _title_has_keyword(self, title: str, keyword: str) -> bool:
        """Word-boundary match so 'staff' does not match 'Stafford'."""
        pattern = r"(?<!\w)" + re.escape(keyword.lower()) + r"(?!\w)"
        return re.search(pattern, title.lower()) is not None

    def _looks_remote(self, job: JobListing) -> bool:
        if job.is_remote:
            return True
        blob = f"{job.location} {job.title} {job.description[:500]}".lower()
        if "remote" in blob or "work from home" in blob or "wfh" in blob:
            return True
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
            if self._title_has_keyword(job.title, kw):
                return False, f"excluded title keyword: {kw}"

        for kw in self._filters.exclude_description_keywords:
            if kw.lower() in description:
                return False, f"excluded description keyword: {kw}"

        if self._filters.remote_only and not self._looks_remote(job):
            return False, "not remote"

        if self._filters.require_posted_date and job.posted_at is None:
            return False, "missing posted date"

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

        relevance = self._scorer.score(job)
        if relevance < self._filters.min_relevance_score:
            return False, f"low relevance ({relevance} < {self._filters.min_relevance_score})"

        return True, "passed"

    def filter_jobs(
        self, jobs: list[JobListing]
    ) -> tuple[list[JobListing], list[tuple[JobListing, str]]]:
        """Filter jobs, returning (passed, rejected_with_reasons)."""
        scored: list[tuple[int, JobListing]] = []
        rejected: list[tuple[JobListing, str]] = []
        for job in jobs:
            ok, reason = self.passes(job)
            if ok:
                scored.append((self._scorer.score(job), job))
            else:
                rejected.append((job, reason))
        # Highest relevance first so digests / caps take the best matches.
        scored.sort(key=lambda item: item[0], reverse=True)
        passed = [job for _, job in scored]
        return passed, rejected

    def select_for_email(self, jobs: list[JobListing]) -> list[JobListing]:
        """Keep only the top N jobs for the manual-apply digest."""
        limit = self._filters.max_email_jobs
        ranked = sorted(jobs, key=self._scorer.score, reverse=True)
        return ranked[:limit]
