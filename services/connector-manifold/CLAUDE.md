# connector-manifold

Syncs markets and user bets from Manifold Markets into the shared PostgreSQL database.

## Tech Stack
- Python 3.12, httpx (async HTTP), sqlalchemy (via data-layer)

## Key Files
```
connector_manifold/
  client.py    # ManifoldClient — async REST client against api.manifold.markets/v0
  adapter.py   # normalize_market(), normalize_prediction() — maps Manifold shapes to internal dicts
  sync.py      # sync_user_predictions(user_id, db) — orchestrates fetch → normalize → upsert
```

## Entry Point
```python
from connector_manifold.sync import sync_user_predictions
await sync_user_predictions(user_id=uuid, db=async_session)
```

## Auth
- Manifold API key (Bearer token) stored in `LinkedAccount.manifold_api_key`; decrypted via Fernet before sync
- Public market data requires no auth; user bet history requires API key

## Adapter Contract
Normalizers return dicts matching `data/crud/market.py` and `data/crud/prediction.py` upsert signatures:
- Market: `{source: "manifold", external_id, title, description, resolved_outcome, currency}`
- Prediction: `{source: "manifold", external_id, user_id, market_id, probability, placed_at}`

## Dependencies
- Imports from `data-layer`: `data.database`, `data.crud.market`, `data.crud.prediction`
- Called by `services/scheduler` (not run standalone)

## Notes
- Upsert keyed on `(source="manifold", external_id)` — safe to re-run
- Manifold uses play-money (Mana); stored as-is, currency field set to "MANA"
