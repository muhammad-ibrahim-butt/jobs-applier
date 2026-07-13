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
    assert _is_usage_limit_error(RuntimeError("Monthly usage hard limit exceeded"))
    assert not _is_usage_limit_error(RuntimeError("timeout connecting to linkedin"))


def test_apify_usage_limit_error_is_runtime_error():
    assert issubclass(ApifyUsageLimitError, RuntimeError)


def test_scrape_continues_after_platform_failure(monkeypatch):
    from jobs_applier.config.profile import AppConfig, PlatformsEnabled, SearchConfig
    from jobs_applier.config.settings import Settings
    from jobs_applier.models.job import JobListing, JobPlatform
    from jobs_applier.scrapers.apify_client import ApifyJobScraper

    settings = Settings(apify_api_token="test-token")
    config = AppConfig(
        search=SearchConfig(platforms=["linkedin", "indeed"], queries=["python"]),
        platforms_enabled=PlatformsEnabled(linkedin=True, indeed=True, glassdoor=False),
    )
    scraper = ApifyJobScraper(settings, config)

    calls: list[list[str]] = []

    def fake_call(platforms: list[str]) -> list[JobListing]:
        calls.append(list(platforms))
        if platforms == ["linkedin", "indeed"]:
            raise RuntimeError("actor boom")
        if platforms == ["linkedin"]:
            raise RuntimeError("linkedin timeout")
        return [
            JobListing(
                platform=JobPlatform.INDEED,
                external_id="1",
                title="Backend Engineer",
                company="Acme",
            )
        ]

    monkeypatch.setattr(scraper, "_call_actor", fake_call)
    jobs = scraper.scrape()
    assert calls[0] == ["linkedin", "indeed"]
    assert ["linkedin"] in calls
    assert ["indeed"] in calls
    assert len(jobs) == 1
    assert jobs[0].platform == JobPlatform.INDEED


def test_scrape_quota_on_combined_returns_empty(monkeypatch):
    from jobs_applier.config.profile import AppConfig, PlatformsEnabled, SearchConfig
    from jobs_applier.config.settings import Settings
    from jobs_applier.scrapers.apify_client import ApifyJobScraper, ApifyUsageLimitError

    settings = Settings(apify_api_token="test-token")
    config = AppConfig(
        search=SearchConfig(platforms=["linkedin", "indeed"], queries=["python"]),
        platforms_enabled=PlatformsEnabled(linkedin=True, indeed=True, glassdoor=False),
    )
    scraper = ApifyJobScraper(settings, config)
    calls: list[list[str]] = []

    def fake_call(platforms: list[str]) -> list:
        calls.append(list(platforms))
        raise ApifyUsageLimitError("quota")

    monkeypatch.setattr(scraper, "_call_actor", fake_call)
    assert scraper.scrape() == []
    assert calls == [["linkedin", "indeed"]]  # no per-platform retry on hard quota


def test_scrape_stops_further_platforms_on_quota_during_fallback(monkeypatch):
    from jobs_applier.config.profile import AppConfig, PlatformsEnabled, SearchConfig
    from jobs_applier.config.settings import Settings
    from jobs_applier.scrapers.apify_client import ApifyJobScraper, ApifyUsageLimitError

    settings = Settings(apify_api_token="test-token")
    config = AppConfig(
        search=SearchConfig(platforms=["linkedin", "indeed"], queries=["python"]),
        platforms_enabled=PlatformsEnabled(linkedin=True, indeed=True, glassdoor=False),
    )
    scraper = ApifyJobScraper(settings, config)
    calls: list[list[str]] = []

    def fake_call(platforms: list[str]) -> list:
        calls.append(list(platforms))
        if len(platforms) > 1:
            raise RuntimeError("combined failed")
        raise ApifyUsageLimitError("quota")

    monkeypatch.setattr(scraper, "_call_actor", fake_call)
    assert scraper.scrape() == []
    assert calls == [["linkedin", "indeed"], ["linkedin"]]
    assert ["indeed"] not in calls
