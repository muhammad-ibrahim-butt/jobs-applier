"""SMTP email notifications."""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

import structlog

from jobs_applier.config.settings import Settings
from jobs_applier.models.job import ApplicationStatus, JobListing, PipelineStats

logger = structlog.get_logger(__name__)


class EmailNotifier:
    """Send one practical run summary (stats + jobs to apply) via SMTP."""

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
        """Send a single email for the run. Skips empty no-op runs."""
        if not self.enabled:
            logger.info("email_disabled")
            return

        interesting = (
            stats.applied
            or stats.emailed
            or stats.failed
            or stats.dry_run
            or stats.manual_jobs
            or stats.cap_reached
        )
        if not interesting:
            logger.info("email_skipped_empty_run")
            return

        if stats.emailed and not stats.applied and not stats.failed:
            subject = f"Jobs Applier: {stats.emailed} jobs need your apply"
        else:
            subject = (
                f"Jobs Applier: {stats.applied} applied, "
                f"{stats.emailed} need your apply, "
                f"{stats.failed} failed"
            )
        self._send(subject, self._build_summary_html(stats))

    def send_manual_apply_digest(self, jobs: list[JobListing]) -> bool:
        """Deprecated path: digests are folded into send_run_summary.

        Kept for callers / tests; returns True if jobs were recorded for summary.
        """
        if not jobs:
            return True
        if not self.enabled:
            logger.warning("manual_digest_skipped_email_disabled", count=len(jobs))
            return False
        # Real email goes out with the run summary so users get one inbox message.
        logger.info("manual_jobs_queued_for_summary", count=len(jobs))
        return True

    def send_test(self) -> bool:
        """Send a short test message to verify SMTP settings."""
        if not self.enabled:
            logger.error("email_disabled")
            return False
        return self._send(
            "Jobs Applier — SMTP test",
            "<p>Your Jobs Applier email configuration works.</p>",
        )

    def _result_label(self, result: object) -> str:
        title = getattr(result, "job_title", "") or ""
        company = getattr(result, "job_company", "") or ""
        if title and company:
            return f"{title} @ {company}"
        if title:
            return title
        return str(getattr(result, "job_fingerprint", ""))

    def _build_summary_html(self, stats: PipelineStats) -> str:
        rows = ""
        for result in stats.results[:30]:
            status_color = {
                ApplicationStatus.APPLIED: "#22c55e",
                ApplicationStatus.FAILED: "#ef4444",
                ApplicationStatus.SKIPPED: "#f59e0b",
                ApplicationStatus.DRY_RUN: "#3b82f6",
                ApplicationStatus.EMAILED: "#8b5cf6",
            }.get(result.status, "#6b7280")
            label = escape(self._result_label(result))
            rows += (
                f"<tr><td>{label}</td>"
                f"<td style='color:{status_color}'>{escape(result.status.value)}</td>"
                f"<td>{escape(result.apply_target.value)}</td>"
                f"<td>{escape(result.message)}</td></tr>"
            )

        manual_html = self._job_cards_html(stats.manual_jobs[:25])
        cap_note = "<p><strong>Daily apply cap reached.</strong></p>" if stats.cap_reached else ""

        return f"""
        <html><body style="font-family: sans-serif; max-width: 760px;">
        <h2>Jobs Applier — What to do next</h2>
        <p>Open the links below and apply. Auto-applied roles are listed in results.</p>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
          <tr><td>Scraped</td><td>{stats.scraped}</td></tr>
          <tr><td>Passed filters</td><td>{stats.filtered}</td></tr>
          <tr><td>Auto-applied</td><td>{stats.applied}</td></tr>
          <tr><td>Need your apply</td><td>{stats.emailed}</td></tr>
          <tr><td>Failed</td><td>{stats.failed}</td></tr>
          <tr><td>Skipped</td><td>{stats.skipped}</td></tr>
          <tr><td>Dry run</td><td>{stats.dry_run}</td></tr>
        </table>
        {cap_note}
        <h3>Apply these yourself</h3>
        {manual_html or "<p>None this run — either auto-applied or nothing matched.</p>"}
        <h3>Application Results</h3>
        <table border="1" cellpadding="6" cellspacing="0"
               style="border-collapse:collapse; width:100%;">
          <tr><th>Job</th><th>Status</th><th>Target</th><th>Message</th></tr>
          {rows or "<tr><td colspan='4'>No applications this run</td></tr>"}
        </table>
        </body></html>
        """

    def _job_cards_html(self, jobs: list[JobListing]) -> str:
        if not jobs:
            return ""
        parts: list[str] = []
        for job in jobs:
            link = job.apply_url or job.job_url or "#"
            salary = ""
            if job.salary_min or job.salary_max:
                lo = job.salary_min or "?"
                hi = job.salary_max or "?"
                curr = escape(job.salary_currency)
                salary = f"<div><strong>Salary:</strong> {lo}-{hi} {curr}</div>"
            target = job.apply_target().value.replace("_", " ")
            desc = (job.description or "").strip()
            if len(desc) > 400:
                desc = desc[:400] + "..."
            loc = escape(job.location or "Remote / not listed")
            desc_html = escape(desc) or "No description scraped — open the link for details."
            parts.append(
                f"""
                <div style="border:1px solid #e5e7eb;padding:14px;
                     margin:12px 0;border-radius:8px;">
                  <h3 style="margin:0 0 8px;">{escape(job.title)}</h3>
                  <div><strong>Company:</strong> {escape(job.company)}</div>
                  <div><strong>Location:</strong> {loc}</div>
                  <div><strong>Found on:</strong> {escape(job.platform.value)}</div>
                  <div><strong>Apply path:</strong> {escape(target)}</div>
                  {salary}
                  <div style="margin:10px 0;">
                    <a href="{escape(link)}" style="background:#111827;color:#fff;
                    padding:8px 14px;text-decoration:none;border-radius:6px;">
                    Open &amp; apply</a>
                  </div>
                  <div style="color:#4b5563;font-size:13px;">{desc_html}</div>
                  <div style="margin-top:8px;font-size:12px;color:#6b7280;">
                    Link: <a href="{escape(link)}">{escape(link)}</a>
                  </div>
                </div>
                """
            )
        return "\n".join(parts)

    def _send(self, subject: str, html_body: str) -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._settings.smtp_user
        msg["To"] = self._settings.notify_email
        msg.attach(MIMEText(html_body, "html"))

        host = self._settings.smtp_host
        port = self._settings.smtp_port
        user = self._settings.smtp_user
        password = self._settings.smtp_password

        try:
            if port == 465 or self._settings.resolve_smtp_use_ssl():
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(host, port, context=context, timeout=45) as server:
                    server.login(user, password)
                    server.sendmail(user, self._settings.notify_email, msg.as_string())
            else:
                with smtplib.SMTP(host, port, timeout=45) as server:
                    server.ehlo()
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    server.login(user, password)
                    server.sendmail(user, self._settings.notify_email, msg.as_string())
            logger.info("email_sent", to=self._settings.notify_email, subject=subject)
            return True
        except Exception as exc:
            logger.error("email_send_failed", error=str(exc), host=host, port=port)
            return False
