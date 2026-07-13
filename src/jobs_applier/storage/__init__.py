"""Persistence layer."""

from jobs_applier.storage.db import init_db
from jobs_applier.storage.repositories import JobRepository

__all__ = ["JobRepository", "init_db"]
