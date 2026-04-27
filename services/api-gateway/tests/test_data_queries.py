"""Tests for data_queries pure computation helpers."""
import pytest
from api_gateway.data_queries import (
    _infer_outcome,
    _compute_calibration,
    _compute_brier_timeline,
    _compute_per_source,
    _compute_score_from_predictions,
)
from datetime import datetime, timezone


# ── _infer_outcome ──────────────────────────────────────────────────────────

def test_infer_outcome_yes():
    # prob=0.3, outcome=YES: brier = (0.3 - 1)^2 = 0.49
    assert _infer_outcome(0.3, 0.49) == 1

def test_infer_outcome_no():
    # prob=0.3, outcome=NO: brier = (0.3 - 0)^2 = 0.09
    assert _infer_outcome(0.3, 0.09) == 0

def test_infer_outcome_high_prob_yes():
    # prob=0.9, outcome=YES: brier = (0.9 - 1)^2 = 0.01
    assert _infer_outcome(0.9, 0.01) == 1

def test_infer_outcome_high_prob_no():
    # prob=0.9, outcome=NO: brier = (0.9 - 0)^2 = 0.81
    assert _infer_outcome(0.9, 0.81) == 0


# ── _compute_calibration ────────────────────────────────────────────────────

class _FakePred:
    def __init__(self, probability, brier_score):
        self.probability = probability
        self.brier_score = brier_score
        self.is_resolved = True
        self.source = 'kalshi'
        self.resolved_at = datetime(2026, 1, 15, tzinfo=timezone.utc)


def test_compute_calibration_empty():
    result = _compute_calibration([])
    assert len(result) == 10
    assert all(b['count'] == 0 for b in result)
    assert all(b['actual'] is None for b in result)
    # bins are 0.05, 0.15, ..., 0.95
    assert [b['bin'] for b in result] == [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]

def test_compute_calibration_single_yes():
    # prob=0.7, outcome=YES: brier = (0.7 - 1)^2 = 0.09
    # bin index = int(0.7 * 10) = 7 → midpoint 0.75
    pred = _FakePred(0.7, 0.09)
    result = _compute_calibration([pred])
    bin_7 = result[7]
    assert bin_7['count'] == 1
    assert bin_7['actual'] == 1.0

def test_compute_calibration_single_no():
    # prob=0.3, outcome=NO: brier = (0.3)^2 = 0.09
    # bin index = int(0.3 * 10) = 3 → midpoint 0.35
    pred = _FakePred(0.3, 0.09)
    result = _compute_calibration([pred])
    bin_3 = result[3]
    assert bin_3['count'] == 1
    assert bin_3['actual'] == 0.0

def test_compute_calibration_bin_predicted_equals_midpoint():
    pred = _FakePred(0.5, 0.25)  # prob=0.5, outcome=NO: (0.5)^2=0.25
    result = _compute_calibration([pred])
    for b in result:
        assert b['predicted'] == b['bin']


# ── _compute_brier_timeline ─────────────────────────────────────────────────

def test_compute_brier_timeline_empty():
    assert _compute_brier_timeline([]) == []

def test_compute_brier_timeline_single_month():
    pred = _FakePred(0.7, 0.09)
    result = _compute_brier_timeline([pred])
    assert result == [{'date': '2026-01', 'score': 0.09}]

def test_compute_brier_timeline_groups_by_month():
    p1 = _FakePred(0.7, 0.10)
    p1.resolved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    p2 = _FakePred(0.8, 0.20)
    p2.resolved_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
    p3 = _FakePred(0.6, 0.30)
    p3.resolved_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    result = _compute_brier_timeline([p1, p2, p3])
    assert len(result) == 2
    assert result[0]['date'] == '2026-01'
    assert abs(result[0]['score'] - 0.15) < 0.001  # mean(0.10, 0.20)
    assert result[1] == {'date': '2026-02', 'score': 0.3}

def test_compute_brier_timeline_ordered_ascending():
    p_feb = _FakePred(0.5, 0.25)
    p_feb.resolved_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    p_jan = _FakePred(0.5, 0.25)
    p_jan.resolved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = _compute_brier_timeline([p_feb, p_jan])
    assert result[0]['date'] == '2026-01'
    assert result[1]['date'] == '2026-02'


# ── _compute_per_source ─────────────────────────────────────────────────────

def test_compute_per_source_empty():
    assert _compute_per_source([]) == {}

def test_compute_per_source_groups_by_source():
    p1 = _FakePred(0.7, 0.10)
    p1.source = 'kalshi'
    p2 = _FakePred(0.6, 0.20)
    p2.source = 'kalshi'
    p3 = _FakePred(0.5, 0.30)
    p3.source = 'manifold'
    result = _compute_per_source([p1, p2, p3])
    assert abs(result['kalshi'] - 0.15) < 0.001  # mean(0.10, 0.20)
    assert result['manifold'] == 0.3


# ── _compute_score_from_predictions ─────────────────────────────────────────

def test_compute_score_from_predictions_empty():
    result = _compute_score_from_predictions([])
    assert result['total_predictions'] == 0
    assert result['resolved_predictions'] == 0
    assert result['mean_brier_score'] is None
    assert result['brier_skill_score'] is None
    assert result['accuracy'] is None


def test_compute_score_from_predictions_with_resolved():
    p1 = _FakePred(0.8, 0.04)   # brier=0.04 ≤ 0.25 → accurate
    p2 = _FakePred(0.3, 0.09)   # brier=0.09 ≤ 0.25 → accurate
    p3 = _FakePred(0.5, 0.25)   # brier=0.25 ≤ 0.25 → accurate
    result = _compute_score_from_predictions([p1, p2, p3])
    assert result['total_predictions'] == 3
    assert result['resolved_predictions'] == 3
    expected_mean = round((0.04 + 0.09 + 0.25) / 3, 4)
    assert abs(result['mean_brier_score'] - expected_mean) < 0.0001
    expected_bss = round((0.25 - expected_mean) / 0.25, 4)
    assert abs(result['brier_skill_score'] - expected_bss) < 0.0001
    assert result['accuracy'] == 1.0  # all three ≤ 0.25


def test_compute_score_from_predictions_mixed_pending():
    import types
    pending = types.SimpleNamespace(brier_score=None, source='kalshi',
                                    probability=0.6, is_resolved=False, resolved_at=None)
    resolved = _FakePred(0.7, 0.09)
    result = _compute_score_from_predictions([pending, resolved])
    assert result['total_predictions'] == 2
    assert result['resolved_predictions'] == 1
    assert result['mean_brier_score'] == 0.09


def test_compute_score_from_predictions_calibration_score_is_none():
    result = _compute_score_from_predictions([_FakePred(0.7, 0.09)])
    assert result['calibration_score'] is None


# ── DB query function tests ───────────────────────────────────────────────────
# Run: DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias_test
#      pytest services/api-gateway/tests/test_data_queries.py -v -k "db"

import uuid
from datetime import datetime, timezone
from sqlalchemy import select

from data.models.market import Market
from data.models.prediction import Prediction
from data.models.score import UserScore
from data.models.user import User
from api_gateway.data_queries import get_dashboard_data, get_predictions, get_stats_data
from api_gateway.data_queries import _user_tags


# ── helpers ──────────────────────────────────────────────────────────────────

async def _make_user(session) -> User:
    user = User(
        email=f"test-{uuid.uuid4().hex}@example.com",
        username=f"u{uuid.uuid4().hex[:8]}",
        hashed_password="$2b$12$fakehash",
    )
    session.add(user)
    await session.flush()
    return user


async def _make_market(session, question: str = "Will X happen?", tags: list[str] | None = None) -> Market:
    # Market uses 'title' instead of 'question'
    m = Market(title=question, tags=tags or [])
    session.add(m)
    await session.flush()
    return m


async def _make_prediction(
    session,
    user: User,
    market: Market,
    probability: float = 0.7,
    source: str = "kalshi",
    brier_score: float | None = None,
    resolved_at: datetime | None = None,
) -> Prediction:
    p = Prediction(
        user_id=user.id,
        market_id=market.id,
        probability=probability,
        source=source,
        brier_score=brier_score,
        resolved_at=resolved_at,
    )
    session.add(p)
    await session.flush()
    return p


async def _make_score(session, user: User, **kwargs) -> UserScore:
    defaults = {
        'total_predictions': 0,
        'resolved_predictions': 0,
        'badge_ids': [],
    }
    defaults.update(kwargs)
    s = UserScore(user_id=user.id, **defaults)
    session.add(s)
    await session.flush()
    return s


# ── get_dashboard_data ────────────────────────────────────────────────────────

async def test_db_dashboard_no_score_returns_zeroed(session):
    user = await _make_user(session)
    result = await get_dashboard_data(session, user.id)
    assert result['score']['total_predictions'] == 0
    assert result['score']['mean_brier_score'] is None
    assert result['badges'] == []
    assert result['recent_predictions'] == []
    assert result['user']['id'] == str(user.id)


async def test_db_dashboard_returns_score_fields(session):
    user = await _make_user(session)
    await _make_score(
        session, user,
        total_predictions=10,
        resolved_predictions=6,
        mean_brier_score=0.18,
        badge_ids=['first-prediction'],
    )
    result = await get_dashboard_data(session, user.id)
    assert result['score']['total_predictions'] == 10
    assert result['score']['resolved_predictions'] == 6
    assert abs(result['score']['mean_brier_score'] - 0.18) < 0.001


async def test_db_dashboard_returns_up_to_5_recent_predictions(session):
    user = await _make_user(session)
    market = await _make_market(session)
    for i in range(7):
        await _make_prediction(
            session, user, market,
            source='kalshi',
            resolved_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc) if i < 4 else None,
            brier_score=0.1 if i < 4 else None,
        )
    result = await get_dashboard_data(session, user.id)
    assert len(result['recent_predictions']) == 5


async def test_db_dashboard_badges_resolved_from_catalog(session):
    user = await _make_user(session)
    await _make_score(
        session, user,
        total_predictions=5,
        resolved_predictions=3,
        badge_ids=['first-prediction', 'above-baseline'],
    )
    result = await get_dashboard_data(session, user.id)
    badge_ids = [b['id'] for b in result['badges']]
    assert 'first-prediction' in badge_ids
    assert 'above-baseline' in badge_ids
    assert all(b['earned'] is True for b in result['badges'])


# ── get_predictions ───────────────────────────────────────────────────────────

async def test_db_predictions_returns_all_when_no_filter(session):
    user = await _make_user(session)
    market = await _make_market(session)
    for _ in range(3):
        await _make_prediction(session, user, market)
    result = await get_predictions(session, user.id, None, None, None)
    assert len(result['predictions']) == 3


async def test_db_predictions_filters_by_source(session):
    user = await _make_user(session)
    market = await _make_market(session)
    await _make_prediction(session, user, market, source='kalshi')
    await _make_prediction(session, user, market, source='manifold')
    await _make_prediction(session, user, market, source='kalshi')
    result = await get_predictions(session, user.id, 'kalshi', None, None)
    assert all(p['source'] == 'kalshi' for p in result['predictions'])


async def test_db_predictions_filters_resolved(session):
    user = await _make_user(session)
    market = await _make_market(session)
    await _make_prediction(
        session, user, market, brier_score=0.09,
        resolved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    await _make_prediction(session, user, market)  # pending
    result = await get_predictions(session, user.id, None, 'resolved', None)
    assert result['predictions'][0]['is_resolved'] is True


async def test_db_predictions_filters_pending(session):
    user = await _make_user(session)
    market = await _make_market(session)
    await _make_prediction(
        session, user, market, brier_score=0.09,
        resolved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    await _make_prediction(session, user, market)  # pending
    result = await get_predictions(session, user.id, None, 'pending', None)
    assert result['predictions'][0]['is_resolved'] is False


async def test_db_predictions_sorts_by_brier_asc(session):
    user = await _make_user(session)
    market = await _make_market(session)
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await _make_prediction(session, user, market, brier_score=0.20, resolved_at=t)
    await _make_prediction(session, user, market, brier_score=0.05, resolved_at=t)
    result = await get_predictions(session, user.id, None, None, 'brier_asc')
    scores = [p['brier_score'] for p in result['predictions'] if p['brier_score'] is not None]
    assert scores == sorted(scores)


async def test_db_predictions_includes_totals(session):
    user = await _make_user(session)
    await _make_score(
        session, user, total_predictions=10, resolved_predictions=6
    )
    market = await _make_market(session)
    await _make_prediction(session, user, market)
    result = await get_predictions(session, user.id, None, None, None)
    assert result['totals']['all'] == 10
    assert result['totals']['resolved'] == 6
    assert result['totals']['pending'] == 4


async def test_db_predictions_filters_by_tag(session):
    user = await _make_user(session)
    m_politics = await _make_market(session, tags=['politics'])
    m_crypto   = await _make_market(session, tags=['crypto'])
    await _make_prediction(session, user, m_politics, source='kalshi')
    await _make_prediction(session, user, m_crypto,   source='manifold')
    result = await get_predictions(session, user.id, None, None, None, tag='politics')
    assert len(result['predictions']) == 1
    assert result['predictions'][0]['source'] == 'kalshi'


async def test_db_predictions_tag_filter_returns_correct_totals(session):
    user = await _make_user(session)
    m_politics = await _make_market(session, tags=['politics'])
    m_crypto   = await _make_market(session, tags=['crypto'])
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await _make_prediction(session, user, m_politics, brier_score=0.1, resolved_at=t)
    await _make_prediction(session, user, m_politics)   # pending
    await _make_prediction(session, user, m_crypto, brier_score=0.2, resolved_at=t)
    result = await get_predictions(session, user.id, None, None, None, tag='politics')
    assert result['totals']['all'] == 2
    assert result['totals']['resolved'] == 1
    assert result['totals']['pending'] == 1


async def test_db_predictions_includes_available_tags(session):
    user = await _make_user(session)
    m = await _make_market(session, tags=['politics', 'us'])
    await _make_prediction(session, user, m)
    result = await get_predictions(session, user.id, None, None, None)
    assert 'available_tags' in result
    assert 'politics' in result['available_tags']
    assert 'us' in result['available_tags']


async def test_db_predictions_unknown_tag_returns_empty(session):
    user = await _make_user(session)
    m = await _make_market(session, tags=['politics'])
    await _make_prediction(session, user, m)
    result = await get_predictions(session, user.id, None, None, None, tag='nonexistent')
    assert result['predictions'] == []
    assert result['totals']['all'] == 0


# ── get_stats_data ────────────────────────────────────────────────────────────

async def test_db_stats_no_predictions_returns_empty_charts(session):
    user = await _make_user(session)
    result = await get_stats_data(session, user.id)
    assert result['calibration'] == [
        {'bin': round(i * 0.1 + 0.05, 2), 'predicted': round(i * 0.1 + 0.05, 2), 'actual': None, 'count': 0}
        for i in range(10)
    ]
    assert result['brier_timeline'] == []


async def test_db_stats_returns_score_and_charts(session):
    user = await _make_user(session)
    await _make_score(
        session, user, total_predictions=5, resolved_predictions=3, mean_brier_score=0.15
    )
    market = await _make_market(session)
    t = datetime(2026, 3, 1, tzinfo=timezone.utc)
    # prob=0.8, outcome=YES: brier=(0.8-1)^2=0.04
    await _make_prediction(session, user, market, probability=0.8, brier_score=0.04, resolved_at=t)
    result = await get_stats_data(session, user.id)
    assert result['score']['total_predictions'] == 5
    assert len(result['calibration']) == 10
    assert result['brier_timeline'] == [{'date': '2026-03', 'score': 0.04}]


# ── _user_tags ────────────────────────────────────────────────────────────────

async def test_db_user_tags_returns_sorted_distinct_tags(session):
    user = await _make_user(session)
    m1 = await _make_market(session, tags=['politics', 'us'])
    m2 = await _make_market(session, tags=['crypto', 'politics'])  # 'politics' appears twice
    await _make_prediction(session, user, m1)
    await _make_prediction(session, user, m2)
    result = await _user_tags(user.id, session)
    assert result == ['crypto', 'politics', 'us']  # sorted, no duplicates


async def test_db_user_tags_excludes_other_users(session):
    user1 = await _make_user(session)
    user2 = await _make_user(session)
    m = await _make_market(session, tags=['sports'])
    await _make_prediction(session, user2, m)
    result = await _user_tags(user1.id, session)
    assert result == []


async def test_db_user_tags_empty_when_no_predictions(session):
    user = await _make_user(session)
    result = await _user_tags(user.id, session)
    assert result == []
