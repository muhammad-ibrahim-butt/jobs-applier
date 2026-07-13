"""Browser session management for Playwright."""

from __future__ import annotations

from pathlib import Path

import structlog
from playwright.sync_api import BrowserContext, Playwright, sync_playwright

logger = structlog.get_logger(__name__)


class BrowserSession:
    """Manage persistent Playwright browser context."""

    def __init__(self, user_data_dir: Path, headless: bool = False) -> None:
        self._user_data_dir = user_data_dir
        self._headless = headless
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> BrowserContext:
        self._user_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self._user_data_dir.resolve()),
            headless=self._headless,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            args=["--disable-blink-features=AutomationControlled"],
        )
        logger.info("browser_started", user_data_dir=str(self._user_data_dir))
        return self._context

    def __exit__(self, *args: object) -> None:
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()
        logger.info("browser_stopped")


def is_linkedin_logged_in(context: BrowserContext) -> bool:
    page = context.new_page()
    try:
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        url = page.url
        return "login" not in url and "authwall" not in url
    finally:
        page.close()


def login_linkedin(context: BrowserContext) -> None:
    """Open LinkedIn login page and wait for user to log in manually."""
    page = context.new_page()
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    print("\n>>> Log in to LinkedIn in the browser window.")
    print(">>> Press Enter here once you see your LinkedIn feed...")
    input()
    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    if not is_linkedin_logged_in(context):
        raise RuntimeError("LinkedIn login failed. Please try again.")
    page.close()
    print(">>> LinkedIn session saved successfully.")
