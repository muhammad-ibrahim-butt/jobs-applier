"""SMTP email notifications."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from jobs_applier.config.settings import Settings
from jobs_applier.models.job import ApplicationStatus, PipelineStats

logger = structlog.get_logger(__name__)


class EmailNotifier:
    """Send pipeline summary emails via SMTP."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(
            self._settings.email_enabled
            and self._settings.smtp_user
            and self._settings.smtp_password
            and self._settings.notify_email
        )

    def send_run_summary(self, stats: PipelineStats) -> None:
        if not self.enabled:
            logger.info("email_disabled")
            return

        subject = (
            f"Jobs Applier: {stats.applied} applied, {stats.failed} failed, {stats.skipped} skipped"
        )
        html = self._build_html(stats)
        self._send(subject, html)

    def _build_html(self, stats: PipelineStats) -> str:
        rows = ""
        for result in stats.results[:20]:
            status_color = {
                ApplicationStatus.APPLIED: "#22c55e",
                ApplicationStatus.FAILED: "#ef4444",
                ApplicationStatus.SKIPPED: "#f59e0b",
                ApplicationStatus.DRY_RUN: "#3b82f6",
            }.get(result.status, "#6b7280")
            rows += (
                f"<tr><td>{result.job_fingerprint}</td>"
                f"<td style='color:{status_color}'>{result.status.value}</td>"
                f"<td>{result.apply_target.value}</td>"
                f"<td>{result.message}</td></tr>"
            )

        new_jobs_html = ""
        for job in stats.new_jobs[:10]:
            link = job.job_url or job.apply_url or "#"
            new_jobs_html += (
                f"<li><strong>{job.title}</strong> at {job.company} "
                f"({job.platform.value}) — "
                f"<a href='{link}'>View</a></li>"
            )

        cap_note = "<p><strong>Daily apply cap reached.</strong></p>" if stats.cap_reached else ""

        return f"""
        <html><body style="font-family: sans-serif; max-width: 700px;">
        <h2>Jobs Applier — Run Summary</h2>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
          <tr><td>Scraped</td><td>{stats.scraped}</td></tr>
          <tr><td>Passed filters</td><td>{stats.filtered}</td></tr>
          <tr><td>Applied</td><td>{stats.applied}</td></tr>
          <tr><td>Failed</td><td>{stats.failed}</td></tr>
          <tr><td>Skipped</td><td>{stats.skipped}</td></tr>
          <tr><td>Dry run</td><td>{stats.dry_run}</td></tr>
        </table>
        {cap_note}
        <h3>New Matches</h3>
        <ul>{new_jobs_html or "<li>None</li>"}</ul>
        <h3>Application Results</h3>
        <table border="1" cellpadding="6" cellspacing="0"
               style="border-collapse:collapse; width:100%;">
          <tr><th>Job</th><th>Status</th><th>Target</th><th>Message</th></tr>
          {rows or "<tr><td colspan='4'>No applications this run</td></tr>"}
        </table>
        </body></html>
        """

    def _send(self, subject: str, html_body: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._settings.smtp_user
        msg["To"] = self._settings.notify_email
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as server:
                server.starttls()
                server.login(self._settings.smtp_user, self._settings.smtp_password)
                server.sendmail(
                    self._settings.smtp_user,
                    self._settings.notify_email,
                    msg.as_string(),
                )
            logger.info("email_sent", to=self._settings.notify_email)
        except Exception as exc:
            logger.error("email_send_failed", error=str(exc))
