"""Domain models for jobs and applications."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, computed_field


class JobPlatform(StrEnum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    UNKNOWN = "unknown"


class ApplyTarget(StrEnum):
    LINKEDIN_EASY_APPLY = "linkedin_easy_apply"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    UNSUPPORTED = "unsupported"


class ApplicationStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"
    DRY_RUN = "dry_run"
    EMAILED = "emailed"  # sent to user for manual apply


class JobListing(BaseModel):
    """Normalized job listing from any scrape source."""

    platform: JobPlatform
    external_id: str
    title: str
    company: str
    location: str = ""
    description: str = ""
    apply_url: str = ""
    job_url: str = ""
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "USD"
    is_remote: bool = False
    is_easy_apply: bool = False
    posted_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fingerprint(self) -> str:
        """Unique identifier for deduplication."""
        return f"{self.platform.value}:{self.external_id}"

    def apply_target(self) -> ApplyTarget:
        return detect_apply_target(self)


def _urls_blob(job: JobListing) -> str:
    parts = [job.apply_url or "", job.job_url or ""]
    raw = job.raw or {}
    for key in ("job_url_direct", "jobUrlDirect", "applyUrl", "link", "url"):
        value = raw.get(key)
        if value:
            parts.append(str(value))
    return " ".join(parts).lower()


def detect_apply_target(job: JobListing) -> ApplyTarget:
    """Pick the best auto-apply adapter for a listing."""
    urls = _urls_blob(job)

    # External ATS wins even when the scrape source is LinkedIn/Indeed.
    if "ashbyhq.com" in urls or "jobs.ashbyhq.com" in urls:
        return ApplyTarget.ASHBY
    if "greenhouse.io" in urls or "boards.greenhouse.io" in urls:
        return ApplyTarget.GREENHOUSE
    if "jobs.lever.co" in urls or "lever.co/jobs" in urls:
        return ApplyTarget.LEVER

    apply = (job.apply_url or "").lower()
    listing = (job.job_url or apply).lower()
    external_apply = bool(apply) and "linkedin.com" not in apply
    on_linkedin = job.platform == JobPlatform.LINKEDIN or "linkedin.com" in listing

    # LinkedIn listings without an external ATS → try Easy Apply first.
    # Missing button → adapter skips → email fallback.
    if on_linkedin and not external_apply:
        return ApplyTarget.LINKEDIN_EASY_APPLY

    return ApplyTarget.UNSUPPORTED


class ApplicationResult(BaseModel):
    """Result of an apply attempt."""

    job_fingerprint: str
    status: ApplicationStatus
    apply_target: ApplyTarget
    message: str = ""
    job_title: str = ""
    job_company: str = ""
    applied_at: datetime = Field(default_factory=datetime.utcnow)


class PipelineStats(BaseModel):
    """Summary statistics for a pipeline run."""

    scraped: int = 0
    filtered: int = 0
    applied: int = 0
    skipped: int = 0
    failed: int = 0
    dry_run: int = 0
    emailed: int = 0
    cap_reached: bool = False
    results: list[ApplicationResult] = Field(default_factory=list)
    new_jobs: list[JobListing] = Field(default_factory=list)
    manual_jobs: list[JobListing] = Field(default_factory=list)
