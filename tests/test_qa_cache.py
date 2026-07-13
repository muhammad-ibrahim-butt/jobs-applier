"""Tests for Q&A cache."""

from pathlib import Path

from jobs_applier.config.profile import ApplicantProfile, PersonalInfo, WorkInfo
from jobs_applier.profile.qa_cache import QuestionCache


def _profile() -> ApplicantProfile:
    return ApplicantProfile(
        personal=PersonalInfo(
            first_name="Jane",
            last_name="Doe",
            full_name="Jane Doe",
            email="jane@example.com",
            phone="+1-555-0100",
        ),
        work=WorkInfo(years_of_experience=5, expected_salary="120000"),
        defaults={
            "authorized to work": "Yes",
            "require sponsorship": "No",
        },
    )


def test_resolve_from_profile(tmp_path: Path):
    cache_path = tmp_path / "questions.json"
    cache = QuestionCache(cache_path, _profile())

    assert cache.resolve_from_profile("Email address") == "jane@example.com"
    assert cache.resolve_from_profile("Years of experience") == "5"
    assert cache.resolve_from_profile("Are you authorized to work?") == "Yes"


def test_cache_persists(tmp_path: Path):
    cache_path = tmp_path / "questions.json"
    cache = QuestionCache(cache_path, _profile())
    cache.set_answer("Favorite programming language", "Python")

    cache2 = QuestionCache(cache_path, _profile())
    assert cache2.get_answer("Favorite programming language") == "Python"
