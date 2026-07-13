"""Free Remotive remote-jobs JSON API (no Apify)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import structlog

from jobs_applier.config.profile import AppConfig
from jobs_applier.models.job import JobListing
from jobs_applier.scrapers.normalizer import normalize_apify_item

logger = structlog.get_logger(__name__)

_REMOTIVE_URL = "https://remotive.com/api/remote-jobs"


class RemotiveScraper:
    """Public Remotive API — remote software/dev jobs."""

    name = "remotive"

    def __init__(self, app_config: AppConfig) -> None:
        self._config = app_config

    def scrape(self) -> list[JobListing]:
        search = self._config.search
        seen: set[str] = set()
        jobs: list[JobListing] = []
        # Search terms pull mid-level matches better than one category dump.
        searches = [_search_term(q) for q in search.queries[:3]] or ["software"]
        for term in searches:
            params = urllib.parse.urlencode(
                {
                    "category": "software-dev",
                    "search": term,
                    "limit": min(search.max_results * 2, 50),
                }
            )
            payload = _get_json(f"{_REMOTIVE_URL}?{params}")
            for item in payload.get("jobs") or []:
                mapped = _map_remotive(item)
                job = normalize_apify_item(mapped)
                if not job or job.fingerprint in seen:
                    continue
                seen.add(job.fingerprint)
                jobs.append(job)
                if len(jobs) >= search.max_results:
                    logger.info("remotive_scrape_complete", count=len(jobs))
                    return jobs
        logger.info("remotive_scrape_complete", count=len(jobs))
        return jobs


def _search_term(query: str) -> str:
    """Turn 'remote software engineer python' into a Remotive search string."""
    stop = {"remote", "worldwide", "fully", "job", "jobs", "the", "and", "with"}
    parts = [p for p in query.lower().split() if p not in stop and len(p) > 1]
    return " ".join(parts[:4]) or query


def _map_remotive(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "site": "unknown",
        "id": f"remotive-{item.get('id')}",
        "title": item.get("title") or "",
        "company": item.get("company_name") or "",
        "location": item.get("candidate_required_location") or "Remote",
        "description": item.get("description") or "",
        "job_url": item.get("url") or "",
        "job_url_direct": item.get("url") or "",
        "is_remote": True,
        "date_posted": (item.get("publication_date") or "")[:10] or None,
        "salary_min": None,
        "salary_max": None,
    }


def _get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "jobs-applier/0.1 (+https://github.com/muhammad-ibrahim-butt/jobs-applier)"
            )
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise RuntimeError("Remotive returned unexpected payload")
        return data
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Remotive HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Remotive network error: {exc.reason}") from exc
