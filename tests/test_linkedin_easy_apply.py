"""Unit checks for LinkedIn Easy Apply helpers (no browser required)."""

from jobs_applier.apply.linkedin import (
    EASY_APPLY_ROLE_PATTERN,
    SUCCESS_TEXT_PATTERN,
    SUBMIT_ROLE_PATTERN,
)


def test_easy_apply_role_pattern_matches_variants() -> None:
    assert EASY_APPLY_ROLE_PATTERN.search("Easy Apply")
    assert EASY_APPLY_ROLE_PATTERN.search("easy apply")
    assert EASY_APPLY_ROLE_PATTERN.search("Easy  Apply")
    assert not EASY_APPLY_ROLE_PATTERN.search("Apply on company website")


def test_submit_pattern() -> None:
    assert SUBMIT_ROLE_PATTERN.search("Submit application")
    assert SUBMIT_ROLE_PATTERN.search("submit Application")


def test_success_text_pattern() -> None:
    assert SUCCESS_TEXT_PATTERN.search("Your application was sent.")
    assert SUCCESS_TEXT_PATTERN.search("Application submitted")
    assert SUCCESS_TEXT_PATTERN.search("You applied to this job")
    assert not SUCCESS_TEXT_PATTERN.search("Apply now")
