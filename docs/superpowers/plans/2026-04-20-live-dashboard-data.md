# Live Dashboard Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all hardcoded mock data in the three dashboard route loaders with real API calls to the api-gateway, which queries Postgres via a new query layer.

**Architecture:** Three page-scoped endpoints (`/users/{id}/dashboard`, `/predictions`, `/stats`) implemented in a new `data_queries.py` module (pure query functions, no FastAPI) called by thin route handlers. Frontend loaders follow the existing settings page pattern. Mock server updated so contract tests continue passing.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async (asyncpg), SvelteKit `+page.server.js`, Playwright contract tests.

---

## File Map

**New:**
- `services/api-gateway/api_gateway/data_queries.py` — all DB query logic, no FastAPI
- `services/api-gateway/tests/conftest.py` — async DB test fixtures
- `tests/ui-shared/api-mocks/responses/dashboard.json`
- `tests/ui-shared/api-mocks/responses/predictions.json`
- `tests/ui-shared/api-mocks/responses/stats.json`

**Modified:**
- `services/api-gateway/api_gateway/router.py` — replace stubs with real handlers
- `services/api-gateway/api_gateway/app.py` — mount the data router
- `services/api-gateway/tests/test_data_queries.py` — new tests added here
- `apps/user-dashboard/src/lib/api.js` — add `getPredictions`, `getUserStats`
- `apps/user-dashboard/src/routes/dashboard/+page.server.js`
- `apps/user-dashboard/src/routes/predictions/+page.server.js`
- `apps/user-dashboard/src/routes/stats/+page.server.js`
- `tests/ui-shared/mock-api-server.mjs` — add route pattern matching + new routes
- `apps/user-dashboard/tests/contract/dashboard.spec.ts`
- `apps/user-dashboard/tests/contract/predictions.spec.ts`
- `apps/user-dashboard/tests/contract/stats.spec.ts`

---

## Task 1: Gateway computation utilities + tests

Pure Python helpers — no database needed.

**Files:**
- Create: `services/api-gateway/api_gateway/data_queries.py`
- Modify: `services/api-gateway/tests/test_data_queries.py`

- [ ] **Step 1: Write failing tests for pure helpers**

```python
# services/api-gateway/tests/test_data_queries.py
"""Tests for data_queries pure computation helpers."""
import pytest
from api_gateway.data_queries import (
    _infer_outcome,
    _compute_calibration,
    _compute_brier_timeline,
    _compute_per_source,
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /path/to/repo
pytest services/api-gateway/tests/test_data_queries.py -v
```

Expected: `ERROR` — `ImportError: cannot import name '_infer_outcome' from 'api_gateway.data_queries'` (module doesn't exist yet).

- [ ] **Step 3: Create `data_queries.py` with pure helpers only**

```python
# services/api-gateway/api_gateway/data_queries.py
"""
Gateway query layer — DB queries and computation for dashboard endpoints.

All functions are plain Python (no FastAPI concerns). Pure helpers are
synchronous; DB query functions are async.

Future: when data-work endpoint count exceeds ~10, extract this module
and the three route handlers into a standalone data microservice. The
gateway becomes a thin proxy; frontend and mock server are untouched.
"""
from __future__ import annotations

import math
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


def _score_dict(score: Optional[UserScore], per_source: dict) -> dict:
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


def _pred_dict(p: Prediction) -> dict:
    """Serialize a Prediction row (with eagerly-loaded .market) to a response dict."""
    outcome = None
    if p.is_resolved:
        outcome = 'yes' if _infer_outcome(float(p.probability), float(p.brier_score)) == 1 else 'no'
    # Market.question holds the question text; fall back to market_id if missing.
    # NOTE: if the Market model uses a different field name (e.g. 'title'),
    # change 'question' to the correct attribute name here.
    market_title = None
    if p.market is not None:
        market_title = getattr(p.market, 'question', None) or getattr(p.market, 'title', None)
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


# ── DB query functions (placeholders — implemented in Task 2) ────────────────

async def get_dashboard_data(session: AsyncSession, user_id: UUID) -> dict:
    raise NotImplementedError

async def get_predictions(
    session: AsyncSession,
    user_id: UUID,
    source: Optional[str],
    status: Optional[str],
    sort: Optional[str],
) -> dict:
    raise NotImplementedError

async def get_stats_data(session: AsyncSession, user_id: UUID) -> dict:
    raise NotImplementedError
```

- [ ] **Step 4: Run pure-helper tests — they must pass**

```bash
pytest services/api-gateway/tests/test_data_queries.py -v
```

Expected output (all pure-helper tests pass, DB tests skipped/not yet written):
```
test_infer_outcome_yes PASSED
test_infer_outcome_no PASSED
test_infer_outcome_high_prob_yes PASSED
test_infer_outcome_high_prob_no PASSED
test_compute_calibration_empty PASSED
test_compute_calibration_single_yes PASSED
test_compute_calibration_single_no PASSED
test_compute_calibration_bin_predicted_equals_midpoint PASSED
test_compute_brier_timeline_empty PASSED
test_compute_brier_timeline_single_month PASSED
test_compute_brier_timeline_groups_by_month PASSED
test_compute_brier_timeline_ordered_ascending PASSED
test_compute_per_source_empty PASSED
test_compute_per_source_groups_by_source PASSED
14 passed
```

- [ ] **Step 5: Commit**

```bash
git add services/api-gateway/api_gateway/data_queries.py \
        services/api-gateway/tests/test_data_queries.py
git commit -m "feat: add data_queries pure computation helpers with tests"
```

---

## Task 2: Database query functions + tests

Requires a running Postgres database. Run with `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias_test`.

**Files:**
- Create: `services/api-gateway/tests/conftest.py`
- Modify: `services/api-gateway/api_gateway/data_queries.py` (replace NotImplementedError stubs)
- Modify: `services/api-gateway/tests/test_data_queries.py` (add DB tests)

- [ ] **Step 1: Create `conftest.py` with async DB fixtures**

```python
# services/api-gateway/tests/conftest.py
"""Async Postgres fixtures for api-gateway tests."""
import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from data.database import Base

TEST_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias_test",
)


@pytest.fixture(scope="session")
async def _engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="session", autouse=True)
async def _tables(_engine):
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def session(_engine):
    factory = async_sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)
    async with factory() as sess:
        yield sess
        await sess.rollback()
```

- [ ] **Step 2: Write failing DB tests**

Append to `services/api-gateway/tests/test_data_queries.py`:

```python
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


async def _make_market(session, question: str = "Will X happen?") -> Market:
    # NOTE: If Market uses 'title' instead of 'question', change this line.
    m = Market(question=question)
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
    assert result['total'] == 3


async def test_db_predictions_filters_by_source(session):
    user = await _make_user(session)
    market = await _make_market(session)
    await _make_prediction(session, user, market, source='kalshi')
    await _make_prediction(session, user, market, source='manifold')
    await _make_prediction(session, user, market, source='kalshi')
    result = await get_predictions(session, user.id, 'kalshi', None, None)
    assert result['total'] == 2
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
    assert result['total'] == 1
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
    assert result['total'] == 1
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
```

- [ ] **Step 3: Run DB tests to confirm they fail**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias_test \
  pytest services/api-gateway/tests/test_data_queries.py -v -k "db"
```

Expected: all DB tests fail with `NotImplementedError`.

- [ ] **Step 4: Implement the three DB query functions**

Replace the three `NotImplementedError` stubs in `data_queries.py` with:

```python
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
        'score': _score_dict(score, _compute_per_source(resolved)),
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

    count_result = await session.execute(
        select(func.count()).select_from(base.subquery())
    )
    total = count_result.scalar_one()

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

    score_result = await session.execute(select(UserScore).where(UserScore.user_id == user_id))
    score = score_result.scalar_one_or_none()

    return {
        'predictions': [_pred_dict(p) for p in predictions],
        'total': total,
        'totals': {
            'all': score.total_predictions if score else 0,
            'resolved': score.resolved_predictions if score else 0,
            'pending': (score.total_predictions - score.resolved_predictions) if score else 0,
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
```

- [ ] **Step 5: Run all data_queries tests — all must pass**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias_test \
  pytest services/api-gateway/tests/test_data_queries.py -v
```

Expected: all 14 pure-helper tests + all DB tests pass.

- [ ] **Step 6: Commit**

```bash
git add services/api-gateway/api_gateway/data_queries.py \
        services/api-gateway/tests/conftest.py \
        services/api-gateway/tests/test_data_queries.py
git commit -m "feat: implement dashboard DB query functions with tests"
```

---

## Task 3: Gateway route handlers + mount router

**Files:**
- Modify: `services/api-gateway/api_gateway/router.py`
- Modify: `services/api-gateway/api_gateway/app.py`

- [ ] **Step 1: Replace stub handlers in `router.py`**

Overwrite `services/api-gateway/api_gateway/router.py` with:

```python
"""
Top-level data route handlers for the api-gateway.

These handlers own the HTTP layer: auth, ownership checks, and response.
All query logic lives in data_queries.py for easy future extraction to
a dedicated data microservice.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.api import get_current_user
from data.database import get_db
from data.models.user import User

from api_gateway.data_queries import (
    get_dashboard_data,
    get_predictions as _get_predictions,
    get_stats_data,
)

router = APIRouter()

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str) -> dict:
    return {"user_id": user_id, "status": "stub"}


@router.get("/users/{user_id}/dashboard")
async def get_user_dashboard(
    user_id: str,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return await get_dashboard_data(db, current_user.id)


@router.get("/users/{user_id}/predictions")
async def list_user_predictions(
    user_id: str,
    current_user: CurrentUser,
    db: DB,
    source: Optional[str] = None,
    status: Optional[str] = None,
    sort: Optional[str] = None,
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return await _get_predictions(db, current_user.id, source, status, sort)


@router.get("/users/{user_id}/stats")
async def get_user_stats(
    user_id: str,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    if user_id != str(current_user.id):
        raise HTTPException(status_code=403)
    return await get_stats_data(db, current_user.id)


@router.get("/leaderboard")
async def get_leaderboard(limit: int = 100, offset: int = 0) -> dict:
    return {"entries": [], "total": 0, "status": "stub"}


@router.get("/markets")
async def list_markets(source: Optional[str] = None, resolved: Optional[bool] = None) -> dict:
    return {"markets": [], "status": "stub"}
```

- [ ] **Step 2: Mount the data router in `app.py`**

In `services/api-gateway/api_gateway/app.py`, add the data router import and include after the auth router:

```python
def create_app() -> FastAPI:
    app = FastAPI(
        title="Tiresias API",
        description="Prediction market reputation and badging platform.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: restrict to known frontend origins in prod
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from auth_service.api import router as auth_router
    app.include_router(auth_router)

    from api_gateway.router import router as data_router
    app.include_router(data_router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app
```

- [ ] **Step 3: Verify health test still passes**

```bash
pytest services/api-gateway/tests/test_health.py -v
```

Expected:
```
test_health_endpoint PASSED
1 passed
```

- [ ] **Step 4: Commit**

```bash
git add services/api-gateway/api_gateway/router.py \
        services/api-gateway/api_gateway/app.py
git commit -m "feat: wire dashboard route handlers and mount data router in gateway"
```

---

## Task 4: Mock server route matching + response files

The mock server uses exact string matching. The three new routes have a dynamic `:userId` segment — add wildcard pattern matching first, then add the routes.

**Files:**
- Modify: `tests/ui-shared/mock-api-server.mjs`
- Create: `tests/ui-shared/api-mocks/responses/dashboard.json`
- Create: `tests/ui-shared/api-mocks/responses/predictions.json`
- Create: `tests/ui-shared/api-mocks/responses/stats.json`

- [ ] **Step 1: Add route pattern matching to the mock server**

In `tests/ui-shared/mock-api-server.mjs`, replace the `routes[key]` lookup in the request handler with a helper that supports `:param` wildcards:

```javascript
// Add this function before the server creation:
function matchRoute(method, pathname, routes) {
  const exact = routes[`${method} ${pathname}`];
  if (exact !== undefined) return exact;
  for (const [pattern, body] of Object.entries(routes)) {
    const [patMethod, patPath] = pattern.split(' ');
    if (patMethod !== method) continue;
    const regex = new RegExp('^' + patPath.replace(/:[^/]+/g, '[^/]+') + '$');
    if (regex.test(pathname)) return body;
  }
  return undefined;
}
```

Replace the `const body = routes[key];` line in the request handler with:

```javascript
const pathname = new URL(req.url, 'http://x').pathname;
const body = matchRoute(req.method, pathname, routes);
```

Also remove the `new URL(req.url, 'http://x').pathname` call from the `key` computation above (it's now done inside `matchRoute`). The updated request handler should look like:

```javascript
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://x').pathname;
  const key = `${req.method} ${pathname}`;

  if (key === 'GET /') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok' }));
    return;
  }
  if (key === 'HEAD /') {
    res.writeHead(200);
    res.end();
    return;
  }

  const body = matchRoute(req.method, pathname, routes);
  if (body) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(body);
  } else {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ detail: `No mock for ${req.method} ${req.url}` }));
  }
});
```

- [ ] **Step 2: Add the three new routes to the `routes` object**

```javascript
const routes = {
  'POST /auth/login':             readFileSync(join(__dirname, 'api-mocks/responses/auth-login.json'), 'utf8'),
  'GET /auth/me':                 readFileSync(join(__dirname, 'api-mocks/responses/auth-me.json'), 'utf8'),
  'GET /auth/me/linked-accounts': readFileSync(join(__dirname, 'api-mocks/responses/linked-accounts.json'), 'utf8'),
  'GET /auth/me/share-tokens':    readFileSync(join(__dirname, 'api-mocks/responses/share-tokens.json'), 'utf8'),
  'GET /auth/me/notifications':   readFileSync(join(__dirname, 'api-mocks/responses/notifications.json'), 'utf8'),
  'GET /users/:userId/dashboard':    readFileSync(join(__dirname, 'api-mocks/responses/dashboard.json'), 'utf8'),
  'GET /users/:userId/predictions':  readFileSync(join(__dirname, 'api-mocks/responses/predictions.json'), 'utf8'),
  'GET /users/:userId/stats':        readFileSync(join(__dirname, 'api-mocks/responses/stats.json'), 'utf8'),
};
```

- [ ] **Step 3: Create `dashboard.json`**

```json
{
  "user": {
    "id": "usr_abc123",
    "username": "jeremiah_b",
    "display_name": "Jeremiah B.",
    "email": "jeremiahbuckley@2snakes.com",
    "bio": "Forecaster tracking markets across Kalshi, Polymarket, Manifold, and Metaculus.",
    "avatar_url": null,
    "social_links": {}
  },
  "score": {
    "total_predictions": 10,
    "resolved_predictions": 6,
    "mean_brier_score": 0.162,
    "brier_skill_score": 0.352,
    "calibration_score": 0.82,
    "accuracy": 0.67,
    "last_scored_at": "2026-04-01T00:00:00Z",
    "per_source": {
      "kalshi": 0.14,
      "polymarket": 0.18,
      "manifold": 0.21,
      "metaculus": 0.16
    },
    "per_domain": {}
  },
  "badges": [
    {
      "id": "first-prediction",
      "name": "First Prediction",
      "description": "Made your first prediction.",
      "icon": "🎯",
      "earned": true,
      "earned_at": "2025-10-15T00:00:00Z"
    }
  ],
  "recent_predictions": [
    { "id": "p1", "market_id": "m1", "market_title": "Will the Fed cut rates before July 2025?", "source": "kalshi", "probability": 0.72, "outcome": "yes", "is_resolved": true, "brier_score": 0.078, "created_at": "2026-03-01T00:00:00Z", "resolved_at": "2026-03-15T00:00:00Z", "rationale": null, "category": null },
    { "id": "p2", "market_id": "m2", "market_title": "Will BTC reach $100k by end of 2025?", "source": "polymarket", "probability": 0.55, "outcome": "no", "is_resolved": true, "brier_score": 0.302, "created_at": "2026-02-20T00:00:00Z", "resolved_at": "2026-03-01T00:00:00Z", "rationale": null, "category": null },
    { "id": "p3", "market_id": "m3", "market_title": "Will Manifold add new question types in Q1 2026?", "source": "manifold", "probability": 0.40, "outcome": null, "is_resolved": false, "brier_score": null, "created_at": "2026-02-10T00:00:00Z", "resolved_at": null, "rationale": null, "category": null },
    { "id": "p4", "market_id": "m4", "market_title": "Will GPT-5 release before March 2026?", "source": "metaculus", "probability": 0.65, "outcome": "yes", "is_resolved": true, "brier_score": 0.122, "created_at": "2026-01-15T00:00:00Z", "resolved_at": "2026-02-01T00:00:00Z", "rationale": null, "category": null },
    { "id": "p5", "market_id": "m5", "market_title": "Will US unemployment stay below 5% in 2025?", "source": "kalshi", "probability": 0.80, "outcome": null, "is_resolved": false, "brier_score": null, "created_at": "2026-01-01T00:00:00Z", "resolved_at": null, "rationale": null, "category": null }
  ]
}
```

- [ ] **Step 4: Create `predictions.json`**

```json
{
  "predictions": [
    { "id": "p1", "market_id": "m1", "market_title": "Will the Fed cut rates before July 2025?", "source": "kalshi", "probability": 0.72, "outcome": "yes", "is_resolved": true, "brier_score": 0.078, "created_at": "2026-03-01T00:00:00Z", "resolved_at": "2026-03-15T00:00:00Z", "rationale": null, "category": null },
    { "id": "p2", "market_id": "m2", "market_title": "Will BTC reach $100k by end of 2025?", "source": "polymarket", "probability": 0.55, "outcome": "no", "is_resolved": true, "brier_score": 0.302, "created_at": "2026-02-20T00:00:00Z", "resolved_at": "2026-03-01T00:00:00Z", "rationale": null, "category": null },
    { "id": "p3", "market_id": "m3", "market_title": "Will Manifold add new question types in Q1 2026?", "source": "manifold", "probability": 0.40, "outcome": null, "is_resolved": false, "brier_score": null, "created_at": "2026-02-10T00:00:00Z", "resolved_at": null, "rationale": null, "category": null },
    { "id": "p4", "market_id": "m4", "market_title": "Will GPT-5 release before March 2026?", "source": "metaculus", "probability": 0.65, "outcome": "yes", "is_resolved": true, "brier_score": 0.122, "created_at": "2026-01-15T00:00:00Z", "resolved_at": "2026-02-01T00:00:00Z", "rationale": null, "category": null },
    { "id": "p5", "market_id": "m5", "market_title": "Will US unemployment stay below 5% in 2025?", "source": "kalshi", "probability": 0.80, "outcome": null, "is_resolved": false, "brier_score": null, "created_at": "2026-01-01T00:00:00Z", "resolved_at": null, "rationale": null, "category": null }
  ],
  "total": 10,
  "totals": {
    "all": 10,
    "resolved": 6,
    "pending": 4
  }
}
```

- [ ] **Step 5: Create `stats.json`**

```json
{
  "score": {
    "total_predictions": 10,
    "resolved_predictions": 6,
    "mean_brier_score": 0.162,
    "brier_skill_score": 0.352,
    "calibration_score": 0.82,
    "accuracy": 0.67,
    "last_scored_at": "2026-04-01T00:00:00Z",
    "per_source": {
      "kalshi": 0.14,
      "polymarket": 0.18,
      "manifold": 0.21,
      "metaculus": 0.16
    },
    "per_domain": {}
  },
  "calibration": [
    { "bin": 0.05, "predicted": 0.05, "actual": null,  "count": 0 },
    { "bin": 0.15, "predicted": 0.15, "actual": null,  "count": 0 },
    { "bin": 0.25, "predicted": 0.25, "actual": 0.0,   "count": 1 },
    { "bin": 0.35, "predicted": 0.35, "actual": null,  "count": 0 },
    { "bin": 0.45, "predicted": 0.45, "actual": 0.5,   "count": 2 },
    { "bin": 0.55, "predicted": 0.55, "actual": 0.5,   "count": 2 },
    { "bin": 0.65, "predicted": 0.65, "actual": 0.667, "count": 3 },
    { "bin": 0.75, "predicted": 0.75, "actual": 0.75,  "count": 4 },
    { "bin": 0.85, "predicted": 0.85, "actual": 1.0,   "count": 2 },
    { "bin": 0.95, "predicted": 0.95, "actual": 1.0,   "count": 2 }
  ],
  "brier_timeline": [
    { "date": "2025-10", "score": 0.22 },
    { "date": "2025-11", "score": 0.20 },
    { "date": "2025-12", "score": 0.19 },
    { "date": "2026-01", "score": 0.18 },
    { "date": "2026-02", "score": 0.17 },
    { "date": "2026-03", "score": 0.162 }
  ]
}
```

- [ ] **Step 6: Commit**

```bash
git add tests/ui-shared/mock-api-server.mjs \
        tests/ui-shared/api-mocks/responses/dashboard.json \
        tests/ui-shared/api-mocks/responses/predictions.json \
        tests/ui-shared/api-mocks/responses/stats.json
git commit -m "feat: add mock API routes for dashboard, predictions, stats"
```

---

## Task 5: Frontend API client additions

`getDashboard` already exists in `api.js`. Only `getPredictions` and `getUserStats` are new.

**Files:**
- Modify: `apps/user-dashboard/src/lib/api.js`

- [ ] **Step 1: Add `getPredictions` and `getUserStats` to `api.js`**

Insert after the existing `getDashboard` function (after the `// Dashboard` section):

```javascript
// ---------------------------------------------------------------------------
// Predictions  —  GET /users/{user_id}/predictions
// ---------------------------------------------------------------------------

/**
 * Paginated, filtered prediction list.
 * @param {string} userId
 * @param {string} token
 * @param {{ source?: string, status?: string, sort?: string }} [filters]
 */
export async function getPredictions(userId, token, { source = '', status = '', sort = 'date_desc' } = {}) {
  const params = new URLSearchParams();
  if (source && source !== 'all') params.set('source', source);
  if (status && status !== 'all') params.set('status', status);
  if (sort && sort !== 'date_desc') params.set('sort', sort);
  const qs = params.toString();
  return apiFetch(`/users/${userId}/predictions${qs ? '?' + qs : ''}`, { token });
}

// ---------------------------------------------------------------------------
// Stats  —  GET /users/{user_id}/stats
// ---------------------------------------------------------------------------

/** Scores + calibration curve + Brier timeline. */
export async function getUserStats(userId, token) {
  return apiFetch(`/users/${userId}/stats`, { token });
}
```

- [ ] **Step 2: Run svelte-check to confirm no type errors introduced**

```bash
cd apps/user-dashboard && npm run check
```

Expected: `0 errors, 0 warnings`

- [ ] **Step 3: Commit**

```bash
git add apps/user-dashboard/src/lib/api.js
git commit -m "feat: add getPredictions and getUserStats to api client"
```

---

## Task 6: Frontend route loaders

**Files:**
- Modify: `apps/user-dashboard/src/routes/dashboard/+page.server.js`
- Modify: `apps/user-dashboard/src/routes/predictions/+page.server.js`
- Modify: `apps/user-dashboard/src/routes/stats/+page.server.js`

- [ ] **Step 1: Replace `dashboard/+page.server.js`**

```javascript
import { getDashboard } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent }) {
  const { user, token } = await parent();
  const data = await getDashboard(user.id, token);
  return {
    user: data.user,
    score: data.score,
    badges: data.badges,
    recentPredictions: data.recent_predictions,
  };
}
```

- [ ] **Step 2: Replace `predictions/+page.server.js`**

The template reads `data.filters.sourceFilter`, `data.filters.statusFilter`, `data.filters.sortBy` and `data.totals.resolved` etc. — keep these names for backward compatibility.

```javascript
import { getPredictions } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, url }) {
  const { user, token } = await parent();
  const source = url.searchParams.get('source') ?? '';
  const status = url.searchParams.get('status') ?? '';
  const sort   = url.searchParams.get('sort')   ?? 'date_desc';
  const data = await getPredictions(user.id, token, { source, status, sort });
  return {
    predictions: data.predictions,
    totals: data.totals,
    filters: {
      sourceFilter: source || 'all',
      statusFilter: status || 'all',
      sortBy: sort,
    },
  };
}
```

- [ ] **Step 3: Replace `stats/+page.server.js`**

```javascript
import { getUserStats } from '$lib/api.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent }) {
  const { user, token } = await parent();
  const data = await getUserStats(user.id, token);
  return {
    score: data.score,
    calibration: data.calibration,
    brierTimeline: data.brier_timeline,
  };
}
```

- [ ] **Step 4: Run svelte-check — must pass with 0 errors**

```bash
cd apps/user-dashboard && npm run check
```

Expected: `0 errors, 0 warnings`

- [ ] **Step 5: Commit**

```bash
git add apps/user-dashboard/src/routes/dashboard/+page.server.js \
        apps/user-dashboard/src/routes/predictions/+page.server.js \
        apps/user-dashboard/src/routes/stats/+page.server.js
git commit -m "feat: wire dashboard/predictions/stats loaders to live API"
```

---

## Task 7: Contract test updates + full suite run

The existing contract tests were written against the old hardcoded mock data. Update them to match the new mock JSON response shapes, then run the full suite.

**Files:**
- Modify: `apps/user-dashboard/tests/contract/dashboard.spec.ts`
- Modify: `apps/user-dashboard/tests/contract/predictions.spec.ts`
- Modify: `apps/user-dashboard/tests/contract/stats.spec.ts`

- [ ] **Step 1: Update `dashboard.spec.ts`**

The old test checked for `'189'` (old mock's resolved count). New mock has `resolved_predictions: 6` and `mean_brier_score: 0.162`. The recent activity table has 5 rows (matching the 5 entries in dashboard.json).

```typescript
import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('dashboard', () => {
  contractTest('renders heading and welcome message', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Welcome back, Jeremiah B.')).toBeVisible();
  });

  contractTest('shows resolved prediction count from mock data', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    // mock dashboard.json has resolved_predictions: 6
    await expect(page.getByText('6')).toBeVisible();
  });

  contractTest('recent activity table has exactly 5 rows', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('table tbody tr')).toHaveCount(5);
  });

  contractTest('shows earned badge from mock data', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText('First Prediction')).toBeVisible();
  });
});
```

- [ ] **Step 2: Update `predictions.spec.ts`**

Old tests checked for 10/3/6 row counts that matched the old hardcoded mock. New mock returns 5 prediction rows. Filter buttons update the URL but the mock server returns the same data regardless — contract tests verify the URL mechanism, not filtered row counts.

```typescript
import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('predictions', () => {
  contractTest('initial render shows predictions from mock data', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    await expect(page.getByRole('heading', { name: 'Predictions' })).toBeVisible();
    await expect(page.locator('table tbody tr')).toHaveCount(5);
  });

  contractTest('source filter tab updates page URL', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    await page.getByRole('button', { name: 'kalshi' }).click();
    await expect(page).toHaveURL(/source=kalshi/);
  });

  contractTest('status filter tab updates page URL', async ({ authedPage: page }) => {
    await page.goto('/predictions');
    await page.getByRole('button', { name: 'Resolved' }).click();
    await expect(page).toHaveURL(/status=resolved/);
  });

  contractTest('sort — oldest first shows oldest mock prediction first', async ({ authedPage: page }) => {
    await page.goto('/predictions?sort=date_asc');
    await expect(page.locator('table tbody tr').first()).toContainText('US unemployment');
  });
});
```

- [ ] **Step 3: Update `stats.spec.ts`**

Old test checked for `'0.162'` — new mock has the same value. Heading assertions stay the same.

```typescript
import { contractTest, expect } from '../../../../tests/ui-shared/fixtures';

contractTest.describe('stats', () => {
  contractTest('renders heading and Brier score value', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await expect(page.getByRole('heading', { name: 'Stats' })).toBeVisible();
    await expect(page.getByText('0.162')).toBeVisible();
  });

  contractTest('shows calibration chart section', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await expect(page.getByRole('heading', { name: 'Calibration Curve' })).toBeVisible();
  });

  contractTest('shows Brier timeline chart section', async ({ authedPage: page }) => {
    await page.goto('/stats');
    await expect(page.getByRole('heading', { name: 'Brier Score Over Time' })).toBeVisible();
  });
});
```

- [ ] **Step 4: Run svelte-check — must pass**

```bash
cd apps/user-dashboard && npm run check
```

Expected: `0 errors, 0 warnings`

- [ ] **Step 5: Run the full contract test suite**

```bash
cd apps/user-dashboard && npm run test:contract
```

Expected output (all 16+ tests pass):
```
Running 16 tests using 1 worker

  ✓ contract › dashboard › renders heading and welcome message
  ✓ contract › dashboard › shows resolved prediction count from mock data
  ✓ contract › dashboard › recent activity table has exactly 5 rows
  ✓ contract › dashboard › shows earned badge from mock data
  ✓ contract › devBypass banner › shows mock data banner after devBypass login
  ✓ contract › devBypass banner › does not show banner after normal login
  ✓ contract › predictions › initial render shows predictions from mock data
  ✓ contract › predictions › source filter tab updates page URL
  ✓ contract › predictions › status filter tab updates page URL
  ✓ contract › predictions › sort — oldest first shows oldest mock prediction first
  ✓ contract › settings › ...
  ✓ contract › stats › renders heading and Brier score value
  ✓ contract › stats › shows calibration chart section
  ✓ contract › stats › shows Brier timeline chart section

16 passed
```

- [ ] **Step 6: Commit**

```bash
git add apps/user-dashboard/tests/contract/dashboard.spec.ts \
        apps/user-dashboard/tests/contract/predictions.spec.ts \
        apps/user-dashboard/tests/contract/stats.spec.ts
git commit -m "test: update contract specs for live data shapes"
```
