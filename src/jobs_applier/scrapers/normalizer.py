"""Normalize Apify actor output into JobListing models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jobs_applier.models.job import JobListing, JobPlatform


def _parse_platform(value: str | None) -> JobPlatform:
    if not value:
        return JobPlatform.UNKNOWN
    normalized = value.lower().strip()
    for platform in JobPlatform:
        if platform.value in normalized:
            return platform
    return JobPlatform.UNKNOWN


def _parse_datetime(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    # JobSpy returns datetime.date objects — do not call str.replace on them.
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        try:
            return datetime(int(value.year), int(value.month), int(value.day))
        except (TypeError, ValueError):
            return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.replace("+00:00", "Z"), fmt)
        except ValueError:
            continue
    return None


def _extract_salary(item: dict[str, Any]) -> tuple[int | None, int | None, str]:
    salary_min = (
        item.get("salaryMin")
        or item.get("minSalary")
        or item.get("salary_min")
        or item.get("min_amount")
    )
    salary_max = (
        item.get("salaryMax")
        or item.get("maxSalary")
        or item.get("salary_max")
        or item.get("max_amount")
    )
    currency = item.get("salaryCurrency") or item.get("currency") or "USD"

    if isinstance(item.get("salary"), dict):
        salary = item["salary"]
        salary_min = salary_min or salary.get("min")
        salary_max = salary_max or salary.get("max")
        currency = salary.get("currency") or currency

    def to_int(val: object) -> int | None:
        if val is None:
            return None
        try:
            return int(float(str(val).replace(",", "").replace("$", "")))
        except (ValueError, TypeError):
            return None

    return to_int(salary_min), to_int(salary_max), str(currency)


def normalize_apify_item(item: dict[str, Any]) -> JobListing | None:
    """Convert a single Apify dataset item to JobListing."""
    title = (
        item.get("title") or item.get("jobTitle") or item.get("position") or item.get("job_title")
    )
    company = item.get("company") or item.get("companyName") or item.get("company_name") or ""
    if not title:
        return None

    platform = _parse_platform(
        item.get("platform") or item.get("source") or item.get("site") or item.get("board")
    )
    external_id = str(
        item.get("id")
        or item.get("jobId")
        or item.get("job_id")
        or item.get("linkedinJobId")
        or item.get("link")
        or f"{company}-{title}".lower().replace(" ", "-")
    )

    apply_url = (
        item.get("applyUrl")
        or item.get("apply_url")
        or item.get("applicationUrl")
        or item.get("job_url_direct")
        or item.get("jobUrlDirect")
        or item.get("link")
        or ""
    )
    job_url = (
        item.get("jobUrl")
        or item.get("job_url")
        or item.get("link")
        or apply_url
        or item.get("job_url_direct")
        or ""
    )
    # Prefer company/ATS direct URL over a LinkedIn listing URL for apply routing.
    direct = str(item.get("job_url_direct") or item.get("jobUrlDirect") or "")
    if (
        direct
        and "linkedin.com" not in direct.lower()
        and (not apply_url or "linkedin.com" in str(apply_url).lower())
    ):
        apply_url = direct

    salary_min, salary_max, currency = _extract_salary(item)
    # JobSpy / openclawai actor uses snake_case (`is_remote`, `date_posted`).
    is_remote = bool(
        item.get("isRemote")
        or item.get("is_remote")
        or item.get("remote")
        or "remote" in str(item.get("location", "")).lower()
    )
    is_easy_apply = bool(item.get("easyApply") or item.get("easy_apply") or item.get("isEasyApply"))

    posted_at = _parse_datetime(
        item.get("postedAt")
        or item.get("posted_at")
        or item.get("datePosted")
        or item.get("date_posted")
    )

    return JobListing(
        platform=platform,
        external_id=external_id,
        title=str(title).strip(),
        company=str(company).strip(),
        location=str(item.get("location") or item.get("jobLocation") or ""),
        description=str(item.get("description") or item.get("jobDescription") or ""),
        apply_url=str(apply_url),
        job_url=str(job_url),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=currency,
        is_remote=is_remote,
        is_easy_apply=is_easy_apply,
        posted_at=posted_at,
        raw=item,
    )


def normalize_apify_dataset(items: list[dict[str, Any]]) -> list[JobListing]:
    """Normalize a full Apify dataset."""
    results: list[JobListing] = []
    seen: set[str] = set()
    for item in items:
        job = normalize_apify_item(item)
        if job and job.fingerprint not in seen:
            seen.add(job.fingerprint)
            results.append(job)
    return results
