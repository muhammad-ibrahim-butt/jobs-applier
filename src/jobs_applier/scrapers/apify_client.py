"""Apify client for multi-board job scraping."""

from __future__ import annotations

from typing import Any, cast

import structlog
from apify_client import ApifyClient

from jobs_applier.config.profile import AppConfig
from jobs_applier.config.settings import Settings
from jobs_applier.models.job import JobListing
from jobs_applier.scrapers.normalizer import normalize_apify_dataset

logger = structlog.get_logger(__name__)


class ApifyJobScraper:
    """Scrape jobs via Apify actor."""

    def __init__(self, settings: Settings, app_config: AppConfig) -> None:
        self._settings = settings
        self._config = app_config
        if not settings.apify_api_token:
            raise ValueError("APIFY_API_TOKEN is required. Set it in your .env file.")
        self._client = ApifyClient(settings.apify_api_token)

    def _build_actor_input(self) -> dict[str, Any]:
        search = self._config.search
        enabled = self._config.platforms_enabled
        platforms = [p for p in search.platforms if getattr(enabled, p, True)]

        return {
            "searchTerms": search.queries,
            "location": search.location,
            "country": search.country,
            "platforms": platforms,
            "maxResults": search.max_results,
            "easyApply": search.easy_apply_only,
            "hoursOld": search.hours_old,
        }

    def scrape(self) -> list[JobListing]:
        actor_input = self._build_actor_input()
        actor_id = self._settings.apify_actor_id

        logger.info("starting_apify_run", actor_id=actor_id, input=actor_input)
        run = self._client.actor(actor_id).call(run_input=actor_input)
        if run is None:
            raise RuntimeError(f"Apify actor run failed: {actor_id}")
        run_data = cast(dict[str, Any], run)
        dataset_id = str(run_data.get("defaultDatasetId", ""))
        if not dataset_id:
            raise RuntimeError("Apify run returned no dataset ID")
        items = list(self._client.dataset(dataset_id).iterate_items())

        jobs = normalize_apify_dataset(items)
        logger.info("apify_scrape_complete", raw_count=len(items), normalized_count=len(jobs))
        return jobs
