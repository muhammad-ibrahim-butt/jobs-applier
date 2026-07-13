"""Data access layer for jobs and applications."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from jobs_applier.models.job import ApplicationResult, ApplicationStatus, JobListing, JobPlatform
from jobs_applier.storage.models import ApplicationRecord, JobRecord, RunRecord


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def exists(self, fingerprint: str) -> bool:
        return (
            self._session.query(JobRecord).filter(JobRecord.fingerprint == fingerprint).first()
            is not None
        )

    def has_applied(self, fingerprint: str) -> bool:
        record = (
            self._session.query(ApplicationRecord)
            .filter(ApplicationRecord.job_fingerprint == fingerprint)
            .filter(
                ApplicationRecord.status.in_(
                    [
                        ApplicationStatus.APPLIED.value,
                        ApplicationStatus.DRY_RUN.value,
                        ApplicationStatus.EMAILED.value,
                    ]
                )
            )
            .first()
        )
        return record is not None

    def save_job(self, job: JobListing) -> None:
        if self.exists(job.fingerprint):
            return
        record = JobRecord(
            fingerprint=job.fingerprint,
            platform=job.platform.value,
            external_id=job.external_id,
            title=job.title,
            company=job.company,
            location=job.location,
            apply_url=job.apply_url,
            job_url=job.job_url,
            is_easy_apply=job.is_easy_apply,
        )
        self._session.add(record)

    def save_application(self, result: ApplicationResult) -> None:
        existing = (
            self._session.query(ApplicationRecord)
            .filter(ApplicationRecord.job_fingerprint == result.job_fingerprint)
            .first()
        )
        if existing:
            existing.status = result.status.value
            existing.apply_target = result.apply_target.value
            existing.message = result.message
            existing.applied_at = result.applied_at
            return
        self._session.add(
            ApplicationRecord(
                job_fingerprint=result.job_fingerprint,
                status=result.status.value,
                apply_target=result.apply_target.value,
                message=result.message,
                applied_at=result.applied_at,
            )
        )

    def count_applications_today(self) -> int:
        """Count submitted (or dry-run) applications today toward the daily cap."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            self._session.query(ApplicationRecord)
            .filter(ApplicationRecord.applied_at >= today_start)
            .filter(
                ApplicationRecord.status.in_(
                    [
                        ApplicationStatus.APPLIED.value,
                        ApplicationStatus.DRY_RUN.value,
                    ]
                )
            )
            .count()
        )

    def recent_applications(self, limit: int = 20) -> list[ApplicationRecord]:
        return (
            self._session.query(ApplicationRecord)
            .order_by(ApplicationRecord.applied_at.desc())
            .limit(limit)
            .all()
        )

    def recent_failures(self, limit: int = 10) -> list[ApplicationRecord]:
        return (
            self._session.query(ApplicationRecord)
            .filter(ApplicationRecord.status == ApplicationStatus.FAILED.value)
            .order_by(ApplicationRecord.applied_at.desc())
            .limit(limit)
            .all()
        )

    def unapplied_jobs(self, limit: int = 40) -> list[JobListing]:
        """Jobs saved earlier that never reached applied/emailed/dry_run."""
        applied_fps = {
            row[0]
            for row in (
                self._session.query(ApplicationRecord.job_fingerprint)
                .filter(
                    ApplicationRecord.status.in_(
                        [
                            ApplicationStatus.APPLIED.value,
                            ApplicationStatus.DRY_RUN.value,
                            ApplicationStatus.EMAILED.value,
                        ]
                    )
                )
                .all()
            )
        }
        records = (
            self._session.query(JobRecord)
            .order_by(JobRecord.first_seen_at.desc())
            .limit(limit * 3)
            .all()
        )
        out: list[JobListing] = []
        for rec in records:
            if rec.fingerprint in applied_fps:
                continue
            try:
                platform = JobPlatform(rec.platform)
            except ValueError:
                platform = JobPlatform.UNKNOWN
            out.append(
                JobListing(
                    platform=platform,
                    external_id=rec.external_id,
                    title=rec.title,
                    company=rec.company,
                    location=rec.location or "",
                    apply_url=rec.apply_url or "",
                    job_url=rec.job_url or "",
                    is_easy_apply=bool(rec.is_easy_apply),
                )
            )
            if len(out) >= limit:
                break
        return out

    def save_run(self, stats: dict[str, Any]) -> None:
        self._session.add(RunRecord(**stats))

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
