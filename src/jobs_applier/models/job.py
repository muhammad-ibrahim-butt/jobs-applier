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
    UNSUPPORTED = "unsupported"


class ApplicationStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"
    DRY_RUN = "dry_run"


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
        url = (self.apply_url or self.job_url).lower()
        if self.platform == JobPlatform.LINKEDIN and self.is_easy_apply:
            return ApplyTarget.LINKEDIN_EASY_APPLY
        if "greenhouse.io" in url or "boards.greenhouse.io" in url:
            return ApplyTarget.GREENHOUSE
        if "jobs.lever.co" in url or "lever.co" in url:
            return ApplyTarget.LEVER
        return ApplyTarget.UNSUPPORTED


class ApplicationResult(BaseModel):
    """Result of an apply attempt."""

    job_fingerprint: str
    status: ApplicationStatus
    apply_target: ApplyTarget
    message: str = ""
    applied_at: datetime = Field(default_factory=datetime.utcnow)


class PipelineStats(BaseModel):
    """Summary statistics for a pipeline run."""

    scraped: int = 0
    filtered: int = 0
    applied: int = 0
    skipped: int = 0
    failed: int = 0
    dry_run: int = 0
    cap_reached: bool = False
    results: list[ApplicationResult] = Field(default_factory=list)
    new_jobs: list[JobListing] = Field(default_factory=list)
