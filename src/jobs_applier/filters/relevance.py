"""Rank jobs by fit to the applicant profile / preferred skills."""

from __future__ import annotations

from jobs_applier.config.profile import ApplicantProfile
from jobs_applier.models.job import JobListing

# Default skill terms derived from a typical senior backend/fullstack + AI resume.
_DEFAULT_PREFERRED = (
    "python",
    "laravel",
    "php",
    "django",
    "flask",
    "node",
    "typescript",
    "react",
    "next.js",
    "vue",
    "c#",
    ".net",
    "aws",
    "docker",
    "kubernetes",
    "postgresql",
    "mysql",
    "redis",
    "rest",
    "api",
    "langchain",
    "llm",
    "rag",
    "automation",
    "backend",
    "full-stack",
    "fullstack",
    "fastapi",
)


class RelevanceScorer:
    """Score 0–100 based on skill overlap with title + description."""

    def __init__(
        self,
        profile: ApplicantProfile,
        preferred_keywords: list[str] | None = None,
    ) -> None:
        skills = [s.lower() for s in profile.work.skill_years]
        preferred = [k.lower() for k in (preferred_keywords or list(_DEFAULT_PREFERRED))]
        # Profile skills weigh more (x2 when matching).
        self._terms: list[tuple[str, int]] = [(s, 2) for s in skills]
        for kw in preferred:
            if kw not in skills:
                self._terms.append((kw, 1))

    def score(self, job: JobListing) -> int:
        title = job.title.lower()
        description = job.description.lower()
        if not title.strip() and not description.strip():
            return 0

        # LinkedIn cards often ship with empty descriptions unless fetch is enabled.
        # Don't dilute title skill hits across the full preferred-keyword vocabulary.
        if not description.strip():
            hit_weight = sum(weight for term, weight in self._terms if term in title)
            # Profile skill weight 2 → 26 (≥ default min_relevance_score 25).
            return min(100, hit_weight * 13)

        blob = f"{title}\n{description}"
        points = 0
        max_points = 0
        for term, weight in self._terms:
            max_points += weight * 3
            if term in blob:
                # Title hits are stronger than description-only.
                points += weight * (3 if term in title else 2)

        if max_points == 0:
            return 0
        return min(100, int(round(100 * points / max_points)))
