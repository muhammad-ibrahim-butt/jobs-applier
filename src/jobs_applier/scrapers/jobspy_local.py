"""Local JobSpy scraper — same boards Apify wraps, no cloud quota."""

from __future__ import annotations

from typing import Any

import structlog

from jobs_applier.config.profile import AppConfig
from jobs_applier.models.job import JobListing
from jobs_applier.scrapers.normalizer import normalize_apify_dataset

logger = structlog.get_logger(__name__)

# JobSpy site names we map from config platforms.
_SITE_MAP = {
    "linkedin": "linkedin",
    "indeed": "indeed",
    "glassdoor": "glassdoor",
}


class JobSpyLocalScraper:
    """Run python-jobspy locally when Apify is unavailable or exhausted."""

    name = "jobspy"

    def __init__(self, app_config: AppConfig) -> None:
        self._config = app_config

    def scrape(self) -> list[JobListing]:
        try:
            from jobspy import scrape_jobs
        except ImportError as exc:
            raise RuntimeError("python-jobspy is not installed. Run: uv add python-jobspy") from exc

        search = self._config.search
        enabled = self._config.platforms_enabled
        sites = [
            _SITE_MAP[p] for p in search.platforms if getattr(enabled, p, True) and p in _SITE_MAP
        ]
        if not sites:
            sites = ["linkedin", "indeed"]

        country = (search.country or "").strip().lower()
        country_indeed = (
            "USA" if country in {"", "worldwide", "world", "global", "any"} else country
        )

        all_items: list[dict[str, Any]] = []
        # Cap queries so local scrapes stay fast on free / home IPs.
        for query in search.queries[:3]:
            logger.info("jobspy_query_start", query=query, sites=sites)
            try:
                frame = scrape_jobs(
                    site_name=sites,
                    search_term=query,
                    location=search.location or "Remote",
                    results_wanted=min(search.max_results, 20),
                    hours_old=search.hours_old,
                    is_remote=search.is_remote,
                    country_indeed=country_indeed,
                    linkedin_fetch_description=search.fetch_linkedin_descriptions,
                    verbose=0,
                )
            except Exception as exc:
                logger.error("jobspy_query_failed", query=query, error=str(exc))
                continue

            if frame is None or getattr(frame, "empty", True):
                continue
            records = frame.where(frame.notna(), None).to_dict(orient="records")
            for row in records:
                cleaned = {k: _clean_cell(v) for k, v in row.items()}
                all_items.append(cleaned)

        jobs = normalize_apify_dataset(all_items)
        logger.info("jobspy_scrape_complete", raw=len(all_items), normalized=len(jobs))
        return jobs


def _clean_cell(value: object) -> object:
    if value is None:
        return None
    # pandas / numpy NaN
    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return None
    except Exception:
        pass
    text = str(value)
    if text.lower() in {"nan", "nat", "none"}:
        return None
    return value
