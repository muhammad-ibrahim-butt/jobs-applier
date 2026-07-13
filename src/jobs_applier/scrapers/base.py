"""Scraper protocol and shared helpers."""

from __future__ import annotations

from typing import Protocol

from jobs_applier.models.job import JobListing


class JobScraper(Protocol):
    """Scrape jobs into normalized listings."""

    name: str

    def scrape(self) -> list[JobListing]: ...


def dedupe_jobs(jobs: list[JobListing]) -> list[JobListing]:
    seen: set[str] = set()
    out: list[JobListing] = []
    for job in jobs:
        if job.fingerprint in seen:
            continue
        seen.add(job.fingerprint)
        out.append(job)
    return out
