"""Route jobs to the appropriate apply adapter."""

from __future__ import annotations

from jobs_applier.apply.ashby import AshbyAdapter
from jobs_applier.apply.base import ApplyAdapter
from jobs_applier.apply.greenhouse import GreenhouseAdapter
from jobs_applier.apply.lever import LeverAdapter
from jobs_applier.apply.linkedin import LinkedInEasyApplyAdapter
from jobs_applier.models.job import ApplyTarget, JobListing


class ApplyRouter:
    """Detect apply target and return matching adapter."""

    def __init__(self) -> None:
        self._adapters: dict[ApplyTarget, ApplyAdapter] = {
            ApplyTarget.LINKEDIN_EASY_APPLY: LinkedInEasyApplyAdapter(),
            ApplyTarget.GREENHOUSE: GreenhouseAdapter(),
            ApplyTarget.LEVER: LeverAdapter(),
            ApplyTarget.ASHBY: AshbyAdapter(),
        }

    def get_target(self, job: JobListing) -> ApplyTarget:
        return job.apply_target()

    def get_adapter(self, job: JobListing) -> ApplyAdapter | None:
        target = self.get_target(job)
        return self._adapters.get(target)
