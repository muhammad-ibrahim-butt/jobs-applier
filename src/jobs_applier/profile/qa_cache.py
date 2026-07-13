"""Persist answers to recurring application questions."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from jobs_applier.config.profile import ApplicantProfile

logger = structlog.get_logger(__name__)


class QuestionCache:
    """Cache for form question answers."""

    def __init__(self, cache_path: Path, profile: ApplicantProfile) -> None:
        self._path = cache_path
        self._profile = profile
        self._cache: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with self._path.open(encoding="utf-8") as f:
                self._cache = json.load(f)
        else:
            self._cache = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2)

    def _normalize_key(self, label: str) -> str:
        return " ".join(label.lower().strip().split())

    def get_answer(self, label: str) -> str | None:
        key = self._normalize_key(label)
        if key in self._cache:
            return self._cache[key]
        for pattern, answer in self._profile.defaults.items():
            if pattern.lower() in key:
                return answer
        return None

    def set_answer(self, label: str, answer: str) -> None:
        key = self._normalize_key(label)
        self._cache[key] = answer
        self.save()
        logger.info("cached_answer", question=key)

    def resolve_from_profile(self, label: str) -> str | None:
        key = self._normalize_key(label)
        personal = self._profile.personal
        work = self._profile.work

        field_map: dict[str, str] = {
            "first name": personal.first_name,
            "last name": personal.last_name,
            "full name": personal.full_name,
            "email": personal.email,
            "phone": personal.phone,
            "city": personal.city,
            "linkedin": personal.linkedin_url,
            "years of experience": str(work.years_of_experience),
            "salary": work.expected_salary,
            "authorization": work.work_authorization,
            "sponsorship": "Yes" if work.requires_sponsorship else "No",
        }

        for pattern, value in field_map.items():
            if pattern in key and value:
                return value

        return self.get_answer(label)
