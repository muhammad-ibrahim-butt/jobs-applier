"""Application settings loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings from .env file and environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Apify
    apify_api_token: str = ""
    apify_actor_id: str = "openclawai/job-board-scraper"

    # Search defaults (config.yaml takes precedence when loaded)
    search_queries: str = "software engineer"
    search_location: str = "Remote"
    search_country: str = "USA"

    # Apply limits
    daily_apply_cap: int = Field(default=25, ge=1, le=500)
    run_interval_minutes: int = Field(default=120, ge=15, le=1440)
    dry_run: bool = False

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_email: str = ""
    email_enabled: bool = False
    # Auto True when port is 465; override with SMTP_USE_SSL=true/false
    smtp_use_ssl: bool | None = None

    @field_validator("smtp_password", mode="before")
    @classmethod
    def strip_password_quotes(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value

    # Paths
    profile_path: Path = Path("./profile.yaml")
    config_path: Path = Path("./config.yaml")
    resume_path: Path = Path("./resume.pdf")
    database_path: Path = Path("./data/applications.db")
    browser_user_data_dir: Path = Path("./sessions/chromium")
    questions_cache_path: Path = Path("./data/questions.json")

    # Logging
    log_level: str = "INFO"

    @field_validator("search_queries", mode="before")
    @classmethod
    def parse_queries(cls, value: str | list[str]) -> str:
        if isinstance(value, list):
            return ",".join(value)
        return str(value)

    def search_query_list(self) -> list[str]:
        return [q.strip() for q in self.search_queries.split(",") if q.strip()]

    def ensure_directories(self) -> None:
        """Create required data directories."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.browser_user_data_dir.mkdir(parents=True, exist_ok=True)
        self.questions_cache_path.parent.mkdir(parents=True, exist_ok=True)

    def resolve_smtp_use_ssl(self) -> bool:
        if self.smtp_use_ssl is not None:
            return self.smtp_use_ssl
        return self.smtp_port == 465


def get_settings() -> Settings:
    return Settings()
