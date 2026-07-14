"""Status / run persistence checks."""

from pathlib import Path

from jobs_applier.models.job import ApplicationResult, ApplicationStatus, ApplyTarget, JobListing, JobPlatform
from jobs_applier.storage.db import init_db
from jobs_applier.storage.repositories import JobRepository


def test_status_counts_and_run_notes(tmp_path: Path) -> None:
    db = tmp_path / "status.db"
    session_factory = init_db(db)
    session = session_factory()
    repo = JobRepository(session)

    job = JobListing(
        platform=JobPlatform.LINKEDIN,
        external_id="1",
        title="Backend Engineer",
        company="Acme",
        apply_url="https://linkedin.com/jobs/view/1",
        job_url="https://linkedin.com/jobs/view/1",
        is_easy_apply=True,
    )
    repo.save_job(job)
    repo.save_application(
        ApplicationResult(
            job_fingerprint=job.fingerprint,
            status=ApplicationStatus.EMAILED,
            apply_target=ApplyTarget.UNSUPPORTED,
            message="manual",
            job_title=job.title,
            job_company=job.company,
        )
    )
    repo.save_run(
        {
            "scraped": 10,
            "filtered": 3,
            "applied": 0,
            "skipped": 1,
            "failed": 0,
            "emailed": 2,
            "notes": "hit=jobspy",
        }
    )
    repo.commit()

    assert repo.count_jobs() == 1
    assert repo.counts_today_by_status().get("emailed") == 1
    last = repo.last_run()
    assert last is not None
    assert last.emailed == 2
    assert last.notes == "hit=jobspy"

    rows = repo.recent_applications_with_jobs(5)
    assert len(rows) == 1
    app, joined = rows[0]
    assert app.status == "emailed"
    assert joined is not None
    assert joined.title == "Backend Engineer"
    session.close()
