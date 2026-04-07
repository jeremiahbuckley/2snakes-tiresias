"""
APScheduler runner.

Registers all jobs and starts the scheduler process.
Run with: python -m scheduler.runner
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .jobs import (
    detect_and_score_resolutions,
    rebuild_leaderboard,
    sync_all_markets,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        sync_all_markets,
        trigger=IntervalTrigger(minutes=15),
        id="sync_markets",
        name="Sync markets from all connectors",
        max_instances=1,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        detect_and_score_resolutions,
        trigger=IntervalTrigger(minutes=5),
        id="score_resolutions",
        name="Score newly resolved predictions",
        max_instances=1,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        rebuild_leaderboard,
        trigger=IntervalTrigger(hours=1),
        id="rebuild_leaderboard",
        name="Rebuild leaderboard snapshot",
        max_instances=1,
        misfire_grace_time=300,
    )

    return scheduler


async def main() -> None:
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to exit.")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
