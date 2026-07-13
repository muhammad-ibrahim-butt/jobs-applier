"""YAML configuration and applicant profile loaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SearchConfig(BaseModel):
    queries: list[str] = Field(default_factory=lambda: ["software engineer"])
    location: str = "Remote"
    country: str = "USA"
    platforms: list[str] = Field(default_factory=lambda: ["linkedin", "indeed", "glassdoor"])
    max_results: int = Field(default=50, ge=1, le=500)
    easy_apply_only: bool = True
    hours_old: int = Field(default=168, ge=1, le=720)


class FilterConfig(BaseModel):
    include_title_keywords: list[str] = Field(default_factory=list)
    exclude_title_keywords: list[str] = Field(default_factory=list)
    exclude_description_keywords: list[str] = Field(default_factory=list)
    exclude_companies: list[str] = Field(default_factory=list)
    remote_only: bool = False
    max_days_old: int = Field(default=7, ge=1, le=90)
    min_salary: int | None = None


class PlatformsEnabled(BaseModel):
    linkedin: bool = True
    indeed: bool = True
    glassdoor: bool = True


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
