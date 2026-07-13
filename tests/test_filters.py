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
        "location": "Remote",
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


def test_keeps_non_easy_apply_for_manual_email():
    """Non-Easy-Apply jobs must pass filters so they can be emailed."""
    config = AppConfig(
        search=SearchConfig(easy_apply_only=False),
        filters=FilterConfig(remote_only=True),
    )
    engine = FilterEngine(config, _profile())
    ok, reason = engine.passes(
        _make_job(is_easy_apply=False, apply_url="https://company.com/jobs/1")
    )
    assert ok is True
    assert reason == "passed"


def test_rejects_onsite_when_remote_only():
    config = AppConfig(filters=FilterConfig(remote_only=True))
    engine = FilterEngine(config, _profile())
    ok, reason = engine.passes(
        _make_job(
            is_remote=False,
            location="New York, NY (On-site)",
            description="Must work from HQ",
        )
    )
    assert ok is False
    assert reason == "not remote"


def test_rejects_old_jobs():
    config = AppConfig(filters=FilterConfig(max_days_old=7))
    engine = FilterEngine(config, _profile())
    old_date = datetime.utcnow() - timedelta(days=30)
    ok, reason = engine.passes(_make_job(posted_at=old_date))
    assert ok is False
    assert reason == "too old"


def test_rejects_missing_posted_date_when_required():
    config = AppConfig(filters=FilterConfig(require_posted_date=True, max_days_old=2))
    engine = FilterEngine(config, _profile())
    ok, reason = engine.passes(_make_job(posted_at=None))
    assert ok is False
    assert reason == "missing posted date"


def test_select_for_email_caps_results():
    config = AppConfig(filters=FilterConfig(max_email_jobs=2, min_relevance_score=0))
    engine = FilterEngine(config, _profile())
    jobs = [
        _make_job(external_id="1", title="Python Engineer", description="python laravel"),
        _make_job(external_id="2", title="Java Dev", description="java spring"),
        _make_job(external_id="3", title="React Laravel", description="react laravel python"),
    ]
    selected = engine.select_for_email(jobs)
    assert len(selected) == 2


def test_include_title_keywords():
    config = AppConfig(filters=FilterConfig(include_title_keywords=["engineer"]))
    engine = FilterEngine(config, _profile())
    ok, _ = engine.passes(_make_job(title="Product Manager"))
    assert ok is False


def test_exclude_title_uses_word_boundaries():
    config = AppConfig(filters=FilterConfig(exclude_title_keywords=["staff"]))
    engine = FilterEngine(config, _profile())
    ok_staff, reason = engine.passes(_make_job(title="Staff Software Engineer"))
    assert ok_staff is False
    assert "staff" in reason
    ok_place, _ = engine.passes(_make_job(title="Engineer at Stafford Labs"))
    assert ok_place is True
