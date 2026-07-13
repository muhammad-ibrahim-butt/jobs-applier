"""Shared form-filling utilities for browser automation."""

from __future__ import annotations

import random
import time
from pathlib import Path

import structlog
from playwright.sync_api import Locator, Page

from jobs_applier.profile.qa_cache import QuestionCache

logger = structlog.get_logger(__name__)


def human_delay(min_ms: int = 300, max_ms: int = 900) -> None:
    time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


def human_type(locator: Locator, text: str) -> None:
    locator.click()
    locator.fill("")
    for char in text:
        locator.type(char, delay=random.randint(30, 80))


class FormFiller:
    """Fill common form fields using profile and Q&A cache."""

    def __init__(self, page: Page, qa_cache: QuestionCache, resume_path: Path) -> None:
        self._page = page
        self._qa = qa_cache
        self._resume_path = resume_path

    def fill_text_inputs(self) -> list[str]:
        """Fill visible text inputs. Returns list of unanswered labels."""
        unanswered: list[str] = []
        inputs = self._page.locator(
            "input[type='text'], input[type='email'], input[type='tel'], "
            "input[type='number'], input:not([type]), textarea"
        ).all()

        for inp in inputs:
            if not inp.is_visible():
                continue
            try:
                if inp.input_value():
                    continue
            except Exception:
                continue

            label = self._find_label(inp)
            answer = self._qa.resolve_from_profile(label) if label else None
            if answer:
                human_type(inp, answer)
                human_delay()
            elif label and inp.get_attribute("required") is not None:
                unanswered.append(label)

        return unanswered

    def fill_selects(self) -> None:
        selects = self._page.locator("select").all()
        for sel in selects:
            if not sel.is_visible():
                continue
            label = self._find_label(sel)
            answer = self._qa.resolve_from_profile(label) if label else None
            if answer:
                try:
                    sel.select_option(label=answer)
                except Exception:
                    try:
                        sel.select_option(value=answer)
                    except Exception:
                        logger.debug("select_fill_failed", label=label)

    def fill_radios(self) -> None:
        """Select radio buttons based on cached answers."""
        fieldsets = self._page.locator("fieldset, div[role='radiogroup']").all()
        for fieldset in fieldsets:
            if not fieldset.is_visible():
                continue
            label = fieldset.get_attribute("aria-label") or fieldset.inner_text()[:100]
            answer = self._qa.resolve_from_profile(label)
            if answer:
                try:
                    fieldset.get_by_text(answer, exact=False).first.click()
                    human_delay()
                except Exception:
                    logger.debug("radio_fill_failed", label=label)

    def upload_resume(self) -> bool:
        if not self._resume_path.exists():
            logger.warning("resume_not_found", path=str(self._resume_path))
            return False
        # File inputs are often hidden; try every input[type=file] on the page.
        file_inputs = self._page.locator("input[type='file']").all()
        for fi in file_inputs:
            try:
                fi.set_input_files(str(self._resume_path.resolve()))
                human_delay(500, 1200)
                return True
            except Exception:
                continue
        return False

    def _find_label(self, element: Locator) -> str:
        elem_id = element.get_attribute("id")
        if elem_id:
            label_el = self._page.locator(f"label[for='{elem_id}']")
            if label_el.count():
                return label_el.first.inner_text().strip()

        aria = element.get_attribute("aria-label")
        if aria:
            return aria.strip()

        placeholder = element.get_attribute("placeholder")
        if placeholder:
            return placeholder.strip()

        name = element.get_attribute("name")
        return name or "unknown field"

    def fill_all(self) -> list[str]:
        self.fill_text_inputs()
        self.fill_selects()
        self.fill_radios()
        self.upload_resume()
        return self.fill_text_inputs()
