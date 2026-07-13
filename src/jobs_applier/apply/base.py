"""Apply adapter protocol."""

from __future__ import annotations

from typing import Protocol

from playwright.sync_api import BrowserContext

from jobs_applier.config.profile import ApplicantProfile
from jobs_applier.config.settings import Settings
from jobs_applier.models.job import ApplicationResult, JobListing
from jobs_applier.profile.qa_cache import QuestionCache


class ApplyAdapter(Protocol):
    """Protocol for platform-specific apply adapters."""

    def can_apply(self, job: JobListing) -> bool: ...

    def apply(
        self,
        job: JobListing,
        context: BrowserContext,
        profile: ApplicantProfile,
        qa_cache: QuestionCache,
        settings: Settings,
        dry_run: bool,
    ) -> ApplicationResult: ...
