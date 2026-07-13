"""Free RemoteOK JSON API (no Apify)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

import structlog

from jobs_applier.config.profile import AppConfig
from jobs_applier.models.job import JobListing
from jobs_applier.scrapers.normalizer import normalize_apify_item

logger = structlog.get_logger(__name__)

_REMOTEOK_URL = "https://remoteok.com/api"


class RemoteOKScraper:
    """Public RemoteOK API — remote tech jobs."""

    name = "remoteok"

    def __init__(self, app_config: AppConfig) -> None:
        self._config = app_config

    def scrape(self) -> list[JobListing]:
        search = self._config.search
        payload = _get_json(_REMOTEOK_URL)
        if not isinstance(payload, list):
            raise RuntimeError("RemoteOK returned unexpected payload")

        queries = [q.lower() for q in search.queries]
        tokens = {t for q in queries for t in q.split() if len(t) > 3}
        jobs: list[JobListing] = []
        for item in payload:
            if not isinstance(item, dict) or not item.get("id") or not item.get("position"):
                continue
            mapped = _map_remoteok(item)
            blob = (
                f"{mapped.get('title', '')} {mapped.get('description', '')[:400]} "
                f"{' '.join(str(t) for t in (item.get('tags') or []))}"
            ).lower()
            if tokens and not any(t in blob for t in tokens):
                continue
            job = normalize_apify_item(mapped)
            if job:
                jobs.append(job)
            if len(jobs) >= search.max_results:
                break
        logger.info("remoteok_scrape_complete", count=len(jobs))
        return jobs


def _map_remoteok(item: dict[str, Any]) -> dict[str, Any]:
    epoch = item.get("epoch") or item.get("date")
    date_posted = None
    if isinstance(epoch, (int, float)):
        date_posted = datetime.fromtimestamp(epoch, tz=UTC).strftime("%Y-%m-%d")
    url = item.get("url") or item.get("apply_url") or ""
    if url and url.startswith("/"):
        url = f"https://remoteok.com{url}"
    return {
        "site": "unknown",
        "id": f"remoteok-{item.get('id')}",
        "title": item.get("position") or item.get("title") or "",
        "company": item.get("company") or "",
        "location": item.get("location") or "Remote",
        "description": item.get("description") or "",
        "job_url": url,
        "job_url_direct": item.get("apply_url") or url,
        "is_remote": True,
        "date_posted": date_posted,
        "salary_min": item.get("salary_min"),
        "salary_max": item.get("salary_max"),
    }


def _get_json(url: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "jobs-applier/0.1 (+https://github.com/muhammad-ibrahim-butt/jobs-applier)"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"RemoteOK HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"RemoteOK network error: {exc.reason}") from exc
