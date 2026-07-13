"""Apply adapters for job platforms."""

from jobs_applier.apply.browser import BrowserSession, is_linkedin_logged_in, login_linkedin
from jobs_applier.apply.form_filler import FormFiller
from jobs_applier.apply.greenhouse import GreenhouseAdapter
from jobs_applier.apply.lever import LeverAdapter
from jobs_applier.apply.linkedin import LinkedInEasyApplyAdapter
from jobs_applier.apply.router import ApplyRouter

__all__ = [
    "ApplyRouter",
    "BrowserSession",
    "FormFiller",
    "GreenhouseAdapter",
    "LeverAdapter",
    "LinkedInEasyApplyAdapter",
    "is_linkedin_logged_in",
    "login_linkedin",
]
