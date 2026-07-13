"""Run multiple scrape sources with fallback or merge strategies."""

from __future__ import annotations

from collections.abc import Callable

import structlog

from jobs_applier.config.profile import AppConfig
from jobs_applier.config.settings import Settings
from jobs_applier.models.job import JobListing
from jobs_applier.scrapers.apify_client import ApifyJobScraper
from jobs_applier.scrapers.base import JobScraper, dedupe_jobs
from jobs_applier.scrapers.jobspy_local import JobSpyLocalScraper
from jobs_applier.scrapers.remoteok import RemoteOKScraper
from jobs_applier.scrapers.remotive import RemotiveScraper

logger = structlog.get_logger(__name__)

SourceFactory = Callable[[], JobScraper]


class MultiSourceScraper:
    """Try configured sources in order (fallback) or combine them (merge)."""

    name = "multi"

    def __init__(self, settings: Settings, app_config: AppConfig) -> None:
        self._settings = settings
        self._config = app_config

    def _factories(self) -> list[tuple[str, SourceFactory]]:
        settings = self._settings
        config = self._config

        def apify() -> JobScraper:
            return ApifyJobScraper(settings, config)

        def jobspy() -> JobScraper:
            return JobSpyLocalScraper(config)

        def remotive() -> JobScraper:
            return RemotiveScraper(config)

        def remoteok() -> JobScraper:
            return RemoteOKScraper(config)

        registry: dict[str, SourceFactory] = {
            "apify": apify,
            "jobspy": jobspy,
            "remotive": remotive,
            "remoteok": remoteok,
        }
        ordered: list[tuple[str, SourceFactory]] = []
        for name in self._config.search.sources:
            key = name.strip().lower()
            factory = registry.get(key)
            if factory is None:
                logger.warning("unknown_scrape_source", source=name)
                continue
            if key == "apify" and not settings.apify_api_token:
                logger.info("skip_apify_no_token")
                continue
            ordered.append((key, factory))
        return ordered

    def scrape(self) -> list[JobListing]:
        mode = (self._config.search.source_mode or "fallback").lower()
        factories = self._factories()
        if not factories:
            logger.error("no_scrape_sources_configured")
            return []

        collected: list[JobListing] = []
        for name, factory in factories:
            try:
                scraper = factory()
                jobs = scraper.scrape()
            except Exception as exc:
                logger.error("scrape_source_failed", source=name, error=str(exc))
                continue

            logger.info("scrape_source_complete", source=name, count=len(jobs), mode=mode)
            if not jobs:
                continue
            if mode == "fallback":
                return jobs
            collected.extend(jobs)

        return dedupe_jobs(collected)
