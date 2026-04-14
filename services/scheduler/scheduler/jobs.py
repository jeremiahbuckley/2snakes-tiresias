"""
Job definitions.

Each function here is a scheduled job. Jobs are idempotent — safe to run
multiple times without double-processing.

Job overview
------------
sync_user_predictions(user_id)   On-demand: import one user's full prediction
                                  history from all linked market platforms.

sync_all_markets()               Every 15 min: call sync_user_predictions for
                                  every active user with linked accounts.

detect_and_score_resolutions()   Every 5 min: find markets that resolved on a
                                  platform and have unscored local predictions;
                                  compute Brier scores, update per-user stats,
                                  evaluate badge changes, and send notifications.

rebuild_leaderboard()            Every 1 hr: recompute the full user_scores table
                                  from raw prediction data to correct any drift
                                  introduced by incremental updates.

Dependencies (installed in the container alongside this package):
    data-layer        — database models and CRUD helpers
    connector-*       — platform API clients and adapters (via sync.py)
    scoring-engine    — Brier score and calibration computation
    badge-service     — badge evaluation logic
    notification-service — notification dispatching
"""

from __future__ import annotations

import logging
from collections import defaultdict
from uuid import UUID

from data.database import db_context
from data.crud.market import MarketCRUD
from data.crud.prediction import PredictionCRUD
from data.crud.score import ScoreCRUD
from data.crud.user import UserCRUD
from data.models.market import MarketOutcome
from data.models.prediction import Prediction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job 1 — On-demand: sync one user across all platforms
# ---------------------------------------------------------------------------

async def sync_user_predictions(user_id: str) -> None:
    """
    Pull prediction history for a single user across all linked market platforms
    and upsert into the data layer.

    Triggered when:
    - A user links a new platform account (called by auth-service or API gateway).
    - Manually via an admin endpoint.

    Args:
        user_id: Tiresias internal user UUID as a string.
    """
    from .sync import sync_one_user

    uid = UUID(user_id)
    logger.info("sync_user_predictions: starting for user %s", uid)

    async with db_context() as db:
        total = await sync_one_user(db, uid)

    logger.info("sync_user_predictions: upserted %d predictions for user %s", total, uid)


# ---------------------------------------------------------------------------
# Job 2 — Recurring every 15 min: sync all users
# ---------------------------------------------------------------------------

async def sync_all_markets() -> None:
    """
    Pull fresh market and prediction data from all connectors for every active
    user who has at least one enabled, verified linked market account.

    Each user is processed in its own DB transaction so one user's failure does
    not roll back others' work.

    Runs every 15 minutes. If the previous run is still in progress (e.g. many
    users, slow APIs), APScheduler will skip the overlapping firing thanks to
    max_instances=1 on the job registration.
    """
    from .sync import sync_one_user

    logger.info("sync_all_markets: starting")

    async with db_context() as db:
        users = await UserCRUD.list_active(db)

    user_count = len(users)
    success_count = 0
    total_predictions = 0

    for user in users:
        try:
            async with db_context() as db:
                count = await sync_one_user(db, user.id)
            total_predictions += count
            success_count += 1
        except Exception as exc:
            logger.error(
                "sync_all_markets: unhandled error for user %s: %s",
                user.id, exc, exc_info=True
            )

    logger.info(
        "sync_all_markets: complete. %d/%d users succeeded, %d predictions upserted",
        success_count, user_count, total_predictions,
    )


# ---------------------------------------------------------------------------
# Job 3 — Recurring every 5 min: score resolved predictions
# ---------------------------------------------------------------------------

async def detect_and_score_resolutions() -> None:
    """
    Find markets that have resolved (outcome set via connector sync) but still
    have unscored predictions, then:

    1. Compute Brier scores for each unscored prediction.
    2. Incrementally update each affected user's UserScore row.
    3. Re-evaluate which badges the user qualifies for and persist changes.
    4. Dispatch notifications (market resolved, badge earned).

    The scoring engine and badge service are called with in-memory data derived
    from the DB — no separate HTTP calls to those services.

    Runs every 5 minutes. Idempotent: once a prediction has a brier_score it
    will not be re-scored (resolve_all_for_market skips already-scored rows).
    """
    from scoring_engine.engine import PredictionRecord, score_user
    from badge_service.issuer import evaluate_badges, diff_badges
    from notification_service.dispatcher import (
        Notification,
        NotificationType,
        dispatch,
    )

    logger.info("detect_and_score_resolutions: starting")
    markets_processed = 0
    users_scored = 0

    async with db_context() as db:
        markets = await MarketCRUD.list_resolved_with_unscored_predictions(db)

    for market in markets:
        try:
            async with db_context() as db:
                # Refetch the market inside its own transaction (avoids stale data)
                fresh_market = await MarketCRUD.get(db, market.id)
                if fresh_market is None or not fresh_market.is_resolved:
                    continue
                if fresh_market.outcome == MarketOutcome.AMBIGUOUS:
                    continue

                # Score every unresolved prediction for this market
                scored_preds: list[Prediction] = await PredictionCRUD.resolve_all_for_market(
                    db, fresh_market
                )

                if not scored_preds:
                    continue

                # Group scored predictions by user
                preds_by_user: dict[UUID, list[Prediction]] = defaultdict(list)
                for pred in scored_preds:
                    preds_by_user[pred.user_id].append(pred)

                # Incrementally update each affected user's stats
                for uid, user_preds in preds_by_user.items():
                    new_brier_scores = [
                        float(p.brier_score)
                        for p in user_preds
                        if p.brier_score is not None
                    ]
                    if not new_brier_scores:
                        continue

                    # Update the DB-side score aggregates
                    user_score_row = await ScoreCRUD.increment_for_user(
                        db, uid, new_brier_scores=new_brier_scores
                    )

                    # Build PredictionRecord objects for the scoring engine
                    # (uses all resolved predictions for this user, not just the new ones,
                    # so that badge checks have full context)
                    all_resolved = await PredictionCRUD.list_by_user(
                        db, uid, resolved_only=True, limit=10_000
                    )
                    pred_records = [
                        PredictionRecord(
                            prediction_id=str(p.id),
                            predicted_probability=float(p.probability),
                            outcome=fresh_market.outcome == MarketOutcome.YES,
                            source=p.source or "unknown",
                            domain=None,  # TODO: add domain/category mapping
                        )
                        for p in all_resolved
                        if p.market_id == fresh_market.id  # limit to current market for outcome
                    ] + [
                        PredictionRecord(
                            prediction_id=str(p.id),
                            predicted_probability=float(p.probability),
                            outcome=float(p.brier_score) <= 0.25,  # proxy for correct direction
                            source=p.source or "unknown",
                            domain=None,
                        )
                        for p in all_resolved
                        if p.market_id != fresh_market.id
                    ]

                    # Evaluate scoring-engine result (for badge evaluation)
                    score_result = score_user(str(uid), pred_records)

                    # Evaluate badges
                    earned_ids = evaluate_badges(score_result)
                    current_ids = set(user_score_row.badge_ids or [])
                    to_grant, to_revoke = diff_badges(current_ids, earned_ids)

                    if to_grant or to_revoke:
                        updated_ids = (current_ids | set(to_grant)) - set(to_revoke)
                        user_score_row.badge_ids = sorted(updated_ids)
                        db.add(user_score_row)
                        await db.flush()

                    # Dispatch notifications (non-fatal if notification service is incomplete)
                    await _notify_market_resolved(
                        uid, fresh_market, user_preds, dispatch
                    )
                    for badge_id in to_grant:
                        await _notify_badge_earned(uid, badge_id, dispatch)

                markets_processed += 1
                users_scored += len(preds_by_user)

        except Exception as exc:
            logger.error(
                "detect_and_score_resolutions: error processing market %s: %s",
                market.id, exc, exc_info=True
            )

    logger.info(
        "detect_and_score_resolutions: processed %d markets, scored predictions for %d users",
        markets_processed, users_scored,
    )


# ---------------------------------------------------------------------------
# Job 4 — Recurring every 1 hr: rebuild leaderboard
# ---------------------------------------------------------------------------

async def rebuild_leaderboard() -> None:
    """
    Recompute the user_scores table for every user from scratch.

    The detect_and_score_resolutions job keeps scores up to date incrementally.
    This job provides a safety net that corrects any accumulated drift (e.g. from
    failed increments, schema migrations, or manual DB edits).

    Because it recomputes all stats from raw prediction data it is slower than
    the incremental updates, which is why it runs hourly rather than every 5 min.
    """
    logger.info("rebuild_leaderboard: starting full recompute")

    async with db_context() as db:
        users = await UserCRUD.list_active(db)

    rebuilt = 0
    errors = 0

    for user in users:
        try:
            async with db_context() as db:
                await ScoreCRUD.rebuild_for_user(db, user.id)
            rebuilt += 1
        except Exception as exc:
            logger.error(
                "rebuild_leaderboard: failed for user %s: %s",
                user.id, exc, exc_info=True
            )
            errors += 1

    logger.info(
        "rebuild_leaderboard: complete. %d rebuilt, %d errors", rebuilt, errors
    )


# ---------------------------------------------------------------------------
# Notification helpers (non-fatal — log errors rather than propagating)
# ---------------------------------------------------------------------------

async def _notify_market_resolved(uid, market, scored_preds, dispatch_fn) -> None:
    """Dispatch a market-resolved notification for each scored prediction."""
    from notification_service.dispatcher import Notification, NotificationType

    for pred in scored_preds:
        try:
            await dispatch_fn(
                Notification(
                    user_id=str(uid),
                    type=NotificationType.MARKET_RESOLVED,
                    payload={
                        "market_id": str(market.id),
                        "market_title": market.title,
                        "outcome": market.outcome.value if market.outcome else None,
                        "brier_score": float(pred.brier_score) if pred.brier_score else None,
                    },
                )
            )
        except NotImplementedError:
            pass  # notification handlers are stubs in V1; silently skip
        except Exception as exc:
            logger.warning("Failed to dispatch market_resolved notification: %s", exc)


async def _notify_badge_earned(uid, badge_id: str, dispatch_fn) -> None:
    """Dispatch a badge-earned notification."""
    from notification_service.dispatcher import Notification, NotificationType

    try:
        await dispatch_fn(
            Notification(
                user_id=str(uid),
                type=NotificationType.BADGE_EARNED,
                payload={"badge_id": badge_id},
            )
        )
    except NotImplementedError:
        pass  # notification handlers are stubs in V1; silently skip
    except Exception as exc:
        logger.warning("Failed to dispatch badge_earned notification: %s", exc)
