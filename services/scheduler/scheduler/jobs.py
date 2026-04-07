"""
Job definitions.

Each function here is a scheduled job. Jobs should be idempotent —
safe to run multiple times without double-processing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def sync_all_markets() -> None:
    """
    Pull fresh market data from all connectors and upsert into the data layer.
    Runs every 15 minutes.
    """
    logger.info("Starting market sync across all connectors")
    # TODO: import and call each connector's sync_markets()
    # TODO: upsert results via data layer CRUD
    raise NotImplementedError


async def detect_and_score_resolutions() -> None:
    """
    Find markets that resolved since the last run, compute scores for all
    affected users, and trigger badge re-evaluation.
    Runs every 5 minutes.
    """
    logger.info("Checking for newly resolved markets")
    # TODO: query data layer for unscored resolved markets
    # TODO: call scoring_engine.score_user() for each affected user
    # TODO: call badge_service.issuer.evaluate_badges() and persist changes
    # TODO: dispatch notifications for resolved markets and new badges
    raise NotImplementedError


async def rebuild_leaderboard() -> None:
    """
    Recompute the public leaderboard snapshot from current user scores.
    Runs every hour.
    """
    logger.info("Rebuilding leaderboard snapshot")
    # TODO: aggregate user scores, rank, and write to leaderboard cache/table
    raise NotImplementedError


async def sync_user_predictions(user_id: str) -> None:
    """
    On-demand job: pull prediction history for a single user across all
    linked platforms and upsert into the data layer.
    Triggered when a user links a new account.
    """
    logger.info(f"Syncing predictions for user {user_id}")
    # TODO: fetch linked accounts from auth-service
    # TODO: call each connector's sync_user_predictions()
    raise NotImplementedError
