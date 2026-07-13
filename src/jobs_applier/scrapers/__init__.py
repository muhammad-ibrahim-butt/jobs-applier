"""Job scrapers."""

from jobs_applier.scrapers.apify_client import ApifyJobScraper
from jobs_applier.scrapers.jobspy_local import JobSpyLocalScraper
from jobs_applier.scrapers.multi import MultiSourceScraper
from jobs_applier.scrapers.normalizer import normalize_apify_dataset, normalize_apify_item
from jobs_applier.scrapers.remoteok import RemoteOKScraper
from jobs_applier.scrapers.remotive import RemotiveScraper

__all__ = [
    "ApifyJobScraper",
    "JobSpyLocalScraper",
    "MultiSourceScraper",
    "RemoteOKScraper",
    "RemotiveScraper",
    "normalize_apify_dataset",
    "normalize_apify_item",
]
