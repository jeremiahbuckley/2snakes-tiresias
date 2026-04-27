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
from typing import Optional
from uuid import UUID

from data.database import db_context
from data.crud.market import MarketCRUD
from data.crud.prediction import PredictionCRUD
from data.crud.score import ScoreCRUD
from data.crud.user import UserCRUD
from sqlalchemy import select
from data.models.market import Market, MarketOutcome
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
    4. After all markets in this run are processed, dispatch notifications:
         - one batched "market_resolved" email per user listing every
           market that resolved for them this run;
         - one "badge_earned" email per badge a user earned (payload is
           enriched with the badge name/description from the catalogue).

    The scoring engine and badge service are called with in-memory data derived
    from the DB — no separate HTTP calls to those services.

    Runs every 5 minutes. Idempotent: once a prediction has a brier_score it
    will not be re-scored (resolve_all_for_market skips already-scored rows).
    Notification dedupe is enforced downstream via the email_deliveries
    table, so a re-run that touches the same markets won't re-email.
    """
    from scoring_engine.engine import PredictionRecord, score_user
    from badge_service.issuer import evaluate_badges, diff_badges
    from notification_service.dispatcher import dispatch

    logger.info("detect_and_score_resolutions: starting")
    markets_processed = 0
    users_scored = 0

    # Accumulators: collected across every market processed in this run so
    # we can send one batched email per user at the end.
    resolutions_per_user: dict[UUID, list[dict]] = defaultdict(list)
    badges_granted_per_user: dict[UUID, set[str]] = defaultdict(set)

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

                    # Batch-load tags for all markets in this user's history.
                    _market_ids = {p.market_id for p in all_resolved}
                    _tag_rows = (
                        await db.execute(
                            select(Market.id, Market.tags).where(
                                Market.id.in_(_market_ids)
                            )
                        )
                    ).all()
                    _market_tags: dict[UUID, list[str]] = {
                        row.id: row.tags for row in _tag_rows
                    }

                    pred_records = [
                        PredictionRecord(
                            prediction_id=str(p.id),
                            predicted_probability=float(p.probability),
                            outcome=fresh_market.outcome == MarketOutcome.YES,
                            source=p.source or "unknown",
                            domain=(_market_tags.get(p.market_id) or [None])[0],
                        )
                        for p in all_resolved
                        if p.market_id == fresh_market.id
                    ] + [
                        PredictionRecord(
                            prediction_id=str(p.id),
                            predicted_probability=float(p.probability),
                            outcome=float(p.brier_score) <= 0.25,  # proxy for correct direction
                            source=p.source or "unknown",
                            domain=(_market_tags.get(p.market_id) or [None])[0],
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

                    # Record what to notify about at the end of the run.
                    # Best Brier score across this user's predictions for
                    # this market is what we show in the email — multiple
                    # positions on one market collapse into one line.
                    best_pred = min(
                        (p for p in user_preds if p.brier_score is not None),
                        key=lambda p: float(p.brier_score),
                        default=None,
                    )
                    if best_pred is not None:
                        resolutions_per_user[uid].append(
                            {
                                "market_id": str(fresh_market.id),
                                "market_title": fresh_market.title,
                                "outcome": (
                                    fresh_market.outcome.value
                                    if fresh_market.outcome else None
                                ),
                                "brier_score": float(best_pred.brier_score),
                            }
                        )
                    badges_granted_per_user[uid].update(to_grant)

                markets_processed += 1
                users_scored += len(preds_by_user)

        except Exception as exc:
            logger.error(
                "detect_and_score_resolutions: error processing market %s: %s",
                market.id, exc, exc_info=True
            )

    # -----------------------------------------------------------------
    # Send notifications (one batched email per user per event type).
    # Errors are logged — never fatal to the scheduler loop.
    # -----------------------------------------------------------------
    for uid, resolutions in resolutions_per_user.items():
        try:
            await _notify_market_resolved(uid, resolutions, dispatch)
        except Exception as exc:
            logger.warning(
                "detect_and_score_resolutions: market_resolved dispatch failed user=%s: %s",
                uid, exc,
            )

    for uid, badge_ids in badges_granted_per_user.items():
        for badge_id in sorted(badge_ids):
            try:
                await _notify_badge_earned(uid, badge_id, dispatch)
            except Exception as exc:
                logger.warning(
                    "detect_and_score_resolutions: badge_earned dispatch failed user=%s badge=%s: %s",
                    uid, badge_id, exc,
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
    Recompute the user_scores table for every user from scratch, then
    detect leaderboard-rank milestones crossed since the previous run
    and dispatch rank_change notifications for them.

    The detect_and_score_resolutions job keeps scores up to date incrementally.
    This job provides a safety net that corrects any accumulated drift (e.g. from
    failed increments, schema migrations, or manual DB edits).

    Because it recomputes all stats from raw prediction data it is slower than
    the incremental updates, which is why it runs hourly rather than every 5 min.

    Rank-change notifications
    -------------------------
    We snapshot the pre-rebuild leaderboard, run the rebuild, then compare
    against the post-rebuild leaderboard. A user who was outside a milestone
    band (top 1, top 10, top 100) and is now inside it gets notified.
    Downward transitions are not notified. Notification dedupe
    (email_deliveries) ensures each milestone is only emailed about once
    per user, even across repeated boundary-jittering rebuilds.
    """
    from notification_service.dispatcher import dispatch

    logger.info("rebuild_leaderboard: starting full recompute")

    # Snapshot pre-rebuild ranks (enough entries to cover top 100 + some
    # slack so we can see users near the boundary).
    async with db_context() as db:
        before = await ScoreCRUD.leaderboard(db, skip=0, limit=200)
        users = await UserCRUD.list_active(db)

    before_ranks: dict[UUID, int] = {e.user_id: e.rank for e in before}

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

    # Post-rebuild leaderboard + total eligible user count (for the email
    # body: "Rank 7 out of 500 forecasters").
    async with db_context() as db:
        after = await ScoreCRUD.leaderboard(db, skip=0, limit=200)

    # Total forecasters that qualify for ranking — rough proxy is the size
    # of the full leaderboard result. (If we ever have > 200 eligible users
    # we should swap this for a COUNT query in ScoreCRUD.)
    total_users = len(after)

    notified = 0
    for entry in after:
        previous = before_ranks.get(entry.user_id)
        milestone = _milestone_crossed(previous, entry.rank)
        if milestone is None:
            continue
        try:
            await _notify_rank_change(
                user_id=entry.user_id,
                new_rank=entry.rank,
                previous_rank=previous,
                total_users=total_users,
                milestone=milestone,
                dispatch_fn=dispatch,
            )
            notified += 1
        except Exception as exc:
            logger.warning(
                "rebuild_leaderboard: rank_change dispatch failed for user %s: %s",
                entry.user_id, exc,
            )

    logger.info(
        "rebuild_leaderboard: complete. %d rebuilt, %d errors, %d rank notifications",
        rebuilt, errors, notified,
    )


# ---------------------------------------------------------------------------
# Rank milestone detection
# ---------------------------------------------------------------------------

# Ordered from most-prestigious to least. A user is considered to have
# "crossed into" a band if the new rank is <= threshold and the previous
# rank was > threshold (or they weren't ranked at all). Each milestone is
# emitted at most once per run — see dedupe in notification-service.
_RANK_MILESTONES: tuple[tuple[str, int, str], ...] = (
    ("top1",   1,   "#1 on the leaderboard"),
    ("top10",  10,  "the top 10"),
    ("top100", 100, "the top 100"),
)


def _milestone_crossed(
    previous_rank: Optional[int], new_rank: int
) -> Optional[tuple[str, str]]:
    """
    Return ``(milestone_id, milestone_label)`` for the most prestigious band
    the user just entered, or ``None`` if they didn't cross any band upward.
    """
    for milestone_id, threshold, label in _RANK_MILESTONES:
        entered = new_rank <= threshold and (
            previous_rank is None or previous_rank > threshold
        )
        if entered:
            return milestone_id, label
    return None


# ---------------------------------------------------------------------------
# Notification helpers (non-fatal — log errors rather than propagating)
# ---------------------------------------------------------------------------

async def _notify_market_resolved(uid, resolutions: list[dict], dispatch_fn) -> None:
    """
    Dispatch a single batched market-resolved notification covering every
    market that resolved for this user during the current scheduler run.

    ``resolutions`` is a list of dicts with keys ``market_id``,
    ``market_title``, ``outcome``, ``brier_score`` — matching the shape
    the notification-service template expects.
    """
    from notification_service.dispatcher import Notification, NotificationType

    if not resolutions:
        return

    try:
        await dispatch_fn(
            Notification(
                user_id=str(uid),
                type=NotificationType.MARKET_RESOLVED,
                payload={"resolutions": resolutions},
            )
        )
    except NotImplementedError:
        pass  # handlers incomplete in dev — safe no-op
    except Exception as exc:
        logger.warning("Failed to dispatch market_resolved notification: %s", exc)


async def _notify_badge_earned(uid, badge_id: str, dispatch_fn) -> None:
    """
    Dispatch a badge-earned notification, enriching the payload with
    ``badge_name`` and ``badge_description`` from the badge-service
    catalogue. Unknown badge_ids are skipped with a warning.
    """
    from badge_service.badges import BADGE_INDEX
    from notification_service.dispatcher import Notification, NotificationType

    definition = BADGE_INDEX.get(badge_id)
    if definition is None:
        logger.warning(
            "Badge id %r not found in catalogue; skipping notification",
            badge_id,
        )
        return

    try:
        await dispatch_fn(
            Notification(
                user_id=str(uid),
                type=NotificationType.BADGE_EARNED,
                payload={
                    "badge_id": definition.id,
                    "badge_name": definition.name,
                    "badge_description": definition.description,
                },
            )
        )
    except NotImplementedError:
        pass  # handlers incomplete in dev — safe no-op
    except Exception as exc:
        logger.warning("Failed to dispatch badge_earned notification: %s", exc)


async def _notify_rank_change(
    *,
    user_id: UUID,
    new_rank: int,
    previous_rank: Optional[int],
    total_users: int,
    milestone: tuple[str, str],
    dispatch_fn,
) -> None:
    """
    Dispatch a rank_change notification for a user who just entered a
    leaderboard milestone band (top 1 / top 10 / top 100).
    """
    from notification_service.dispatcher import Notification, NotificationType

    milestone_id, milestone_label = milestone
    try:
        await dispatch_fn(
            Notification(
                user_id=str(user_id),
                type=NotificationType.RANK_CHANGE,
                payload={
                    "new_rank": new_rank,
                    "previous_rank": previous_rank,
                    "total_users": total_users,
                    "milestone": milestone_id,
                    "milestone_label": milestone_label,
                },
            )
        )
    except NotImplementedError:
        pass
    except Exception as exc:
        logger.warning("Failed to dispatch rank_change notification: %s", exc)
