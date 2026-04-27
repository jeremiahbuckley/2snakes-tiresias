# Market Tags Design

**Date:** 2026-04-27
**Status:** Approved

## Problem

Markets from all four connector platforms carry topic tags/categories, but nothing is stored in the database. The `Market` model has a single `category: String(128)` column that is never populated from sync. As a result, the scoring engine's `per_domain` Brier scores are always empty (`domain=None` hardcoded in `jobs.py`), and UI filtering by topic is impossible.

## Goals

1. Store raw tags for each synced market.
2. Feed those tags into the scoring engine's `per_domain` computation.
3. Enable UI filtering of markets by tag.

Tag normalization across platforms (e.g. mapping Kalshi `"Politics"` and Metaculus `"us-politics"` to a canonical `"politics"`) is out of scope — a TODO for a future pass.

## Scope

Connectors covered: Kalshi, Manifold, Metaculus.
Polymarket: excluded (authentication issues; tags already dropped in adapter output as `tags`).

## Data Model

### Migration 0006

Drop `category: String(128)` and add `tags: ARRAY(Text)` with a GIN index.

```python
# services/data-layer/alembic/versions/0006_market_tags.py

def upgrade():
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

def downgrade():
    op.drop_index("ix_markets_tags", table_name="markets")
    op.drop_column("markets", "tags")
    op.add_column(
        "markets",
        sa.Column("category", sa.String(128), nullable=True),
    )
```

`category` is safe to drop: the column is never populated from sync, and no row in the DB carries a non-NULL value from any connector.

### Market model

Replace:
```python
category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
```

With:
```python
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY

tags: Mapped[list[str]] = mapped_column(
    PG_ARRAY(Text()),
    nullable=False,
    default=list,
    server_default="{}",
)
```

### Pydantic schemas

In `MarketCreate` and `MarketUpdate`, replace `category: Optional[str]` with `tags: list[str] = []`.

In the read/response schema (whichever Pydantic model is returned from API endpoints), add `tags: list[str]`.

### CRUD

**`list_open`:** Replace the `category` filter parameter with a `tag: str | None` parameter.
```python
if tag:
    stmt = stmt.where(tag == func.any(Market.tags))
```

**`upsert_from_sync`:**
- On create: `tags=normalized.get("tags", [])`.
- On update: if `normalized.get("tags")` is non-empty, overwrite `market.tags`. If empty, leave existing tags untouched (a re-sync with missing tag data should not wipe stored tags).

## Adapter Changes

### Kalshi

`normalise_market` currently has no `tags` field. Add:
```python
raw_category = raw.get("category")
"tags": [raw_category] if raw_category else [],
```

### Manifold

Already returns `"tags": raw.get("groupSlugs", [])`. No change needed.

### Metaculus

Already returns `"tags": [c["slug"] for c in categories if c.get("slug")]`. No change needed.

## Scoring Engine Wiring

In `scheduler/scheduler/jobs.py`, where `PredictionRecord` objects are built with `domain=None`:

1. After loading `all_resolved`, collect the unique market IDs.
2. Run a single batch query: `SELECT id, tags FROM markets WHERE id IN (...)`.
3. Build `market_tags: dict[UUID, list[str]]`.
4. Populate `domain` as `market_tags.get(p.market_id, [None])[0]` (first tag, or `None`).

This is one extra DB query per scoring run — negligible cost.

## Testing

### Adapter unit tests

- **Kalshi** (`services/connector-kalshi/tests/test_adapter.py`): add `test_normalise_market_tags` asserting `normalise_market(raw_with_category)["tags"] == ["Politics"]`, and `test_normalise_market_no_category` asserting `tags == []`.
- **Manifold and Metaculus**: tag tests already exist — no new tests needed.

### Integration fixture JSON

Update `tests/fixtures/kalshi/happy_path.json`, `tests/fixtures/manifold/happy_path.json`, and `tests/fixtures/metaculus/happy_path.json` to add a `tags` field to their `expected.markets` entry. This confirms tags flow from the adapter all the way to the DB row.

Example (Kalshi — the fixture market currently has no `category` field, so we add one):
```json
"markets": {
  "PRES-2024-DEM": {
    ...
    "category": "Politics"
  }
}
```
```json
"expected": {
  "markets": [{ "external_id": "PRES-2024-DEM", "source": "kalshi", "outcome": "no", "tags": ["Politics"] }]
}
```
