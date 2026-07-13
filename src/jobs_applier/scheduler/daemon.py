"""Daemon scheduler for continuous pipeline runs."""

from __future__ import annotations

import signal
import sys

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from jobs_applier.config.settings import get_settings
from jobs_applier.logging_config import configure_logging
from jobs_applier.pipeline.runner import PipelineRunner

logger = structlog.get_logger(__name__)


def run_daemon() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_directories()

    runner = PipelineRunner(settings)
    scheduler = BlockingScheduler()

    def pipeline_job() -> None:
        logger.info("daemon_run_start")
        try:
            runner.run()
        except Exception as exc:
            logger.error("daemon_run_failed", error=str(exc))

    scheduler.add_job(
        pipeline_job,
        trigger=IntervalTrigger(minutes=settings.run_interval_minutes),
        id="pipeline",
        name="Jobs Applier Pipeline",
        next_run_time=None,
    )

    def shutdown(signum: int, frame: object) -> None:
        logger.info("daemon_shutdown", signal=signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(
        "daemon_started",
        interval_minutes=settings.run_interval_minutes,
    )
    print(f"Daemon started — running every {settings.run_interval_minutes} minutes.")
    print("Press Ctrl+C to stop.\n")

    pipeline_job()
    scheduler.start()
