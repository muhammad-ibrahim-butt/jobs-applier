"""Tests for resume relevance scoring."""

from jobs_applier.config.profile import ApplicantProfile, PersonalInfo, WorkInfo
from jobs_applier.filters.relevance import RelevanceScorer
from jobs_applier.models.job import JobListing, JobPlatform


def _profile() -> ApplicantProfile:
    return ApplicantProfile(
        personal=PersonalInfo(
            first_name="M",
            last_name="I",
            full_name="M I",
            email="a@b.com",
            phone="1",
        ),
        work=WorkInfo(skill_years={"python": 5, "laravel": 5, "react": 3}),
    )


def test_scores_matching_stack_higher():
    scorer = RelevanceScorer(_profile(), preferred_keywords=["django", "aws"])
    good = JobListing(
        platform=JobPlatform.LINKEDIN,
        external_id="1",
        title="Senior Python Laravel Engineer",
        company="Acme",
        description="Build APIs with Python, Laravel, React, and AWS",
    )
    weak = JobListing(
        platform=JobPlatform.INDEED,
        external_id="2",
        title="Java Android Developer",
        company="Other",
        description="Kotlin and Android Studio only",
    )
    assert scorer.score(good) > scorer.score(weak)
    assert scorer.score(good) >= 25


def test_title_only_listing_is_not_diluted():
    scorer = RelevanceScorer(_profile(), preferred_keywords=["django", "aws", "docker"])
    job = JobListing(
        platform=JobPlatform.LINKEDIN,
        external_id="3",
        title="Remote Python Laravel Developer",
        company="Acme",
        description="",
    )
    assert scorer.score(job) >= 25
