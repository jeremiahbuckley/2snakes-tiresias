# Market Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store raw topic tags on Market rows, feed them into the scoring engine's per-domain Brier scores, and enable tag-based market filtering.

**Architecture:** Replace the unused `category: String(128)` column on `markets` with `tags: ARRAY(Text)` (GIN-indexed). Connector adapters already return `tags` lists for Manifold and Metaculus; the Kalshi adapter needs a one-line addition. `MarketCRUD.upsert_from_sync` stores them. `jobs.py` batch-loads tags and populates `PredictionRecord.domain` from the first tag.

**Tech Stack:** SQLAlchemy 2.0 async, PostgreSQL ARRAY + GIN index, Alembic, pytest-asyncio

---

## File Map

| File | Change |
|------|--------|
| `services/data-layer/alembic/versions/0006_market_tags.py` | Create — migration |
| `services/data-layer/data/models/market.py` | Modify — replace `category` with `tags` |
| `services/data-layer/data/schemas/market.py` | Modify — replace `category` with `tags` in all three schemas |
| `services/data-layer/data/crud/market.py` | Modify — `upsert_from_sync` stores tags; `list_open` filters by tag |
| `services/connector-kalshi/connector_kalshi/adapter.py` | Modify — add `tags` from `raw.get("category")` |
| `services/connector-kalshi/tests/test_adapter.py` | Modify — add two tag tests |
| `services/scheduler/scheduler/jobs.py` | Modify — batch-load market tags, populate domain |
| `tests/integration/test_data_layer.py` | Modify — remove `category="weather"` from `test_create_market` |

---

## Task 1: Alembic migration — drop `category`, add `tags`

**Files:**
- Create: `services/data-layer/alembic/versions/0006_market_tags.py`

### Background

`category` has never been populated from sync — every synced market has `NULL` there. It is safe to drop. The new `tags ARRAY(TEXT) NOT NULL DEFAULT '{}'` column gets a GIN index so `WHERE 'politics' = ANY(tags)` uses an index scan rather than a sequential scan.

---

- [ ] **Step 1: Write the migration file**

Create `services/data-layer/alembic/versions/0006_market_tags.py`:

```python
"""Market tags — replace category with tags ARRAY

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-27

Drops the unused ``category`` column (never populated from sync) and adds
``tags TEXT[] NOT NULL DEFAULT '{}'`` with a GIN index for fast containment
queries (``WHERE 'politics' = ANY(tags)``).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("markets", "category")
    op.add_column(
        "markets",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index(
        "ix_markets_tags",
        "markets",
        ["tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_markets_tags", table_name="markets")
    op.drop_column("markets", "tags")
    op.add_column(
        "markets",
        sa.Column("category", sa.String(128), nullable=True),
    )
```

- [ ] **Step 2: Apply the migration**

```bash
cd services/data-layer && alembic upgrade head
```

Expected:
```
INFO  [alembic.runtime.migration] Running upgrade 0005 -> 0006, Market tags ...
```

- [ ] **Step 3: Verify the schema**

```bash
cd services/data-layer && python -c "
import asyncio, os
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text, inspect
async def check():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.connect() as conn:
        result = await conn.execute(text(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='markets' ORDER BY ordinal_position\"))
        for row in result:
            print(row)
asyncio.run(check())
"
```

Expected output includes `tags | ARRAY` and does NOT include `category`.

- [ ] **Step 4: Commit**

```bash
git add services/data-layer/alembic/versions/0006_market_tags.py
git commit -m "feat: migration 0006 — replace category with tags ARRAY on markets"
```

---

## Task 2: Update Market model and Pydantic schemas

**Files:**
- Modify: `services/data-layer/data/models/market.py`
- Modify: `services/data-layer/data/schemas/market.py`
- Modify: `tests/integration/test_data_layer.py:160`

---

- [ ] **Step 1: Update the Market ORM model**

In `services/data-layer/data/models/market.py`:

Add to the imports block:
```python
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
```

Replace:
```python
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
```

With:
```python
    tags: Mapped[list[str]] = mapped_column(
        PG_ARRAY(Text()),
        nullable=False,
        default=list,
        server_default="{}",
    )
```

Remove `String` from the `sqlalchemy` import if it's no longer used elsewhere in the file (check — `String` is also used for `source`, `external_id`, `title`, `source_url`, and `category` in `__table_args__`). Since `category` is gone, verify `String` is still needed for the other columns — it is (`source: String(32)`, `external_id: String(512)`, etc.). Keep the `String` import.

- [ ] **Step 2: Update the Pydantic schemas**

Replace the entire contents of `services/data-layer/data/schemas/market.py` with:

```python
"""
Pydantic schemas for Market.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from data.models.market import MarketOutcome


# ---------------------------------------------------------------------------
# Write schemas
# ---------------------------------------------------------------------------

class MarketCreate(BaseModel):
    title: str = Field(..., min_length=10, max_length=512)
    description: Optional[str] = Field(None, max_length=10_000)
    resolution_criteria: Optional[str] = Field(None, max_length=5_000)
    tags: list[str] = Field(default_factory=list)
    source_url: Optional[str] = Field(None, max_length=2048)
    closes_at: Optional[datetime] = None
    resolves_at: Optional[datetime] = None

    @model_validator(mode="after")
    def closes_before_resolves(self) -> "MarketCreate":
        if self.closes_at and self.resolves_at:
            if self.closes_at > self.resolves_at:
                raise ValueError("closes_at must be before resolves_at")
        return self


class MarketUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=10, max_length=512)
    description: Optional[str] = Field(None, max_length=10_000)
    resolution_criteria: Optional[str] = Field(None, max_length=5_000)
    tags: Optional[list[str]] = None
    source_url: Optional[str] = Field(None, max_length=2048)
    closes_at: Optional[datetime] = None
    resolves_at: Optional[datetime] = None


class MarketResolve(BaseModel):
    outcome: MarketOutcome


# ---------------------------------------------------------------------------
# Read schemas
# ---------------------------------------------------------------------------

class MarketPublic(BaseModel):
    id: UUID
    creator_id: Optional[UUID]
    title: str
    description: Optional[str]
    resolution_criteria: Optional[str]
    tags: list[str]
    source_url: Optional[str]
    closes_at: Optional[datetime]
    resolves_at: Optional[datetime]
    resolved_at: Optional[datetime]
    outcome: Optional[MarketOutcome]
    created_at: datetime
    updated_at: datetime

    # Convenience flags
    is_resolved: bool
    is_open: bool

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Fix the integration test that passed `category`**

In `tests/integration/test_data_layer.py`, find `test_create_market` (around line 156). Change:

```python
    market = await MarketCRUD.create(
        db,
        obj_in=MarketCreate(
            title="Will it rain in SF tomorrow?",
            category="weather",
        ),
        creator_id=user.id,
    )
```

To:

```python
    market = await MarketCRUD.create(
        db,
        obj_in=MarketCreate(
            title="Will it rain in SF tomorrow?",
        ),
        creator_id=user.id,
    )
```

- [ ] **Step 4: Run the integration tests**

```bash
pytest tests/integration/test_data_layer.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/data-layer/data/models/market.py \
        services/data-layer/data/schemas/market.py \
        tests/integration/test_data_layer.py
git commit -m "feat: replace Market.category with tags ARRAY in model and schemas"
```

---

## Task 3: Update MarketCRUD — store tags, filter by tag

**Files:**
- Modify: `services/data-layer/data/crud/market.py`

---

- [ ] **Step 1: Update `list_open` to filter by tag**

In `services/data-layer/data/crud/market.py`, replace the `list_open` method signature and filter:

```python
    async def list_open(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        tag: Optional[str] = None,
    ) -> Sequence[Market]:
        """Return markets that are not yet resolved."""
        stmt = (
            select(Market)
            .where(Market.outcome.is_(None))
            .offset(skip)
            .limit(limit)
            .order_by(Market.created_at.desc())
        )
        if tag:
            stmt = stmt.where(Market.tags.contains([tag]))
        result = await db.execute(stmt)
        return result.scalars().all()
```

- [ ] **Step 2: Update `upsert_from_sync` to store tags**

In `upsert_from_sync`, the market creation block currently is:

```python
        if market is None:
            title = normalized.get("title") or f"[{source}] {external_id}"
            market = Market(
                source=source,
                external_id=external_id,
                title=title,
                description=normalized.get("description"),
                resolution_criteria=normalized.get("resolution_criteria"),
                closes_at=normalized.get("closes_at"),
                resolves_at=normalized.get("resolves_at"),
            )
```

Replace with:

```python
        if market is None:
            title = normalized.get("title") or f"[{source}] {external_id}"
            market = Market(
                source=source,
                external_id=external_id,
                title=title,
                description=normalized.get("description"),
                resolution_criteria=normalized.get("resolution_criteria"),
                closes_at=normalized.get("closes_at"),
                resolves_at=normalized.get("resolves_at"),
                tags=normalized.get("tags", []),
            )
```

Then, in the `else` block that updates existing markets, add after the existing mutable field updates (after the `resolves_at` block, before the resolution block):

```python
            incoming_tags = normalized.get("tags", [])
            if incoming_tags:
                market.tags = incoming_tags
```

The full `else` block should look like:

```python
        else:
            # Refresh mutable metadata fields
            if normalized.get("title"):
                market.title = normalized["title"]
            if normalized.get("description") is not None:
                market.description = normalized["description"]
            if normalized.get("resolution_criteria") is not None:
                market.resolution_criteria = normalized["resolution_criteria"]
            if normalized.get("closes_at") is not None:
                market.closes_at = normalized["closes_at"]
            if normalized.get("resolves_at") is not None:
                market.resolves_at = normalized["resolves_at"]
            incoming_tags = normalized.get("tags", [])
            if incoming_tags:
                market.tags = incoming_tags
```

- [ ] **Step 3: Run the tests**

```bash
pytest tests/integration/test_data_layer.py services/scheduler/tests/test_jobs.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add services/data-layer/data/crud/market.py
git commit -m "feat: MarketCRUD stores tags from sync and filters by tag in list_open"
```

---

## Task 4: Add tags to the Kalshi adapter (TDD)

**Files:**
- Modify: `services/connector-kalshi/tests/test_adapter.py`
- Modify: `services/connector-kalshi/connector_kalshi/adapter.py`

### Background

Kalshi market objects carry a top-level `category` field (a single string, e.g. `"Politics"`). `normalise_market` wraps it in a one-element list for consistency with the multi-tag format used by Manifold and Metaculus. If `category` is absent or `None`, `tags` is `[]`.

---

- [ ] **Step 1: Write the failing tests**

Add to `services/connector-kalshi/tests/test_adapter.py` (after the existing `test_normalise_market_no_title_at_all` test):

```python
def test_normalise_market_tags_from_category():
    """A market with a category field produces a one-element tags list."""
    raw = {**SAMPLE_MARKET, "category": "Politics"}
    m = normalise_market(raw)
    assert m["tags"] == ["Politics"]


def test_normalise_market_tags_empty_when_no_category():
    """A market with no category field produces an empty tags list."""
    raw = {k: v for k, v in SAMPLE_MARKET.items() if k != "category"}
    m = normalise_market(raw)
    assert m["tags"] == []
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
pytest services/connector-kalshi/tests/test_adapter.py::test_normalise_market_tags_from_category \
       services/connector-kalshi/tests/test_adapter.py::test_normalise_market_tags_empty_when_no_category -v
```

Expected: FAIL — `KeyError: 'tags'` or `AssertionError`.

- [ ] **Step 3: Add `tags` to `normalise_market` in the Kalshi adapter**

In `services/connector-kalshi/connector_kalshi/adapter.py`, add `tags` to the dict returned by `normalise_market`. The full return statement becomes:

```python
    return {
        "external_id": raw.get("ticker"),
        "source": "kalshi",
        "title": _market_title(raw),
        "description": raw.get("rules_primary"),
        "resolution_criteria": raw.get("rules_secondary"),
        "closes_at": _parse_ts(raw.get("close_time")),
        "resolves_at": _parse_ts(
            raw.get("latest_expiration_time") or raw.get("expiration_time")
        ),
        "resolved": raw.get("status") == "finalized",
        "outcome": raw.get("result"),  # "yes" | "no" | None
        "tags": [raw["category"]] if raw.get("category") else [],
        "raw": raw,
    }
```

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
pytest services/connector-kalshi/tests/test_adapter.py -v
```

Expected: all tests pass, including the two new tag tests.

- [ ] **Step 5: Commit**

```bash
git add services/connector-kalshi/connector_kalshi/adapter.py \
        services/connector-kalshi/tests/test_adapter.py
git commit -m "feat: add tags to Kalshi normalise_market from category field"
```

---

## Task 5: Wire scoring engine domain in jobs.py

**Files:**
- Modify: `services/scheduler/scheduler/jobs.py`

### Background

`detect_and_score_resolutions` builds `PredictionRecord` objects with `domain=None`. After this task, `domain` is populated from the first tag of each prediction's market. A single batch `SELECT id, tags FROM markets WHERE id IN (...)` runs once per user per scoring cycle — one extra query, negligible cost.

The `db` object in this code path is a real `AsyncSession`. The existing unit tests mock `db` with `AsyncMock`, so the new `db.execute(...)` call will return a MagicMock whose iteration produces nothing, leaving `_market_tags` as `{}` and `domain` as `None`. All existing tests continue to pass.

---

- [ ] **Step 1: Add imports**

At the top of `services/scheduler/scheduler/jobs.py`, make two changes:

Change:
```python
from sqlalchemy import select
```
(Add this line — it doesn't currently exist. Place it after the existing stdlib imports, before the `data.*` imports.)

Change:
```python
from data.models.market import MarketOutcome
```
To:
```python
from data.models.market import Market, MarketOutcome
```

- [ ] **Step 2: Add the market tags batch query and replace `domain=None`**

Find the block that builds `pred_records` (around line 205). It currently reads:

```python
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
                        if p.market_id == fresh_market.id
                    ] + [
                        PredictionRecord(
                            prediction_id=str(p.id),
                            predicted_probability=float(p.probability),
                            outcome=float(p.brier_score) <= 0.25,
                            source=p.source or "unknown",
                            domain=None,
                        )
                        for p in all_resolved
                        if p.market_id != fresh_market.id
                    ]
```

Replace with:

```python
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
                            outcome=float(p.brier_score) <= 0.25,
                            source=p.source or "unknown",
                            domain=(_market_tags.get(p.market_id) or [None])[0],
                        )
                        for p in all_resolved
                        if p.market_id != fresh_market.id
                    ]
```

- [ ] **Step 3: Run the scheduler tests**

```bash
pytest services/scheduler/tests/test_jobs.py -v
```

Expected: all tests pass. The new `db.execute` call returns a MagicMock in tests, which iterates as empty, leaving `_market_tags = {}` and `domain = None` — matching the previous hardcoded behaviour.

- [ ] **Step 4: Run the full test suite**

```bash
pytest tests/ services/scoring-engine/tests/ services/connector-kalshi/tests/ \
       services/connector-manifold/tests/ services/connector-metaculus/tests/ \
       services/scheduler/tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/scheduler/scheduler/jobs.py
git commit -m "feat: populate PredictionRecord.domain from market tags for per-domain scoring"
```
