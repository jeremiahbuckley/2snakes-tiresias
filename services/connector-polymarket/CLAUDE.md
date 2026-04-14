# connector-polymarket

Syncs markets and user positions from Polymarket (CLOB API + Gamma metadata API) into the shared PostgreSQL database.

## Tech Stack
- Python 3.12, httpx (async HTTP), sqlalchemy (via data-layer)

## Key Files
```
connector_polymarket/
  client.py    # PolymarketClient — fetches from both CLOB API and Gamma API; wallet-address-based auth
  adapter.py   # normalize_market(), normalize_prediction() — maps Polymarket shapes to internal dicts
  sync.py      # sync_user_predictions(user_id, db) — orchestrates fetch → normalize → upsert
```

## Entry Point
```python
from connector_polymarket.sync import sync_user_predictions
await sync_user_predictions(user_id=uuid, db=async_session)
```

## Auth
- Polymarket uses wallet address (no API key for public data; wallet address for user positions)
- Wallet address stored in `LinkedAccount.polymarket_wallet`; decrypted via Fernet before sync

## Two APIs
- **Gamma API**: market metadata (title, description, resolution)
- **CLOB API**: user trade history and current positions

## Adapter Contract
Normalizers return dicts matching `data/crud/market.py` and `data/crud/prediction.py` upsert signatures:
- Market: `{source: "polymarket", external_id, title, description, resolved_outcome, currency}`
- Prediction: `{source: "polymarket", external_id, user_id, market_id, probability, placed_at}`

## Dependencies
- Imports from `data-layer`: `data.database`, `data.crud.market`, `data.crud.prediction`
- Called by `services/scheduler` (not run standalone)

## Notes
- Upsert keyed on `(source="polymarket", external_id)` — safe to re-run
- Binary markets only (V1)
