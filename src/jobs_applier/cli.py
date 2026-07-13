"""Typer CLI for jobs-applier."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from jobs_applier.apply.browser import BrowserSession, is_linkedin_logged_in, login_linkedin
from jobs_applier.config.settings import get_settings
from jobs_applier.logging_config import configure_logging
from jobs_applier.models.job import PipelineStats
from jobs_applier.notifications.email import EmailNotifier
from jobs_applier.pipeline.runner import PipelineRunner
from jobs_applier.scheduler.daemon import run_daemon
from jobs_applier.storage.db import init_db
from jobs_applier.storage.repositories import JobRepository

app = typer.Typer(
    name="jobs-applier",
    help="Local job scraper and auto-applier powered by Apify and Playwright.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def init() -> None:
    """Initialize project directories and copy example config files."""
    from jobs_applier.templates import TEMPLATE_MAP, find_template

    settings = get_settings()
    settings.ensure_directories()

    for dst_name in TEMPLATE_MAP:
        dst = Path(dst_name)
        if dst.exists():
            console.print(f"[yellow]Already exists[/yellow] {dst}")
            continue
        src = find_template(dst_name)
        if src is None:
            console.print(f"[red]Missing template for[/red] {dst_name}")
            continue
        shutil.copy(src, dst)
        console.print(f"[green]Created[/green] {dst}")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("1. Edit .env with your APIFY_API_TOKEN (SMTP optional)")
    console.print("2. Edit profile.yaml with your applicant details")
    console.print("3. Place your resume at the path set in RESUME_PATH")
    console.print("4. Run: [cyan]jobs-applier login linkedin[/cyan]")
    console.print("5. Run: [cyan]jobs-applier test-email[/cyan] (if email enabled)")
    console.print("6. Run: [cyan]jobs-applier run --dry-run[/cyan]")


@app.command()
def login(
    platform: str = typer.Argument("linkedin", help="Platform to log in to"),
) -> None:
    """Open browser for interactive login (saves session)."""
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_directories()

    if platform.lower() != "linkedin":
        console.print(f"[red]Unsupported platform:[/red] {platform}")
        raise typer.Exit(1)

    with BrowserSession(settings.browser_user_data_dir, headless=False) as context:
        if is_linkedin_logged_in(context):
            console.print("[green]Already logged in to LinkedIn.[/green]")
            return
        login_linkedin(context)


@app.command()
def scrape() -> None:
    """Scrape jobs only (no apply)."""
    settings = get_settings()
    configure_logging(settings.log_level)

    try:
        runner = PipelineRunner(settings)
        stats = runner.scrape_only()
        console.print(f"\n[bold]Scraped:[/bold] {stats.scraped} jobs")
        console.print(f"[bold]Passed filters:[/bold] {stats.filtered} jobs")
    except FileNotFoundError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


@app.command()
def run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Fill forms but do not submit"),
) -> None:
    """Run the full pipeline: scrape, filter, apply, notify."""
    settings = get_settings()
    configure_logging(settings.log_level)

    try:
        runner = PipelineRunner(settings)
        stats = runner.run(dry_run=dry_run)
        _print_stats(stats)
        if stats.scraped == 0 and stats.filtered == 0 and stats.emailed == 0:
            console.print(
                "[yellow]No new jobs. If Apify quota is exhausted, wait for reset "
                "or process backlog after the next successful scrape.[/yellow]"
            )
    except FileNotFoundError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[red]Pipeline error:[/red] {exc}")
        raise typer.Exit(1) from exc


@app.command()
def daemon() -> None:
    """Run pipeline on a schedule while this process is alive."""
    run_daemon()


@app.command("test-email")
def test_email() -> None:
    """Send a test email using SMTP settings from .env."""
    settings = get_settings()
    configure_logging(settings.log_level)
    notifier = EmailNotifier(settings)
    if not notifier.enabled:
        console.print("[red]Email not configured.[/red] Set EMAIL_ENABLED=true and SMTP_* in .env")
        raise typer.Exit(1)
    console.print(
        f"Sending test email via {settings.smtp_host}:{settings.smtp_port} "
        f"({'SSL' if settings.resolve_smtp_use_ssl() else 'STARTTLS'}) "
        f"to {settings.notify_email}..."
    )
    ok = notifier.send_test()
    if ok:
        console.print("[green]Test email sent. Check your inbox (and spam).[/green]")
    else:
        console.print("[red]Test email failed. Check logs and SMTP credentials.[/red]")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show today's apply count and recent application history."""
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_directories()

    session_factory = init_db(settings.database_path)
    session = session_factory()
    try:
        repo = JobRepository(session)
        today_count = repo.count_applications_today()
        remaining = max(0, settings.daily_apply_cap - today_count)

        console.print(
            f"\n[bold]Today's applications:[/bold] {today_count} / {settings.daily_apply_cap}"
        )
        console.print(f"[bold]Remaining cap:[/bold] {remaining}\n")

        table = Table(title="Recent Applications")
        table.add_column("Job", style="cyan")
        table.add_column("Status")
        table.add_column("Target")
        table.add_column("Message")
        table.add_column("When")

        for app_record in repo.recent_applications(15):
            status_style = {
                "applied": "green",
                "failed": "red",
                "skipped": "yellow",
                "dry_run": "blue",
                "emailed": "magenta",
            }.get(app_record.status, "white")
            table.add_row(
                app_record.job_fingerprint[:40],
                f"[{status_style}]{app_record.status}[/{status_style}]",
                app_record.apply_target,
                app_record.message[:50],
                app_record.applied_at.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)
    finally:
        session.close()


def _print_stats(stats: PipelineStats) -> None:
    console.print("\n[bold green]Pipeline complete[/bold green]")
    console.print(f"  Scraped:  {stats.scraped}")
    console.print(f"  Filtered: {stats.filtered}")
    console.print(f"  Applied:  {stats.applied}")
    console.print(f"  Emailed:  {stats.emailed}")
    console.print(f"  Failed:   {stats.failed}")
    console.print(f"  Skipped:  {stats.skipped}")
    if stats.dry_run:
        console.print(f"  Dry run:  {stats.dry_run}")
    if stats.cap_reached:
        console.print("[yellow]  Daily apply cap reached[/yellow]")
