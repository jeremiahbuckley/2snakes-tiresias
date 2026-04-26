"""
Gateway query layer — DB queries and computation for dashboard endpoints.

All functions are plain Python (no FastAPI concerns). Pure helpers are
synchronous; DB query functions are async.

Future: when data-work endpoint count exceeds ~10, extract this module
and the three route handlers into a standalone data microservice. The
gateway becomes a thin proxy; frontend and mock server are untouched.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from data.models.market import Market
from data.models.prediction import Prediction
from data.models.score import UserScore
from data.models.user import User

BADGE_CATALOG: dict[str, dict] = {
    'first-prediction': {
        'name': 'First Prediction',
        'description': 'Made your first prediction.',
        'icon': '🎯',
    },
    'above-baseline': {
        'name': 'Above Baseline',
        'description': 'Mean Brier score below 0.25.',
        'icon': '📈',
    },
}


# ── Pure helpers ─────────────────────────────────────────────────────────────

def _infer_outcome(probability: float, brier_score: float) -> int:
    """Return 1 (YES) or 0 (NO) by recovering the binary outcome from brier_score."""
    return 1 if abs((probability - 1.0) ** 2 - brier_score) < abs(probability ** 2 - brier_score) else 0


def _compute_per_source(resolved_predictions: list) -> dict:
    """Mean resolved Brier score grouped by platform source."""
    source_scores: dict[str, list[float]] = defaultdict(list)
    for p in resolved_predictions:
        if p.source:
            source_scores[p.source].append(float(p.brier_score))
    return {
        src: round(sum(scores) / len(scores), 4)
        for src, scores in source_scores.items()
    }


def _compute_calibration(resolved_predictions: list) -> list[dict]:
    """10-bin calibration curve from resolved predictions.

    Future: precompute and cache in user_scores JSONB when query latency
    becomes noticeable.
    """
    bins: dict[int, list[int]] = defaultdict(list)
    for p in resolved_predictions:
        prob = float(p.probability)
        brier = float(p.brier_score)
        bin_idx = min(int(prob * 10), 9)
        bins[bin_idx].append(_infer_outcome(prob, brier))
    result = []
    for i in range(10):
        midpoint = round(i * 0.1 + 0.05, 2)
        outcomes = bins[i]
        result.append({
            'bin': midpoint,
            'predicted': midpoint,
            'actual': round(sum(outcomes) / len(outcomes), 4) if outcomes else None,
            'count': len(outcomes),
        })
    return result


def _compute_brier_timeline(resolved_predictions: list) -> list[dict]:
    """Monthly mean Brier score, ordered ascending by month.

    Future: precompute and cache in user_scores JSONB when query latency
    becomes noticeable.
    """
    monthly: dict[str, list[float]] = defaultdict(list)
    for p in resolved_predictions:
        if p.resolved_at is not None:
            monthly[p.resolved_at.strftime('%Y-%m')].append(float(p.brier_score))
    return [
        {'date': m, 'score': round(sum(s) / len(s), 4)}
        for m, s in sorted(monthly.items())
    ]


def _score_dict(score: Optional[object], per_source: dict) -> dict:
    """Serialize a UserScore row (or None) to a response-ready dict."""
    if score is None:
        return {
            'total_predictions': 0,
            'resolved_predictions': 0,
            'mean_brier_score': None,
            'brier_skill_score': None,
            'calibration_score': None,
            'accuracy': None,
            'last_scored_at': None,
            'per_source': per_source,
            'per_domain': {},
        }
    mean_brier = float(score.mean_brier_score) if score.mean_brier_score is not None else None
    # BSS = (uninformed_score - mean_brier) / uninformed_score
    # Uninformed baseline for binary forecasting = 0.25
    bss = round((0.25 - mean_brier) / 0.25, 4) if mean_brier is not None else None
    return {
        'total_predictions': score.total_predictions,
        'resolved_predictions': score.resolved_predictions,
        'mean_brier_score': mean_brier,
        'brier_skill_score': bss,
        'calibration_score': float(score.calibration_score) if score.calibration_score is not None else None,
        'accuracy': float(score.accuracy) if score.accuracy is not None else None,
        'last_scored_at': score.last_scored_at.isoformat() if score.last_scored_at else None,
        'per_source': per_source,
        'per_domain': {},  # domain taxonomy not yet stored in DB
    }


def _pred_dict(p: object) -> dict:
    """Serialize a Prediction row (with eagerly-loaded .market) to a response dict."""
    outcome = None
    if p.is_resolved:
        outcome = 'yes' if _infer_outcome(float(p.probability), float(p.brier_score)) == 1 else 'no'
    market_title = None
    if p.market is not None:
        market_title = p.market.title
    return {
        'id': str(p.id),
        'market_id': str(p.market_id),
        'market_title': market_title or str(p.market_id),
        'source': p.source,
        'probability': float(p.probability),
        'outcome': outcome,
        'is_resolved': p.is_resolved,
        'brier_score': float(p.brier_score) if p.brier_score is not None else None,
        'rationale': p.rationale,
        'category': None,  # category not stored on Prediction; add when Market gains tags
        'created_at': p.created_at.isoformat(),
        'resolved_at': p.resolved_at.isoformat() if p.resolved_at else None,
    }


# ── DB query functions ───────────────────────────────────────────────────────

async def get_dashboard_data(session: AsyncSession, user_id: UUID) -> dict:
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    score_result = await session.execute(select(UserScore).where(UserScore.user_id == user_id))
    score = score_result.scalar_one_or_none()

    recent_result = await session.execute(
        select(Prediction)
        .where(Prediction.user_id == user_id)
        .options(selectinload(Prediction.market))
        .order_by(Prediction.created_at.desc())
        .limit(5)
    )
    recent = recent_result.scalars().all()

    resolved_result = await session.execute(
        select(Prediction)
        .where(Prediction.user_id == user_id, Prediction.brier_score.is_not(None))
    )
    resolved = resolved_result.scalars().all()

    # Count total predictions directly — UserScore.total_predictions only updates
    # after market resolutions, so it reads 0 for users with only pending predictions.
    total_pred_result = await session.execute(
        select(func.count(Prediction.id)).where(Prediction.user_id == user_id)
    )
    total_pred_count = total_pred_result.scalar_one()

    badge_ids = (score.badge_ids or []) if score else []
    badges = [
        {
            **BADGE_CATALOG[b],
            'id': b,
            'earned': True,
            'earned_at': score.last_scored_at.isoformat() if score and score.last_scored_at else None,
        }
        for b in badge_ids
        if b in BADGE_CATALOG
    ]

    score_data = _score_dict(score, _compute_per_source(resolved))
    score_data['total_predictions'] = total_pred_count

    return {
        'user': {
            'id': str(user.id),
            'username': user.username,
            'display_name': user.display_name,
            'email': user.email,
            'bio': user.bio,
            'avatar_url': user.avatar_url,
            'social_links': user.social_links or {},
        },
        'score': score_data,
        'badges': badges,
        'recent_predictions': [_pred_dict(p) for p in recent],
    }


async def get_predictions(
    session: AsyncSession,
    user_id: UUID,
    source: Optional[str],
    status: Optional[str],
    sort: Optional[str],
) -> dict:
    base = select(Prediction).where(Prediction.user_id == user_id)

    if source and source != 'all':
        base = base.where(Prediction.source == source)
    if status == 'resolved':
        base = base.where(Prediction.brier_score.is_not(None))
    elif status == 'pending':
        base = base.where(Prediction.brier_score.is_(None))

    if sort in ('brier_asc', 'brier_score'):
        base = base.order_by(Prediction.brier_score.asc().nulls_last())
    elif sort == 'brier_desc':
        base = base.order_by(Prediction.brier_score.desc().nulls_last())
    elif sort == 'date_asc':
        base = base.order_by(Prediction.created_at.asc())
    else:
        base = base.order_by(Prediction.created_at.desc())

    paged = base.limit(50).options(selectinload(Prediction.market))
    pred_result = await session.execute(paged)
    predictions = pred_result.scalars().all()

    # Count totals directly from prediction rows — UserScore.total_predictions is only
    # updated by the scoring engine (requires market resolutions), so it reads 0 for
    # new users with pending predictions.
    total_all_result = await session.execute(
        select(func.count(Prediction.id)).where(Prediction.user_id == user_id)
    )
    total_all = total_all_result.scalar_one()

    total_resolved_result = await session.execute(
        select(func.count(Prediction.id)).where(
            Prediction.user_id == user_id,
            Prediction.brier_score.is_not(None),
        )
    )
    total_resolved = total_resolved_result.scalar_one()

    return {
        'predictions': [_pred_dict(p) for p in predictions],
        'totals': {
            'all': total_all,
            'resolved': total_resolved,
            'pending': total_all - total_resolved,
        },
    }


async def get_stats_data(session: AsyncSession, user_id: UUID) -> dict:
    score_result = await session.execute(select(UserScore).where(UserScore.user_id == user_id))
    score = score_result.scalar_one_or_none()

    resolved_result = await session.execute(
        select(Prediction)
        .where(Prediction.user_id == user_id, Prediction.brier_score.is_not(None))
    )
    resolved = resolved_result.scalars().all()

    return {
        'score': _score_dict(score, _compute_per_source(resolved)),
        'calibration': _compute_calibration(resolved),
        'brier_timeline': _compute_brier_timeline(resolved),
    }
