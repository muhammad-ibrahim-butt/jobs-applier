"""Tests for multi-source scraping."""

from jobs_applier.config.profile import AppConfig, SearchConfig
from jobs_applier.config.settings import Settings
from jobs_applier.models.job import JobListing, JobPlatform
from jobs_applier.scrapers.multi import MultiSourceScraper
from jobs_applier.scrapers.remoteok import _map_remoteok
from jobs_applier.scrapers.remotive import RemotiveScraper, _map_remotive, _search_term


def test_remotive_map_fields():
    mapped = _map_remotive(
        {
            "id": 99,
            "title": "Python Engineer",
            "company_name": "Acme",
            "url": "https://remotive.com/jobs/99",
            "description": "Build APIs",
            "candidate_required_location": "Worldwide",
            "publication_date": "2026-07-13T12:00:00",
        }
    )
    assert mapped["id"] == "remotive-99"
    assert mapped["is_remote"] is True
    assert mapped["date_posted"] == "2026-07-13"


def test_remotive_search_term_strips_noise():
    assert "remote" not in _search_term("remote software engineer python")
    assert "python" in _search_term("remote software engineer python")


def test_remoteok_map_fields():
    mapped = _map_remoteok(
        {
            "id": "42",
            "position": "Laravel Developer",
            "company": "Co",
            "url": "/remote-jobs/42",
            "epoch": 1720000000,
            "tags": ["laravel", "php"],
        }
    )
    assert mapped["title"] == "Laravel Developer"
    assert mapped["job_url"].startswith("https://remoteok.com/")
    assert mapped["date_posted"]


def test_multi_fallback_uses_second_source_when_first_empty(monkeypatch):
    settings = Settings(apify_api_token="tok")
    config = AppConfig(
        search=SearchConfig(
            sources=["apify", "remotive"],
            source_mode="fallback",
            queries=["python engineer"],
            max_results=5,
        )
    )
    multi = MultiSourceScraper(settings, config)

    class Empty:
        name = "apify"

        def scrape(self):
            return []

    class Filled:
        name = "remotive"

        def scrape(self):
            return [
                JobListing(
                    platform=JobPlatform.UNKNOWN,
                    external_id="r1",
                    title="Python Engineer",
                    company="Acme",
                )
            ]

    monkeypatch.setattr(
        multi,
        "_factories",
        lambda: [("apify", lambda: Empty()), ("remotive", lambda: Filled())],
    )
    jobs = multi.scrape()
    assert len(jobs) == 1
    assert jobs[0].title == "Python Engineer"


def test_multi_fallback_skips_failed_source(monkeypatch):
    settings = Settings(apify_api_token="")
    config = AppConfig(
        search=SearchConfig(
            sources=["apify", "remoteok"],
            source_mode="fallback",
            queries=["backend"],
        )
    )
    multi = MultiSourceScraper(settings, config)

    class Boom:
        name = "apify"

        def scrape(self):
            raise RuntimeError("quota")

    class Ok:
        name = "remoteok"

        def scrape(self):
            return [
                JobListing(
                    platform=JobPlatform.UNKNOWN,
                    external_id="ok1",
                    title="Backend Engineer",
                    company="Z",
                )
            ]

    monkeypatch.setattr(
        multi,
        "_factories",
        lambda: [("apify", lambda: Boom()), ("remoteok", lambda: Ok())],
    )
    jobs = multi.scrape()
    assert len(jobs) == 1


def test_remotive_scraper_uses_search_param(monkeypatch):
    config = AppConfig(search=SearchConfig(queries=["python django"], max_results=10))
    scraper = RemotiveScraper(config)
    urls: list[str] = []

    def fake_get(url: str):
        urls.append(url)
        return {
            "jobs": [
                {
                    "id": 1,
                    "title": "Python Django Developer",
                    "company_name": "A",
                    "url": "https://remotive.com/1",
                    "description": "django",
                    "tags": ["python"],
                    "candidate_required_location": "Remote",
                    "publication_date": "2026-07-01T00:00:00",
                },
            ]
        }

    monkeypatch.setattr("jobs_applier.scrapers.remotive._get_json", fake_get)
    jobs = scraper.scrape()
    assert len(jobs) == 1
    assert "search=" in urls[0]
    assert "python" in urls[0]
