"""Apify client for multi-board job scraping."""

from __future__ import annotations

from typing import Any

import structlog
from apify_client import ApifyClient

from jobs_applier.config.profile import AppConfig
from jobs_applier.config.settings import Settings
from jobs_applier.models.job import JobListing
from jobs_applier.scrapers.normalizer import normalize_apify_dataset

logger = structlog.get_logger(__name__)

_COUNTRY_ALIASES: dict[str, str] = {
    "usa": "usa",
    "us": "usa",
    "united states": "usa",
    "united states of america": "usa",
    "uk": "uk",
    "united kingdom": "uk",
    "pakistan": "pakistan",
}

_WORLDWIDE = {"", "worldwide", "world", "global", "any", "anywhere"}


def _normalize_country(raw: str) -> str | None:
    key = raw.strip().lower()
    if key in _WORLDWIDE:
        return None
    return _COUNTRY_ALIASES.get(key, key)


def _dataset_id_from_run(run: Any) -> str:
    """Extract dataset id from Apify Run model or plain dict."""
    if isinstance(run, dict):
        return str(run.get("defaultDatasetId") or run.get("default_dataset_id") or "")
    for attr in ("default_dataset_id", "defaultDatasetId"):
        value = getattr(run, attr, None)
        if value:
            return str(value)
    return ""


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
        country = _normalize_country(search.country)

        # openclawai/job-board-scraper uses `sites`. Omitting country for worldwide
        # avoids JobSpy LinkedIn country bugs (usa → uganda/lebanon).
        actor_input: dict[str, Any] = {
            "searchTerms": search.queries,
            "location": search.location or "Remote",
            "sites": platforms,
            "platforms": platforms,
            "maxResults": search.max_results,
            "isRemote": search.is_remote,
            "hoursOld": search.hours_old,
            # Empty LinkedIn descriptions make relevance scoring useless.
            "linkedinFetchDescription": True,
        }
        if country:
            actor_input["country"] = country
            actor_input["countryIndeed"] = country
        # Prefer Easy Apply only when explicitly requested — can zero out Indeed/Glassdoor
        if search.easy_apply_only:
            actor_input["easyApply"] = True
            actor_input.pop("hoursOld", None)
        return actor_input

    def scrape(self) -> list[JobListing]:
        actor_input = self._build_actor_input()
        actor_id = self._settings.apify_actor_id

        logger.info("starting_apify_run", actor_id=actor_id, input=actor_input)
        run = self._client.actor(actor_id).call(run_input=actor_input)
        if run is None:
            raise RuntimeError(f"Apify actor run failed: {actor_id}")
        dataset_id = _dataset_id_from_run(run)
        if not dataset_id:
            raise RuntimeError("Apify run returned no dataset ID")
        items = list(self._client.dataset(dataset_id).iterate_items())

        jobs = normalize_apify_dataset(items)
        logger.info("apify_scrape_complete", raw_count=len(items), normalized_count=len(jobs))
        return jobs
