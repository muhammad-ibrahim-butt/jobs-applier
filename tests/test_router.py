"""Tests for apply router."""

from jobs_applier.apply.router import ApplyRouter
from jobs_applier.models.job import ApplyTarget, JobListing, JobPlatform


def _job(**kwargs) -> JobListing:
    defaults = {
        "platform": JobPlatform.LINKEDIN,
        "external_id": "1",
        "title": "Engineer",
        "company": "Co",
        "is_easy_apply": True,
        "job_url": "https://linkedin.com/jobs/1",
    }
    defaults.update(kwargs)
    return JobListing(**defaults)


def test_routes_linkedin_easy_apply():
    router = ApplyRouter()
    job = _job()
    assert router.get_target(job) == ApplyTarget.LINKEDIN_EASY_APPLY
    assert router.get_adapter(job) is not None


def test_routes_greenhouse():
    router = ApplyRouter()
    job = _job(
        platform=JobPlatform.INDEED,
        is_easy_apply=False,
        apply_url="https://boards.greenhouse.io/company/jobs/123",
    )
    assert router.get_target(job) == ApplyTarget.GREENHOUSE


def test_routes_lever():
    router = ApplyRouter()
    job = _job(
        platform=JobPlatform.GLASSDOOR,
        is_easy_apply=False,
        apply_url="https://jobs.lever.co/company/abc",
    )
    assert router.get_target(job) == ApplyTarget.LEVER


def test_unsupported_target():
    router = ApplyRouter()
    job = _job(
        is_easy_apply=False,
        apply_url="https://myworkdayjobs.com/company/job/123",
    )
    assert router.get_target(job) == ApplyTarget.UNSUPPORTED
    assert router.get_adapter(job) is None
