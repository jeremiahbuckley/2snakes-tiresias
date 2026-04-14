# notification-service

Dispatches email and push notifications to users based on platform events (badge earned, market resolved, weekly digest). Currently stub implementations — not yet wired to a real provider.

## Tech Stack
- Python 3.12, FastAPI, sqlalchemy (via data-layer)

## Key Files
```
notification_service/
  dispatcher.py   # dispatch(user_id, event_type, context, db) — routes to email or push handler
  templates.py    # TEMPLATES dict — maps event_type → (subject, body) template strings
```

## Entry Point
```python
from notification_service.dispatcher import dispatch
await dispatch(user_id=uuid, event_type="badge_earned", context={"badge_name": "..."}, db=session)
```

## Event Types
- `badge_earned` — triggered after badge issuance
- `market_resolved` — triggered when a tracked market resolves
- `weekly_digest` — scheduled weekly summary

## Status
**Handlers are stubs** — `NotImplementedError` is silently caught in dispatcher. No emails or pushes are actually sent. To implement:
1. Choose a provider (SendGrid, Postmark, etc.)
2. Replace stub in `dispatcher.py` `_send_email()` / `_send_push()`
3. Add provider API key to env vars

## Preferences
- Checks `NotificationPreferences` model before dispatching — respects user opt-outs
- Preferences fetched from `data-layer` via `data.crud` (or direct model query)

## Dependencies
- Imports from `data-layer`: `data.models.notification_preferences`, `data.crud.user`
- Called by `services/scheduler` for digest jobs; called directly by other services for event-driven notifications
