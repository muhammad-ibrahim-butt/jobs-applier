"""YAML configuration and applicant profile loaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SearchConfig(BaseModel):
    queries: list[str] = Field(default_factory=lambda: ["software engineer"])
    location: str = "Remote"
    # Empty / "worldwide" = any country (omit country from Apify for LinkedIn)
    country: str = "worldwide"
    # Prefer linkedin+indeed on free Apify tiers — Glassdoor often 403s and still burns CU.
    platforms: list[str] = Field(default_factory=lambda: ["linkedin", "indeed"])
    max_results: int = Field(default=20, ge=1, le=500)
    # If true, Apify prefers Easy Apply listings. Non-easy-apply matches are still kept
    # and emailed for manual apply when auto-apply adapters cannot handle them.
    easy_apply_only: bool = False
    is_remote: bool = True
    hours_old: int = Field(default=168, ge=1, le=720)
    # Costly on Apify (extra LinkedIn page fetches). Title-only relevance works without it.
    fetch_linkedin_descriptions: bool = False
    # Scrape providers tried in order. fallback = first non-empty wins; merge = combine all.
    sources: list[str] = Field(default_factory=lambda: ["apify", "jobspy", "remotive", "remoteok"])
    source_mode: str = Field(default="fallback")  # fallback | merge


class FilterConfig(BaseModel):
    include_title_keywords: list[str] = Field(default_factory=list)
    exclude_title_keywords: list[str] = Field(default_factory=list)
    exclude_description_keywords: list[str] = Field(default_factory=list)
    exclude_companies: list[str] = Field(default_factory=list)
    remote_only: bool = False
    max_days_old: int = Field(default=7, ge=1, le=90)
    min_salary: int | None = None
    # Resume/skill relevance (0–100). Jobs below this score are dropped.
    min_relevance_score: int = Field(default=0, ge=0, le=100)
    preferred_keywords: list[str] = Field(default_factory=list)
    # Drop jobs with no posted date when true (stricter for "recent only").
    require_posted_date: bool = False
    # Cap how many manual-apply jobs are emailed per run (top by relevance).
    max_email_jobs: int = Field(default=15, ge=1, le=100)


class PlatformsEnabled(BaseModel):
    linkedin: bool = True
    indeed: bool = True
    glassdoor: bool = False


class AppConfig(BaseModel):
    search: SearchConfig = Field(default_factory=SearchConfig)
    filters: FilterConfig = Field(default_factory=FilterConfig)
    platforms_enabled: PlatformsEnabled = Field(default_factory=PlatformsEnabled)


class PersonalInfo(BaseModel):
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str
    city: str = ""
    state: str = ""
    country: str = "United States"
    linkedin_url: str = ""


class WorkInfo(BaseModel):
    years_of_experience: int = 0
    skill_years: dict[str, int] = Field(default_factory=dict)
    work_authorization: str = ""
    requires_sponsorship: bool = False
    notice_period_days: int = 14
    expected_salary: str = ""
    willing_to_relocate: bool = False


class Blocklist(BaseModel):
    companies: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ApplicantProfile(BaseModel):
    personal: PersonalInfo
    work: WorkInfo = Field(default_factory=WorkInfo)
    defaults: dict[str, str] = Field(default_factory=dict)
    blocklist: Blocklist = Field(default_factory=Blocklist)


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_app_config(path: Path) -> AppConfig:
    data = load_yaml_file(path)
    return AppConfig.model_validate(data)


def load_profile(path: Path) -> ApplicantProfile:
    data = load_yaml_file(path)
    return ApplicantProfile.model_validate(data)
