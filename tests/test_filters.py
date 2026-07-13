"""Tests for filter engine."""

from datetime import datetime, timedelta

from jobs_applier.config.profile import (
    AppConfig,
    ApplicantProfile,
    FilterConfig,
    PersonalInfo,
    SearchConfig,
)
from jobs_applier.filters.engine import FilterEngine
from jobs_applier.models.job import JobListing, JobPlatform


def _make_job(**kwargs) -> JobListing:
    defaults = {
        "platform": JobPlatform.LINKEDIN,
        "external_id": "1",
        "title": "Software Engineer",
        "company": "Acme",
        "description": "Python and AWS experience required",
        "is_easy_apply": True,
        "is_remote": True,
        "posted_at": datetime.utcnow(),
    }
    defaults.update(kwargs)
    return JobListing(**defaults)


def _profile() -> ApplicantProfile:
    return ApplicantProfile(
        personal=PersonalInfo(
            first_name="Jane",
            last_name="Doe",
            full_name="Jane Doe",
            email="jane@example.com",
            phone="+1-555-0100",
        )
    )


def test_passes_default_job():
    engine = FilterEngine(AppConfig(), _profile())
    ok, reason = engine.passes(_make_job())
    assert ok is True
    assert reason == "passed"


def test_rejects_excluded_title_keyword():
    config = AppConfig(filters=FilterConfig(exclude_title_keywords=["intern"]))
    engine = FilterEngine(config, _profile())
    ok, reason = engine.passes(_make_job(title="Software Engineering Intern"))
    assert ok is False
    assert "intern" in reason


def test_rejects_non_easy_apply_when_required():
    config = AppConfig(search=SearchConfig(easy_apply_only=True))
    engine = FilterEngine(config, _profile())
    ok, _ = engine.passes(_make_job(is_easy_apply=False))
    assert ok is False


def test_rejects_old_jobs():
    config = AppConfig(filters=FilterConfig(max_days_old=7))
    engine = FilterEngine(config, _profile())
    old_date = datetime.utcnow() - timedelta(days=30)
    ok, reason = engine.passes(_make_job(posted_at=old_date))
    assert ok is False
    assert reason == "too old"


def test_include_title_keywords():
    config = AppConfig(filters=FilterConfig(include_title_keywords=["engineer"]))
    engine = FilterEngine(config, _profile())
    ok, _ = engine.passes(_make_job(title="Product Manager"))
    assert ok is False
