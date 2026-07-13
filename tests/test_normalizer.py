"""Tests for job normalizer."""

from jobs_applier.models.job import JobPlatform
from jobs_applier.scrapers.normalizer import normalize_apify_item


def test_normalize_linkedin_item():
    item = {
        "platform": "linkedin",
        "id": "12345",
        "title": "Software Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "description": "Build great software",
        "link": "https://linkedin.com/jobs/12345",
        "easyApply": True,
        "isRemote": True,
        "salaryMin": 100000,
        "salaryMax": 150000,
    }
    job = normalize_apify_item(item)
    assert job is not None
    assert job.platform == JobPlatform.LINKEDIN
    assert job.title == "Software Engineer"
    assert job.is_easy_apply is True
    assert job.is_remote is True
    assert job.salary_min == 100000
    assert job.fingerprint == "linkedin:12345"


def test_normalize_indeed_item():
    item = {
        "source": "indeed",
        "jobId": "abc-999",
        "jobTitle": "Backend Developer",
        "companyName": "Tech Inc",
        "jobLocation": "New York, NY",
        "applyUrl": "https://indeed.com/apply/abc-999",
    }
    job = normalize_apify_item(item)
    assert job is not None
    assert job.platform == JobPlatform.INDEED
    assert job.title == "Backend Developer"
    assert job.company == "Tech Inc"


def test_normalize_missing_title_returns_none():
    assert normalize_apify_item({"company": "No Title Corp"}) is None
