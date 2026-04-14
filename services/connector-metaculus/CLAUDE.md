# connector-metaculus

Syncs questions and user predictions from Metaculus into the shared PostgreSQL database.

## Tech Stack
- Python 3.12, httpx (async HTTP), sqlalchemy (via data-layer)

## Key Files
```
connector_metaculus/
  client.py    # MetaculusClient — async REST client against www.metaculus.com/api2
  adapter.py   # normalize_market(), normalize_prediction() — maps Metaculus shapes to internal dicts
  sync.py      # sync_user_predictions(user_id, db) — orchestrates fetch → normalize → upsert
```

## Entry Point
```python
from connector_metaculus.sync import sync_user_predictions
await sync_user_predictions(user_id=uuid, db=async_session)
```

## Auth
- Metaculus auth token stored in `LinkedAccount.metaculus_token`; decrypted via Fernet before sync
- Token passed as `Authorization: Token <token>` header

## Adapter Contract
Normalizers return dicts matching `data/crud/market.py` and `data/crud/prediction.py` upsert signatures:
- Market: `{source: "metaculus", external_id, title, description, resolved_outcome, currency}`
- Prediction: `{source: "metaculus", external_id, user_id, market_id, probability, placed_at}`

## Dependencies
- Imports from `data-layer`: `data.database`, `data.crud.market`, `data.crud.prediction`
- Called by `services/scheduler` (not run standalone)

## Notes
- Upsert keyed on `(source="metaculus", external_id)` — safe to re-run
- Metaculus questions can be continuous; binary filter applied in adapter (V1)
- "resolved_outcome" mapped from Metaculus resolution field (YES/NO/AMBIGUOUS)
