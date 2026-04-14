# badge-service

Defines the badge catalogue and evaluates/issues badges to users based on their scoring data. Exposes a FastAPI router for querying badge state.

## Tech Stack
- Python 3.12, FastAPI, sqlalchemy (via data-layer)

## Key Files
```
badge_service/
  badges.py    # BADGE_CATALOGUE — list of BadgeDefinition(id, name, description, criteria_fn)
  issuer.py    # evaluate_and_issue_badges(user_id, db) — checks all criteria, updates UserScore.badge_ids
  api.py       # FastAPI router — GET /badges (catalogue), GET /users/{user_id}/badges (issued)
```

## Entry Point (programmatic — called by scheduler)
```python
from badge_service.issuer import evaluate_and_issue_badges
await evaluate_and_issue_badges(user_id=uuid, db=async_session)
```

## Entry Point (HTTP — mounted in api-gateway)
```
GET /badges              # list full catalogue
GET /users/{id}/badges   # list badges issued to a user
```

## Badge Storage
- Badge IDs stored as JSONB list on `UserScore.badge_ids`
- Issuer reads current `UserScore`, evaluates all criteria, writes updated list
- Idempotent — re-evaluating never removes earned badges (append-only in V1)

## Adding a New Badge
1. Add a `BadgeDefinition` entry to `BADGE_CATALOGUE` in `badges.py`
2. Implement the `criteria_fn(user_score: UserScore) -> bool` predicate
3. No migration needed — badge IDs stored as free-form JSONB

## Dependencies
- Imports from `data-layer`: `data.crud.score`, `data.models.score.UserScore`
- Router mounted by `services/api-gateway`
- Called by `services/scheduler` after scoring completes
