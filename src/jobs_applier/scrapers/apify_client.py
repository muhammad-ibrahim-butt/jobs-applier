"""Apify client for multi-board job scraping."""

from __future__ import annotations

from typing import Any

import structlog
from apify_client import ApifyClient
from apify_client.errors import ApifyApiError

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

_USAGE_NEEDLES = (
    "quota",
    "limit",
    "usage",
    "insufficient",
    "payment required",
    "monthly usage",
    "memory limit",
    "out of memory",
    "not enough",
    "credit",
    "hard limit",
    "forbidden",
)


class ApifyUsageLimitError(RuntimeError):
    """Apify free-tier / paid usage limit was hit."""


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


def _is_usage_limit_error(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "statusCode", None)
    if status in (402, 403, 429):
        text = str(exc).lower()
        # 403 is sometimes auth; only treat as quota when the body says so.
        if status == 403 and not any(n in text for n in _USAGE_NEEDLES):
            return False
        if status in (402, 429):
            return True
        return True
    text = str(exc).lower()
    return any(needle in text for needle in _USAGE_NEEDLES)


class ApifyJobScraper:
    """Scrape jobs via Apify actor — one site at a time so one board's failure is isolated."""

    def __init__(self, settings: Settings, app_config: AppConfig) -> None:
        self._settings = settings
        self._config = app_config
        if not settings.apify_api_token:
            raise ValueError("APIFY_API_TOKEN is required. Set it in your .env file.")
        self._client = ApifyClient(settings.apify_api_token)

    def _enabled_platforms(self) -> list[str]:
        search = self._config.search
        enabled = self._config.platforms_enabled
        return [p for p in search.platforms if getattr(enabled, p, True)]

    def _build_actor_input(self, platforms: list[str]) -> dict[str, Any]:
        search = self._config.search
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
            # Default off: free tiers burn CU fetching every LinkedIn description.
            "linkedinFetchDescription": search.fetch_linkedin_descriptions,
        }
        if country:
            actor_input["country"] = country
            actor_input["countryIndeed"] = country
        # Prefer Easy Apply only when explicitly requested — can zero out Indeed/Glassdoor
        if search.easy_apply_only:
            actor_input["easyApply"] = True
            actor_input.pop("hoursOld", None)
        return actor_input

    def _call_actor(self, platforms: list[str]) -> list[JobListing]:
        actor_input = self._build_actor_input(platforms)
        actor_id = self._settings.apify_actor_id
        logger.info("starting_apify_run", actor_id=actor_id, platforms=platforms, input=actor_input)

        try:
            run = self._client.actor(actor_id).call(run_input=actor_input)
        except ApifyApiError as exc:
            if _is_usage_limit_error(exc):
                raise ApifyUsageLimitError(
                    "Apify usage/quota limit hit (common on free tiers). "
                    "Lower max_results, fewer queries/platforms, disable "
                    "fetch_linkedin_descriptions, or raise RUN_INTERVAL_MINUTES. "
                    f"Original: {exc}"
                ) from exc
            raise
        except Exception as exc:
            if _is_usage_limit_error(exc):
                raise ApifyUsageLimitError(
                    f"Apify usage/quota limit hit (common on free tiers). Original: {exc}"
                ) from exc
            raise

        if run is None:
            raise RuntimeError(f"Apify actor run failed: {actor_id}")
        dataset_id = _dataset_id_from_run(run)
        if not dataset_id:
            raise RuntimeError("Apify run returned no dataset ID")
        items = list(self._client.dataset(dataset_id).iterate_items())
        jobs = normalize_apify_dataset(items)
        logger.info(
            "apify_platform_complete",
            platforms=platforms,
            raw_count=len(items),
            normalized_count=len(jobs),
        )
        return jobs

    def scrape(self) -> list[JobListing]:
        """Scrape boards; isolate failures so one site cannot cancel the rest.

        Prefer a single combined Apify run (cheaper). If that fails for a
        non-quota reason, retry each platform alone. Quota errors stop further
        Apify calls and return whatever was collected.
        """
        platforms = self._enabled_platforms()
        if not platforms:
            logger.warning("no_platforms_enabled")
            return []

        try:
            jobs = self._call_actor(platforms)
            logger.info("apify_scrape_complete", normalized_count=len(jobs), mode="combined")
            return jobs
        except ApifyUsageLimitError as exc:
            logger.error("apify_quota_hit", error=str(exc), mode="combined")
            return []
        except Exception as exc:
            logger.warning(
                "apify_combined_failed_retrying_per_platform",
                error=str(exc),
                platforms=platforms,
            )

        collected: list[JobListing] = []
        seen: set[str] = set()
        for platform in platforms:
            try:
                jobs = self._call_actor([platform])
            except ApifyUsageLimitError as exc:
                logger.error(
                    "apify_quota_hit",
                    platform=platform,
                    error=str(exc),
                    tip="Stopping further Apify calls; keeping jobs already scraped",
                )
                break
            except Exception as exc:
                logger.error(
                    "apify_platform_failed",
                    platform=platform,
                    error=str(exc),
                    tip="Other platforms will still run",
                )
                continue

            for job in jobs:
                if job.fingerprint not in seen:
                    seen.add(job.fingerprint)
                    collected.append(job)

        logger.info(
            "apify_scrape_complete",
            normalized_count=len(collected),
            mode="per_platform_fallback",
        )
        return collected
