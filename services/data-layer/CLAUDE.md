# data-layer

Shared SQLAlchemy 2.0 models, Alembic migrations, CRUD helpers, and Pydantic schemas used by all backend services. Not a runnable service — imported as a Python package.

## Tech Stack
- Python 3.12, SQLAlchemy 2.0 (async), AsyncPG, Alembic, Pydantic v2

## Key Files
```
data/
  database.py          # AsyncEngine, AsyncSessionLocal, get_db() FastAPI dep, db_context() CM, new_uuid()
  models/
    user.py            # User (id, email, username, display_name, hashed_password)
    market.py          # Market (title, description, resolved_outcome, source, external_id, currency)
    prediction.py      # Prediction (user_id, market_id, probability, placed_at, source, external_id)
    score.py           # UserScore (brier_score, calibration, bss, badge_ids JSONB)
    linked_account.py  # LinkedAccount (kalshi_key, polymarket_wallet, manifold_api_key, metaculus_token — Fernet-encrypted)
    share_token.py     # ShareToken (secret, user_id, public_profile_only)
    notification_preferences.py  # NotificationPreferences (email/push opt-in, frequency, triggers)
  crud/
    base.py            # CRUDBase generic class
    user.py            # create, get_by_email, get_by_username
    market.py          # upsert_from_sync (source + external_id keyed)
    prediction.py      # upsert_from_sync, get_unscored
    score.py           # upsert_user_score
  schemas/             # Pydantic request/response schemas mirroring models
alembic/
  versions/
    0001_initial_schema.py       # 7 tables + indices
    0002_user_settings.py        # Auth & sharing columns
    0003_sync_external_ids.py    # source/external_id columns; upsert support
```

## Usage Pattern
```python
from data.database import get_db, db_context
from data.models.user import User
from data.crud.user import crud_user

# In FastAPI routes (dependency injection):
async def route(db: AsyncSession = Depends(get_db)): ...

# In scripts/jobs (context manager):
async with db_context() as db:
    user = await crud_user.get_by_email(db, email)
```

## DB Connection
- Env var: `DATABASE_URL` (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/tiresias`)
- **Known issue**: Add `?ssl=disable` to DATABASE_URL if asyncpg hangs on connection (Podman/gvproxy SSL negotiation bug)
- Pool: size=10, max_overflow=20, pool_pre_ping=True

## Migrations
```bash
cd services/data-layer
alembic upgrade head   # apply all migrations
alembic revision --autogenerate -m "description"  # create new migration
```

## Patterns
- All models inherit `Base` + `TimestampMixin` (created_at, updated_at auto-managed)
- All PKs are UUID4 (`new_uuid()` helper)
- Sync upserts keyed on `(source, external_id)` — one prediction per market per user
- Fernet encryption for all external API credentials in LinkedAccount
