# Connector Sync Fixture Testing

**Date:** 2026-04-26
**Status:** Approved

## Problem

The connector services (Kalshi, Manifold, Metaculus, Polymarket) have thorough unit tests for
their adapters but no integration tests verifying that the full sync pipeline — HTTP response →
adapter → DB upsert — produces correct `Market` and `Prediction` rows. Bugs from unexpected API
responses (field renames, encoding changes, pagination quirks) have reached production without
being caught. We need a test layer that exercises the full sync path with known inputs and
verifiable DB outputs, and that can grow to cover regression cases by adding files rather than
Python code.

## Scope

First pass: happy-path fixture (one per connector) covering a single resolved market + prediction.
Subsequent passes: regression cases for bugs already seen (overflow dedupe keys, pagination edge
cases, legacy field fallbacks, void/scalar market results).

Out of scope: testing the scoring engine or badge pipeline; those are a separate integration test.

## Architecture

### Entry point under test

`sync_one_user(db, user_id)` in `services/scheduler/scheduler/sync.py`.

This function:
1. Queries the DB for a user's active linked accounts.
2. Dispatches to `_sync_kalshi`, `_sync_manifold`, `_sync_metaculus`, or `_sync_polymarket`.
3. Each helper calls the connector's HTTP client, runs the adapter, and upserts `Market` and
   `Prediction` rows via the data layer CRUD.

The HTTP client is the only external boundary that needs to be mocked. The adapter, CRUD, and DB
all run for real against the integration test Postgres instance.

### Fixture file format

Each scenario is a single JSON file. The filename is the test ID (used as the pytest parameter
ID). Files live in `tests/fixtures/<connector>/`.

```
tests/fixtures/
  kalshi/
    happy_path.json
  manifold/
    happy_path.json
  metaculus/
    happy_path.json
  polymarket/
    happy_path.json
```

File schema:

```json
{
  "description": "Human-readable summary of what this scenario tests",
  "input": {
    // connector-specific API response payloads (see per-connector shapes below)
  },
  "expected": {
    "market_count": 1,
    "prediction_count": 1,
    "markets": [
      { "external_id": "...", "source": "kalshi", "resolved": true }
    ],
    "predictions": [
      { "predicted_probability": 0.62, "source": "kalshi" }
    ]
  }
}
```

`expected.markets` and `expected.predictions` are partial — only declared fields are asserted.
Floats are compared with `pytest.approx`. Fields not listed are not checked.

#### Per-connector input shapes

**Kalshi:**
```json
{
  "fills": [ /* list of fill objects from get_fills() */ ],
  "settlements": [ /* list of settlement objects from get_settlements() */ ],
  "markets": {
    "TICKER": { /* market object from get_market(ticker) */ }
  }
}
```

**Manifold:**
```json
{
  "bets": [ /* list of bet objects from get_user_bets(username) */ ],
  "markets": {
    "CONTRACT_ID": { /* market object from get_market(contract_id) */ }
  }
}
```

**Metaculus:**
```json
{
  "posts": [ /* list of post stubs from get_user_posts(user_id) */ ],
  "post_details": {
    "POST_ID": { /* full post from get_post(post_id) — includes my_forecasts */ }
  }
}
```

**Polymarket:**
```json
{
  "trades": [ /* list of trade objects from get_user_trades(wallet) */ ],
  "closed_positions": [ /* from get_closed_positions(wallet) */ ],
  "markets": {
    "SLUG": { /* market object from get_market_by_slug(slug) */ }
  }
}
```

### Test files

One file per connector in `tests/integration/`:

```
tests/integration/
  conftest.py               (existing — extended)
  test_sync_kalshi.py       (new)
  test_sync_manifold.py     (new)
  test_sync_metaculus.py    (new)
  test_sync_polymarket.py   (new)
```

Each test file:
1. Defines a `load_scenarios(connector)` helper that globs `tests/fixtures/<connector>/*.json`
   and returns a list of `pytest.param` objects (id = filename stem).
2. Has a single `@pytest.mark.parametrize` async test function that:
   - Receives the `db` session and the per-connector account fixture.
   - Patches the connector's HTTP client class at `scheduler.sync.<ClientClass>`.
   - Mocks client methods to return the scenario's input data.
   - Calls `sync_one_user(db, user_id)`.
   - Calls `assert_scenario(db, scenario["expected"])` to check the DB.

Example (Kalshi):

```python
@pytest.mark.parametrize("scenario", load_scenarios("kalshi"))
async def test_kalshi_sync(db, kalshi_account, scenario):
    with patch("scheduler.sync.KalshiClient") as MockClient:
        inst = MockClient.return_value
        inst.get_fills = AsyncMock(return_value=scenario["input"]["fills"])
        inst.get_settlements = AsyncMock(return_value=scenario["input"]["settlements"])
        inst.get_market = AsyncMock(
            side_effect=lambda t: scenario["input"]["markets"][t]
        )
        await sync_one_user(db, kalshi_account.user_id)

    await assert_scenario(db, scenario["expected"])
```

### Shared infrastructure (conftest additions)

**Account factory fixtures** — added to `tests/integration/conftest.py`:

One `pytest_asyncio.fixture` per connector. Each inserts a `User` and a `LinkedAccount` row
(with `is_enabled=True`, `is_verified=True`, the correct `Platform` value, and a
test-safe `external_identifier`). Credentials use a placeholder encrypted value since the
client is mocked and `decrypt_credential` is not called in the patched path.

Fixtures: `kalshi_account`, `manifold_account`, `metaculus_account`, `polymarket_account`.
Each yields the `LinkedAccount` ORM object (which carries `.user_id`).

**Assertion helper:**

```python
async def assert_scenario(db: AsyncSession, expected: dict) -> None:
    markets = (await db.execute(select(Market))).scalars().all()
    predictions = (await db.execute(select(Prediction))).scalars().all()

    assert len(markets) == expected["market_count"]
    assert len(predictions) == expected["prediction_count"]

    for exp_m in expected.get("markets", []):
        match = next((m for m in markets if m.external_id == exp_m["external_id"]), None)
        assert match is not None, f"Market {exp_m['external_id']} not found in DB"
        for field, value in exp_m.items():
            actual = getattr(match, field)
            assert actual == pytest.approx(value) if isinstance(value, float) else actual == value

    for i, exp_p in enumerate(expected.get("predictions", [])):
        pred = predictions[i]
        for field, value in exp_p.items():
            actual = getattr(pred, field)
            assert actual == pytest.approx(value) if isinstance(value, float) else actual == value
```

## Error handling

`sync_one_user` already catches per-platform errors and logs them without raising. Tests will
assert `market_count` and `prediction_count` to detect silent failures (a bug that swallows an
error and writes nothing will fail the count assertion).

## Adding a regression case

1. Capture the raw API response that triggered the bug.
2. Write it into a new JSON file in `tests/fixtures/<connector>/`.
3. Add the expected DB state to the same file.
4. Run the tests — the new scenario is automatically picked up by parametrize.
No Python changes required.

## Dependencies and constraints

- Requires the `tiresias_test` Postgres instance (same as other integration tests).
- `CREDENTIAL_ENCRYPTION_KEY` env var must be set to a valid Fernet key; the test conftest can
  set a throwaway value since `decrypt_credential` is not exercised through the mocked client path.
  (Kalshi's `_sync_kalshi` does not call `decrypt_credential` — it reads env vars directly. Other
  connectors do call it, so the conftest must set a valid key.)
- No new package dependencies needed (`unittest.mock` is stdlib).
