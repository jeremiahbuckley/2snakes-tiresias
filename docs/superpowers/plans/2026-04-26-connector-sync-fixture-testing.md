# Connector Sync Fixture Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add integration tests for all four connector sync pipelines (Kalshi, Manifold, Metaculus, Polymarket) using parametrized JSON fixture files, so adding a regression case requires only dropping in a new JSON file.

**Architecture:** Tests call `sync_one_user(db, user_id)` from `scheduler/sync.py` with the HTTP client mocked. The DB is real (Postgres `tiresias_test`). Each connector gets a `tests/fixtures/<connector>/` directory of JSON scenarios. All four tests share a conftest that provides account factory fixtures and an `assert_scenario` helper.

**Tech Stack:** pytest-asyncio, unittest.mock (AsyncMock/patch), SQLAlchemy AsyncSession, cryptography (Fernet), PostgreSQL

---

## File Map

| File | Change |
|------|--------|
| `tests/integration/conftest.py` | Modify — add env setup, account fixtures, assert_scenario |
| `tests/fixtures/kalshi/happy_path.json` | Create |
| `tests/fixtures/manifold/happy_path.json` | Create |
| `tests/fixtures/metaculus/happy_path.json` | Create |
| `tests/fixtures/polymarket/happy_path.json` | Create |
| `tests/integration/test_sync_kalshi.py` | Create |
| `tests/integration/test_sync_manifold.py` | Create |
| `tests/integration/test_sync_metaculus.py` | Create |
| `tests/integration/test_sync_polymarket.py` | Create |

---

## Task 1: Extend conftest with shared infrastructure

**Files:**
- Modify: `tests/integration/conftest.py`

### Background

`scheduler/scheduler/credentials.py` reads `CREDENTIAL_ENCRYPTION_KEY` at **module import time**:

```python
_ENCRYPTION_KEY: str = os.environ.get("CREDENTIAL_ENCRYPTION_KEY", "")
```

The integration conftest runs before test modules are imported (pytest processes conftest files before collecting test files in the same directory). Setting the env var here means it is in place when `from scheduler.sync import sync_one_user` runs in the test files.

For **Metaculus** specifically: `_sync_metaculus` calls `decrypt_credential(account.credential_encrypted)` and returns `0` if the result is falsy. So the `metaculus_account` fixture must store a valid Fernet-encrypted value, and the key must be set before the session starts.

For **Manifold**: same call, but the result is used as `api_key or ""`, so even `None` is tolerated — but a real encrypted credential is cleaner.

For **Kalshi** and **Polymarket**: no `decrypt_credential` call; `credential_encrypted=None` is fine.

---

- [ ] **Step 1: Add env setup and Fernet credential at the top of conftest**

Open `tests/integration/conftest.py`. Add the following block **before** the existing `os.environ.setdefault("DATABASE_URL", ...)` line:

```python
import os

from cryptography.fernet import Fernet as _Fernet

# Set before any import of scheduler.credentials (which reads this at module level).
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", _Fernet.generate_key().decode())

# Pre-encrypt a dummy token with whatever key is now active.
_TEST_FERNET_KEY = os.environ["CREDENTIAL_ENCRYPTION_KEY"].encode()
TEST_ENCRYPTED_CREDENTIAL: str = _Fernet(_TEST_FERNET_KEY).encrypt(b"test-token").decode()
```

The full top of the file should read:

```python
"""
Integration test fixtures.
...
"""

import os

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet as _Fernet
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", _Fernet.generate_key().decode())
_TEST_FERNET_KEY = os.environ["CREDENTIAL_ENCRYPTION_KEY"].encode()
TEST_ENCRYPTED_CREDENTIAL: str = _Fernet(_TEST_FERNET_KEY).encrypt(b"test-token").decode()

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias_test",
)

from data.database import Base  # noqa: E402
from data.models import User, Market, Prediction  # noqa: F401,E402
from data.models.linked_account import LinkedAccount, Platform, PlatformType  # noqa: E402
```

Remove the old `from data.models import User, Market, MarketOutcome, Prediction, UserScore` line (replace it with the two imports above — `MarketOutcome` and `UserScore` are no longer needed in conftest; they were only imported to ensure table creation, and `Base.metadata.create_all` handles that regardless).

- [ ] **Step 2: Add the `assert_scenario` fixture**

Append to `tests/integration/conftest.py`:

```python
@pytest.fixture
def assert_scenario(db: AsyncSession):
    """
    Returns an async callable that asserts DB state matches a scenario's expected dict.

    expected schema:
      {
        "market_count": int,
        "prediction_count": int,
        "markets": [{"external_id": str, "source": str, "outcome": str, ...}],
        "predictions": [{"source": str, "probability": float, ...}]
      }

    Markets are matched by external_id. Predictions are index-matched (V1:
    one prediction per fixture). Only declared fields are checked.
    Floats use pytest.approx.
    """
    async def _assert(expected: dict) -> None:
        markets = (await db.execute(select(Market))).scalars().all()
        predictions = (await db.execute(select(Prediction))).scalars().all()

        assert len(markets) == expected["market_count"], (
            f"Expected {expected['market_count']} market(s), got {len(markets)}"
        )
        assert len(predictions) == expected["prediction_count"], (
            f"Expected {expected['prediction_count']} prediction(s), got {len(predictions)}"
        )

        for exp_m in expected.get("markets", []):
            match = next(
                (m for m in markets if m.external_id == exp_m["external_id"]), None
            )
            assert match is not None, (
                f"Market external_id={exp_m['external_id']!r} not found in DB"
            )
            for field, value in exp_m.items():
                if field == "external_id":
                    continue
                actual = getattr(match, field)
                if isinstance(value, float):
                    assert actual == pytest.approx(value), (
                        f"Market.{field}: {actual!r} != approx({value!r})"
                    )
                else:
                    assert actual == value, (
                        f"Market.{field}: {actual!r} != {value!r}"
                    )

        for i, exp_p in enumerate(expected.get("predictions", [])):
            # V1: index-based matching — one prediction per fixture scenario.
            # For multi-prediction scenarios, match by external_id instead.
            pred = predictions[i]
            for field, value in exp_p.items():
                actual = getattr(pred, field)
                if isinstance(value, float):
                    assert actual == pytest.approx(value), (
                        f"Prediction[{i}].{field}: {actual!r} != approx({value!r})"
                    )
                else:
                    assert actual == value, (
                        f"Prediction[{i}].{field}: {actual!r} != {value!r}"
                    )

    return _assert
```

- [ ] **Step 3: Add the four account factory fixtures**

Append to `tests/integration/conftest.py`:

```python
@pytest_asyncio.fixture
async def kalshi_account(db: AsyncSession) -> LinkedAccount:
    """User + Kalshi LinkedAccount. _sync_kalshi reads env vars, not account credentials."""
    user = User(
        email="test-kalshi@example.com",
        username="test_kalshi_user",
        hashed_password="$2b$12$notarealhashedpassword",
    )
    db.add(user)
    await db.flush()

    account = LinkedAccount(
        user_id=user.id,
        platform=Platform.KALSHI,
        platform_type=PlatformType.MARKET,
        external_identifier="kalshi-user-ext-id",
        credential_encrypted=None,
        is_enabled=True,
        is_verified=True,
    )
    db.add(account)
    await db.flush()
    return account


@pytest_asyncio.fixture
async def manifold_account(db: AsyncSession) -> LinkedAccount:
    """User + Manifold LinkedAccount. external_identifier is the Manifold username."""
    user = User(
        email="test-manifold@example.com",
        username="test_manifold_user",
        hashed_password="$2b$12$notarealhashedpassword",
    )
    db.add(user)
    await db.flush()

    account = LinkedAccount(
        user_id=user.id,
        platform=Platform.MANIFOLD,
        platform_type=PlatformType.MARKET,
        external_identifier="test-manifold-username",
        credential_encrypted=TEST_ENCRYPTED_CREDENTIAL,
        is_enabled=True,
        is_verified=True,
    )
    db.add(account)
    await db.flush()
    return account


@pytest_asyncio.fixture
async def metaculus_account(db: AsyncSession) -> LinkedAccount:
    """User + Metaculus LinkedAccount. external_identifier is the integer user ID as a string."""
    user = User(
        email="test-metaculus@example.com",
        username="test_metaculus_user",
        hashed_password="$2b$12$notarealhashedpassword",
    )
    db.add(user)
    await db.flush()

    account = LinkedAccount(
        user_id=user.id,
        platform=Platform.METACULUS,
        platform_type=PlatformType.MARKET,
        external_identifier="12345",
        credential_encrypted=TEST_ENCRYPTED_CREDENTIAL,
        is_enabled=True,
        is_verified=True,
    )
    db.add(account)
    await db.flush()
    return account


@pytest_asyncio.fixture
async def polymarket_account(db: AsyncSession) -> LinkedAccount:
    """User + Polymarket LinkedAccount. external_identifier is the wallet address."""
    user = User(
        email="test-polymarket@example.com",
        username="test_polymarket_user",
        hashed_password="$2b$12$notarealhashedpassword",
    )
    db.add(user)
    await db.flush()

    account = LinkedAccount(
        user_id=user.id,
        platform=Platform.POLYMARKET,
        platform_type=PlatformType.MARKET,
        external_identifier="0xWALLET123",
        credential_encrypted=None,
        is_enabled=True,
        is_verified=True,
    )
    db.add(account)
    await db.flush()
    return account
```

- [ ] **Step 4: Verify the conftest is importable**

```bash
pytest tests/integration/conftest.py --collect-only 2>&1 | head -20
```

Expected: no import errors. May show existing collected tests.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/conftest.py
git commit -m "test: add account fixtures and assert_scenario to integration conftest"
```

---

## Task 2: Kalshi happy-path fixture and test

**Files:**
- Create: `tests/fixtures/kalshi/happy_path.json`
- Create: `tests/integration/test_sync_kalshi.py`

### Background

`_sync_kalshi` (in `scheduler/scheduler/sync.py`) calls:
- `client.get_fills()` → list of fill dicts
- `client.get_settlements()` → list of settlement dicts
- `client.get_market(ticker)` → one market dict per unique ticker in fills

Because these imports happen inside the function body (`from connector_kalshi.client import KalshiClient`), the patch target is `connector_kalshi.client.KalshiClient`.

The fill in the fixture has `yes_price_dollars: "0.62"` → `predicted_probability = 0.62` → stored in `Prediction.probability` as `round(0.62, 5) = 0.62`.

The settlement has `market_result: "no"` → passed to `_map_outcome("kalshi", "no")` → `MarketOutcome.NO`. Since `MarketOutcome` is `str, enum.Enum`, `assert market.outcome == "no"` evaluates to `True`.

---

- [ ] **Step 1: Create the fixture directory and write happy_path.json**

```bash
mkdir -p tests/fixtures/kalshi
```

Write `tests/fixtures/kalshi/happy_path.json`:

```json
{
  "description": "Standard Kalshi fill and settlement for a resolved binary market",
  "input": {
    "fills": [
      {
        "fill_id": "fill-xyz-456",
        "trade_id": "trade-abc-123",
        "ticker": "PRES-2024-DEM",
        "market_ticker": "PRES-2024-DEM",
        "side": "yes",
        "action": "buy",
        "count_fp": "10.0000",
        "yes_price_dollars": "0.62",
        "no_price_dollars": "0.38",
        "created_time": "2024-10-01T10:00:00Z"
      }
    ],
    "settlements": [
      {
        "ticker": "PRES-2024-DEM",
        "market_result": "no",
        "revenue": -620,
        "settled_time": "2024-11-06T14:00:00Z"
      }
    ],
    "markets": {
      "PRES-2024-DEM": {
        "ticker": "PRES-2024-DEM",
        "title": "Will the Democratic candidate win the 2024 US Presidential Election?",
        "rules_primary": "Resolves YES if the Democratic candidate wins.",
        "close_time": "2024-11-05T23:00:00Z",
        "latest_expiration_time": "2024-11-06T12:00:00Z",
        "status": "finalized",
        "result": "no"
      }
    }
  },
  "expected": {
    "market_count": 1,
    "prediction_count": 1,
    "markets": [
      {
        "external_id": "PRES-2024-DEM",
        "source": "kalshi",
        "outcome": "no"
      }
    ],
    "predictions": [
      {
        "source": "kalshi",
        "probability": 0.62
      }
    ]
  }
}
```

- [ ] **Step 2: Write the test file**

Write `tests/integration/test_sync_kalshi.py`:

```python
"""Integration tests for the Kalshi sync pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from scheduler.sync import sync_one_user

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "kalshi"


def _load_scenarios():
    return [
        pytest.param(json.loads(p.read_text()), id=p.stem)
        for p in sorted(_FIXTURES_DIR.glob("*.json"))
    ]


@pytest.mark.parametrize("scenario", _load_scenarios())
async def test_kalshi_sync(db, kalshi_account, assert_scenario, scenario):
    with patch("connector_kalshi.client.KalshiClient") as MockClient:
        inst = MockClient.return_value
        inst.get_fills = AsyncMock(return_value=scenario["input"]["fills"])
        inst.get_settlements = AsyncMock(return_value=scenario["input"]["settlements"])
        inst.get_market = AsyncMock(
            side_effect=lambda ticker: scenario["input"]["markets"][ticker]
        )

        await sync_one_user(db, kalshi_account.user_id)

    await assert_scenario(scenario["expected"])
```

- [ ] **Step 3: Run the test**

```bash
pytest tests/integration/test_sync_kalshi.py -v
```

Expected output:
```
tests/integration/test_sync_kalshi.py::test_kalshi_sync[happy_path] PASSED
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/kalshi/happy_path.json tests/integration/test_sync_kalshi.py
git commit -m "test: add Kalshi sync happy-path integration test"
```

---

## Task 3: Manifold happy-path fixture and test

**Files:**
- Create: `tests/fixtures/manifold/happy_path.json`
- Create: `tests/integration/test_sync_manifold.py`

### Background

`_sync_manifold` calls:
- `client.get_user_bets(manifold_username)` → list of bet dicts
- `client.get_market(contract_id)` → market dict per unique contractId

Redemption bets (`isRedemption: true`) are filtered out before upserting.
The `manifold_account.external_identifier` is `"test-manifold-username"` — this is passed to `get_user_bets`.

For a YES bet with `probBefore: 0.60`: `predicted_probability = probBefore = 0.60` → `Prediction.probability = 0.60`.

Market `resolution: "YES"` → `_map_outcome("manifold", "YES")` → `MarketOutcome.YES` → `market.outcome == "yes"` is `True`.

Patch target: `connector_manifold.client.ManifoldClient`.

---

- [ ] **Step 1: Create the fixture directory and write happy_path.json**

```bash
mkdir -p tests/fixtures/manifold
```

Write `tests/fixtures/manifold/happy_path.json`:

```json
{
  "description": "YES bet on a resolved Manifold binary market",
  "input": {
    "bets": [
      {
        "id": "bet-mfld-001",
        "contractId": "manifold-mkt-789",
        "outcome": "YES",
        "amount": 50.0,
        "shares": 65.3,
        "probBefore": 0.60,
        "probAfter": 0.65,
        "createdTime": 1720000000000,
        "isRedemption": false
      }
    ],
    "markets": {
      "manifold-mkt-789": {
        "id": "manifold-mkt-789",
        "question": "Will OpenAI release GPT-5 in 2024?",
        "textDescription": "Resolves YES if OpenAI officially announces GPT-5 before Jan 1 2025.",
        "resolutionCriteria": "Official OpenAI announcement.",
        "closeTime": 1735689600000,
        "resolutionTime": 1735700000000,
        "isResolved": true,
        "resolution": "YES",
        "groupSlugs": ["ai", "technology"]
      }
    }
  },
  "expected": {
    "market_count": 1,
    "prediction_count": 1,
    "markets": [
      {
        "external_id": "manifold-mkt-789",
        "source": "manifold",
        "outcome": "yes"
      }
    ],
    "predictions": [
      {
        "source": "manifold",
        "probability": 0.6
      }
    ]
  }
}
```

- [ ] **Step 2: Write the test file**

Write `tests/integration/test_sync_manifold.py`:

```python
"""Integration tests for the Manifold sync pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from scheduler.sync import sync_one_user

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "manifold"


def _load_scenarios():
    return [
        pytest.param(json.loads(p.read_text()), id=p.stem)
        for p in sorted(_FIXTURES_DIR.glob("*.json"))
    ]


@pytest.mark.parametrize("scenario", _load_scenarios())
async def test_manifold_sync(db, manifold_account, assert_scenario, scenario):
    with patch("connector_manifold.client.ManifoldClient") as MockClient:
        inst = MockClient.return_value
        inst.get_user_bets = AsyncMock(return_value=scenario["input"]["bets"])
        inst.get_market = AsyncMock(
            side_effect=lambda contract_id: scenario["input"]["markets"][contract_id]
        )

        await sync_one_user(db, manifold_account.user_id)

    await assert_scenario(scenario["expected"])
```

- [ ] **Step 3: Run the test**

```bash
pytest tests/integration/test_sync_manifold.py -v
```

Expected output:
```
tests/integration/test_sync_manifold.py::test_manifold_sync[happy_path] PASSED
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/manifold/happy_path.json tests/integration/test_sync_manifold.py
git commit -m "test: add Manifold sync happy-path integration test"
```

---

## Task 4: Metaculus happy-path fixture and test

**Files:**
- Create: `tests/fixtures/metaculus/happy_path.json`
- Create: `tests/integration/test_sync_metaculus.py`

### Background

`_sync_metaculus` calls:
1. `client.get_user_posts(metaculus_user_id)` — the `metaculus_user_id` is `int("12345") = 12345` (parsed from `account.external_identifier`).
2. Filters posts to those with `question.type == "binary"`.
3. For each binary post ID: `client.get_post(post_id)` — `post_id` is an **integer**.

The mock's `side_effect` for `get_post` must convert the integer to a string to look up in the fixture (JSON object keys are always strings):
```python
side_effect=lambda post_id: scenario["input"]["post_details"][str(post_id)]
```

`my_forecasts.latest.forecast_values = [0.25, 0.75]` → `_extract_probability_yes` → `forecast_values[1] = 0.75` → `Prediction.probability = 0.75`.

Market `question.resolution: "yes"` → `_map_outcome("metaculus", "yes")` → `MarketOutcome.YES` → `market.outcome == "yes"` is `True`.

The `metaculus_account.credential_encrypted` holds a real Fernet-encrypted value so that `decrypt_credential` returns a truthy token and `_sync_metaculus` does not return early.

Patch target: `connector_metaculus.client.MetaculusClient`.

---

- [ ] **Step 1: Create the fixture directory and write happy_path.json**

```bash
mkdir -p tests/fixtures/metaculus
```

Write `tests/fixtures/metaculus/happy_path.json`:

```json
{
  "description": "Binary Metaculus question with a latest forecast and YES resolution",
  "input": {
    "posts": [
      {
        "id": 1234,
        "question": {
          "type": "binary"
        }
      }
    ],
    "post_details": {
      "1234": {
        "id": 1234,
        "title": "Will AI pass the Turing test by 2025?",
        "resolved": true,
        "question": {
          "type": "binary",
          "resolution": "yes",
          "description": "Standard Turing test as defined by Turing (1950).",
          "resolution_criteria": "A human judge cannot distinguish the AI from a human in 30% of trials.",
          "actual_close_time": "2025-01-01T00:00:00Z",
          "actual_resolve_time": "2025-01-15T00:00:00Z",
          "my_forecasts": {
            "latest": {
              "forecast_values": [0.25, 0.75],
              "start_time": 1720000000.0
            },
            "history": [],
            "score_data": {}
          }
        },
        "categories": [
          {
            "id": 1,
            "name": "AI",
            "slug": "ai",
            "description": "Artificial intelligence"
          }
        ]
      }
    }
  },
  "expected": {
    "market_count": 1,
    "prediction_count": 1,
    "markets": [
      {
        "external_id": "1234",
        "source": "metaculus",
        "outcome": "yes"
      }
    ],
    "predictions": [
      {
        "source": "metaculus",
        "probability": 0.75
      }
    ]
  }
}
```

- [ ] **Step 2: Write the test file**

Write `tests/integration/test_sync_metaculus.py`:

```python
"""Integration tests for the Metaculus sync pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from scheduler.sync import sync_one_user

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "metaculus"


def _load_scenarios():
    return [
        pytest.param(json.loads(p.read_text()), id=p.stem)
        for p in sorted(_FIXTURES_DIR.glob("*.json"))
    ]


@pytest.mark.parametrize("scenario", _load_scenarios())
async def test_metaculus_sync(db, metaculus_account, assert_scenario, scenario):
    with patch("connector_metaculus.client.MetaculusClient") as MockClient:
        inst = MockClient.return_value
        inst.get_user_posts = AsyncMock(return_value=scenario["input"]["posts"])
        # get_post is called with an integer post_id; JSON keys are strings.
        inst.get_post = AsyncMock(
            side_effect=lambda post_id: scenario["input"]["post_details"][str(post_id)]
        )

        await sync_one_user(db, metaculus_account.user_id)

    await assert_scenario(scenario["expected"])
```

- [ ] **Step 3: Run the test**

```bash
pytest tests/integration/test_sync_metaculus.py -v
```

Expected output:
```
tests/integration/test_sync_metaculus.py::test_metaculus_sync[happy_path] PASSED
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/metaculus/happy_path.json tests/integration/test_sync_metaculus.py
git commit -m "test: add Metaculus sync happy-path integration test"
```

---

## Task 5: Polymarket happy-path fixture and test

**Files:**
- Create: `tests/fixtures/polymarket/happy_path.json`
- Create: `tests/integration/test_sync_polymarket.py`

### Background

`_sync_polymarket` calls:
1. `client.get_user_trades(wallet_address)` — wallet is `account.external_identifier = "0xWALLET123"`.
2. `client.get_closed_positions(wallet_address)`.
3. Builds `slug_by_condition` from trades (and closed positions): `conditionId → slug`.
4. `client.get_market_by_slug(slug)` → market dict.

The trade in the fixture has `conditionId: "0xCONDITIONABC"` and `slug: "will-trump-win-2024"`.

`_trade_probability` with `side="BUY"`, `outcome="Yes"`, `price="0.65"`:
- `price = float("0.65") = 0.65`
- `outcome.lower() = "yes"` → not in `("no", "false")`
- Returns `0.65` → `Prediction.probability = 0.65`.

Market `outcomePrices: '["1", "0"]'` → `_winning_outcome(["Yes", "No"], ["1", "0"])` → `"Yes"` → `_map_outcome("polymarket", "Yes")` → `MarketOutcome.YES` → `market.outcome == "yes"` is `True`.

Note: `outcomePrices` and `outcomes` are **JSON-encoded strings** (a Polymarket quirk) — they must be passed as strings in the fixture, not as JSON arrays.

Polymarket uses no per-user credentials (`credential_encrypted=None`). No `decrypt_credential` call is made.

Patch target: `connector_polymarket.client.PolymarketClient`.

---

- [ ] **Step 1: Create the fixture directory and write happy_path.json**

```bash
mkdir -p tests/fixtures/polymarket
```

Write `tests/fixtures/polymarket/happy_path.json`:

```json
{
  "description": "Buy-YES trade on a resolved Polymarket binary market",
  "input": {
    "trades": [
      {
        "transactionHash": "0xabc123def456",
        "conditionId": "0xCONDITIONABC",
        "slug": "will-trump-win-2024",
        "side": "BUY",
        "outcome": "Yes",
        "outcomeIndex": 0,
        "size": "100",
        "price": "0.65",
        "timestamp": 1720000000
      }
    ],
    "closed_positions": [],
    "markets": {
      "will-trump-win-2024": {
        "conditionId": "0xCONDITIONABC",
        "question": "Will Trump win the 2024 US election?",
        "description": "Resolves YES if Donald Trump wins the 2024 US presidential election.",
        "resolutionSource": "Major news sources",
        "closed": true,
        "outcomes": "[\"Yes\", \"No\"]",
        "outcomePrices": "[\"1\", \"0\"]",
        "endDateIso": "2024-11-06T12:00:00Z",
        "tags": []
      }
    }
  },
  "expected": {
    "market_count": 1,
    "prediction_count": 1,
    "markets": [
      {
        "external_id": "0xCONDITIONABC",
        "source": "polymarket",
        "outcome": "yes"
      }
    ],
    "predictions": [
      {
        "source": "polymarket",
        "probability": 0.65
      }
    ]
  }
}
```

- [ ] **Step 2: Write the test file**

Write `tests/integration/test_sync_polymarket.py`:

```python
"""Integration tests for the Polymarket sync pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from scheduler.sync import sync_one_user

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "polymarket"


def _load_scenarios():
    return [
        pytest.param(json.loads(p.read_text()), id=p.stem)
        for p in sorted(_FIXTURES_DIR.glob("*.json"))
    ]


@pytest.mark.parametrize("scenario", _load_scenarios())
async def test_polymarket_sync(db, polymarket_account, assert_scenario, scenario):
    with patch("connector_polymarket.client.PolymarketClient") as MockClient:
        inst = MockClient.return_value
        inst.get_user_trades = AsyncMock(return_value=scenario["input"]["trades"])
        inst.get_closed_positions = AsyncMock(
            return_value=scenario["input"]["closed_positions"]
        )
        inst.get_market_by_slug = AsyncMock(
            side_effect=lambda slug: scenario["input"]["markets"].get(slug)
        )

        await sync_one_user(db, polymarket_account.user_id)

    await assert_scenario(scenario["expected"])
```

- [ ] **Step 3: Run the test**

```bash
pytest tests/integration/test_sync_polymarket.py -v
```

Expected output:
```
tests/integration/test_sync_polymarket.py::test_polymarket_sync[happy_path] PASSED
```

- [ ] **Step 4: Run the full integration suite to confirm no regressions**

```bash
pytest tests/integration/ -v
```

Expected: all tests pass (including existing `test_data_layer.py` and `test_scoring_pipeline.py` if any are unskipped).

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/polymarket/happy_path.json tests/integration/test_sync_polymarket.py
git commit -m "test: add Polymarket sync happy-path integration test"
```

---

## Adding a Regression Case (reference)

When a new API response bug is found:

1. Capture the raw API response JSON.
2. Create a new file, e.g. `tests/fixtures/kalshi/overflow_market_id.json`.
3. Populate `input` with the offending response and `expected` with the correct DB state.
4. Run `pytest tests/integration/test_sync_kalshi.py -v` — the new scenario is automatically picked up.
5. If the test fails, fix the bug in the connector adapter, then re-run to confirm it passes.
6. Commit the fixture file alongside the fix.
