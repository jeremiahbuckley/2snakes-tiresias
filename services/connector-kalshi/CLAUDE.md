# connector-kalshi

Syncs markets and user predictions from the Kalshi prediction market platform into the shared PostgreSQL database.

## Tech Stack
- Python 3.12, httpx (async HTTP), cryptography (Fernet), sqlalchemy (via data-layer)

## Key Files
```
connector_kalshi/
  client.py    # KalshiClient — async REST client, RSA auth, paginated market/trade fetching
  adapter.py   # normalize_market(), normalize_prediction() — maps Kalshi API shapes to internal dicts
  sync.py      # sync_user_predictions(user_id, db) — orchestrates fetch → normalize → upsert
```

## Entry Point
```python
from connector_kalshi.sync import sync_user_predictions
await sync_user_predictions(user_id=uuid, db=async_session)
```

## Auth
- Kalshi uses RSA private key signing (not simple API keys)
- Key loaded from `KALSHI_API_KEY_ID` + `KALSHI_PRIVATE_KEY` env vars
- Encrypted at rest in `LinkedAccount.kalshi_key`; decrypted via Fernet before each sync

## Adapter Contract
Both normalizers return dicts matching `data/crud/market.py` and `data/crud/prediction.py` upsert signatures:
- Market: `{source: "kalshi", external_id, title, description, resolved_outcome, currency}`
- Prediction: `{source: "kalshi", external_id, user_id, market_id, probability, placed_at}`

## Dependencies
- Imports from `data-layer`: `data.database`, `data.crud.market`, `data.crud.prediction`
- Called by `services/scheduler` (not run standalone)

## Notes
- Upsert keyed on `(source="kalshi", external_id)` — safe to re-run
- Binary markets only (V1); non-binary skipped in adapter
