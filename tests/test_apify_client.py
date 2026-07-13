"""Tests for Apify client helpers."""

from jobs_applier.scrapers.apify_client import (
    ApifyUsageLimitError,
    _dataset_id_from_run,
    _is_usage_limit_error,
    _normalize_country,
)


def test_normalize_country_usa_aliases():
    assert _normalize_country("USA") == "usa"
    assert _normalize_country("United States") == "usa"
    assert _normalize_country("canada") == "canada"


def test_normalize_country_worldwide_is_none():
    assert _normalize_country("worldwide") is None
    assert _normalize_country("") is None
    assert _normalize_country("any") is None


def test_dataset_id_from_dict():
    assert _dataset_id_from_run({"defaultDatasetId": "abc"}) == "abc"


def test_dataset_id_from_object():
    class FakeRun:
        default_dataset_id = "xyz"

    assert _dataset_id_from_run(FakeRun()) == "xyz"


def test_is_usage_limit_error_detects_quota_text():
    assert _is_usage_limit_error(RuntimeError("Monthly usage quota exceeded"))
    assert not _is_usage_limit_error(RuntimeError("timeout connecting to linkedin"))


def test_apify_usage_limit_error_is_runtime_error():
    assert issubclass(ApifyUsageLimitError, RuntimeError)
