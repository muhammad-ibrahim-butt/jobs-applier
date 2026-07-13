"""Free Remotive remote-jobs JSON API (no Apify)."""

from __future__ import annotations

import json
import urllib.error
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
        # One API call; client-side filter against queries.
        url = f"{_REMOTIVE_URL}?category=software-dev&limit={min(search.max_results * 4, 100)}"
        payload = _get_json(url)
        jobs_raw = payload.get("jobs") or []
        queries = [q.lower() for q in search.queries]
        jobs: list[JobListing] = []
        for item in jobs_raw:
            mapped = _map_remotive(item)
            title = (mapped.get("title") or "").lower()
            tags = " ".join(str(t).lower() for t in (item.get("tags") or []))
            blob = f"{title} {tags} {(mapped.get('description') or '')[:500].lower()}"
            if not _matches_queries(blob, queries):
                continue
            job = normalize_apify_item(mapped)
            if job:
                jobs.append(job)
            if len(jobs) >= search.max_results:
                break
        logger.info("remotive_scrape_complete", count=len(jobs), raw=len(jobs_raw))
        return jobs


def _matches_queries(blob: str, queries: list[str]) -> bool:
    if not queries:
        return True
    if any(q in blob for q in queries):
        return True
    tokens = {t for q in queries for t in q.split() if len(t) > 3}
    return bool(tokens) and any(t in blob for t in tokens)


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
