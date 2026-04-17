"""
Metaculus end-to-end smoke test.

Runs the full _sync_metaculus path against the live Metaculus API and a real
(local dev) PostgreSQL database, then checks that markets and predictions
landed correctly.

Prerequisites
-------------
1. DB is running and migrations are up to date:
       podman compose up -d db
       cd services/data-layer && DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/tiresias?ssl=disable" PYTHONPATH=. alembic upgrade head

2. A Tiresias user exists with a Metaculus linked account configured:
       is_enabled = true
       is_verified = true
       external_identifier = <your integer Metaculus user ID>
       credential_encrypted = <Fernet-encrypted Metaculus token>
   Use scripts/cred.py to encrypt your token:
       python scripts/cred.py encrypt "your-metaculus-token"
   Then update the DB row (replace UUIDs and values):
       podman exec -it <pg-container> psql -U postgres -d tiresias -c "
         UPDATE linked_accounts
         SET is_enabled=true, is_verified=true,
             external_identifier='<metaculus-integer-id>',
             credential_encrypted='<encrypted-output>'
         WHERE user_id='<tiresias-user-uuid>' AND platform='metaculus';"

3. Environment variables:
       DATABASE_URL  — postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/tiresias?ssl=disable
       CREDENTIAL_ENCRYPTION_KEY — Fernet key matching the credential above

Run
---
   cd <repo-root>
   export DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/tiresias?ssl=disable"
   export CREDENTIAL_ENCRYPTION_KEY="<your-fernet-key>"
   export PYTHONPATH="services/scheduler:services/data-layer:services/connector-metaculus"
   python scripts/test_metaculus_live.py [--user-id <uuid>]

What it checks
--------------
1. At least one enabled+verified Metaculus linked account exists (or uses --user-id).
2. _sync_metaculus runs without raising.
3. At least one Market with source="metaculus" exists in the DB after sync.
4. At least one Prediction with source="metaculus" for the user exists in the DB.
5. All synced predictions have a non-None probability.
6. All synced markets have a non-empty title.
7. Resolved markets have a non-None outcome.

Exit code: 0 on success, 1 on any failure.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("smoke_test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Metaculus sync smoke test")
    p.add_argument(
        "--user-id",
        help="Tiresias user UUID to sync. If omitted, picks the first active Metaculus account.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip DB writes — only verify the API connection and normalisation.",
    )
    return p.parse_args()


def _check_env() -> None:
    import os
    missing = [v for v in ("DATABASE_URL", "CREDENTIAL_ENCRYPTION_KEY") if not os.environ.get(v)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)


# ---------------------------------------------------------------------------
# Phase 1 — API connectivity check
# ---------------------------------------------------------------------------

async def _check_api_connection(token: str, metaculus_user_id: int) -> int:
    """Verify the token is valid and return the total forecast count from the API."""
    from connector_metaculus.client import MetaculusClient

    logger.info("Phase 1: checking Metaculus API connectivity …")
    client = MetaculusClient(token=token)

    # Verify auth via /api/users/me/
    try:
        me = await client.get_current_user()
        logger.info("  Authenticated as: %s (id=%s)", me.get("username"), me.get("id"))
    except Exception as exc:
        logger.error("  /api/users/me/ failed: %s", exc)
        raise

    # Fetch first page to confirm forecaster_id resolves
    posts = await client.get_user_posts(metaculus_user_id)
    logger.info("  Fetched %d posts for forecaster_id=%d", len(posts), metaculus_user_id)
    return len(posts)


# ---------------------------------------------------------------------------
# Phase 2 — Run the sync
# ---------------------------------------------------------------------------

async def _run_sync(db, account) -> int:
    from scheduler.sync import _sync_metaculus

    logger.info(
        "Phase 2: running _sync_metaculus for user %s (metaculus_id=%s) …",
        account.user_id,
        account.external_identifier,
    )
    count = await _sync_metaculus(db, account)
    logger.info("  _sync_metaculus returned count=%d", count)
    return count


# ---------------------------------------------------------------------------
# Phase 3 — DB verification
# ---------------------------------------------------------------------------

async def _verify_db(db, user_id: uuid.UUID) -> list[str]:
    """Run assertions against the DB. Returns a list of failure messages (empty = pass)."""
    from sqlalchemy import select, func
    from data.models.market import Market
    from data.models.prediction import Prediction

    failures: list[str] = []

    # --- Markets ---
    result = await db.execute(
        select(func.count()).where(Market.source == "metaculus")
    )
    market_count = result.scalar_one()
    logger.info("Phase 3: markets with source='metaculus' in DB: %d", market_count)
    if market_count == 0:
        failures.append("No metaculus markets found in DB after sync")

    # All metaculus markets should have a non-empty title
    result = await db.execute(
        select(Market).where(Market.source == "metaculus")
    )
    markets = result.scalars().all()
    for m in markets:
        if not m.title:
            failures.append(f"Market {m.id} (ext={m.external_id}) has empty title")

    # Resolved markets must have an outcome
    resolved_markets = [m for m in markets if m.resolved_at is not None]
    for m in resolved_markets:
        if m.outcome is None:
            failures.append(f"Market {m.id} (ext={m.external_id}) is resolved but has no outcome")

    # --- Predictions ---
    result = await db.execute(
        select(func.count()).where(
            Prediction.user_id == user_id,
            Prediction.source == "metaculus",
        )
    )
    pred_count = result.scalar_one()
    logger.info("Phase 3: predictions with source='metaculus' for user in DB: %d", pred_count)
    if pred_count == 0:
        failures.append(f"No metaculus predictions found in DB for user {user_id}")

    # All predictions should have a non-None probability
    result = await db.execute(
        select(Prediction).where(
            Prediction.user_id == user_id,
            Prediction.source == "metaculus",
        )
    )
    preds = result.scalars().all()
    none_prob_count = sum(1 for p in preds if p.probability is None)
    if none_prob_count:
        failures.append(
            f"{none_prob_count} prediction(s) have probability=None — "
            "my_forecasts may be missing from the API response"
        )

    # Spot-check: each prediction's market should be in the DB
    market_ids = {m.id for m in markets}
    orphaned = [p for p in preds if p.market_id not in market_ids]
    if orphaned:
        failures.append(
            f"{len(orphaned)} prediction(s) reference a market_id not in the metaculus market set"
        )

    # Summary stats
    if preds:
        probs = [p.probability for p in preds if p.probability is not None]
        if probs:
            logger.info(
                "  Probability stats: min=%.3f  max=%.3f  mean=%.3f",
                min(probs),
                max(probs),
                sum(probs) / len(probs),
            )
        scored = sum(1 for p in preds if p.brier_score is not None)
        logger.info(
            "  Scored predictions: %d / %d  (unscored markets not yet resolved)",
            scored,
            len(preds),
        )

    return failures


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> int:
    args = _parse_args()
    _check_env()

    from data.database import db_context
    from data.models.linked_account import LinkedAccount, Platform
    from sqlalchemy import select
    from scheduler.credentials import decrypt_credential

    async with db_context() as db:

        # Locate the linked account
        if args.user_id:
            target_user_id = uuid.UUID(args.user_id)
            result = await db.execute(
                select(LinkedAccount).where(
                    LinkedAccount.user_id == target_user_id,
                    LinkedAccount.platform == Platform.METACULUS,
                )
            )
            account = result.scalar_one_or_none()
            if account is None:
                logger.error("No Metaculus linked account found for user %s", target_user_id)
                return 1
        else:
            result = await db.execute(
                select(LinkedAccount).where(
                    LinkedAccount.platform == Platform.METACULUS,
                    LinkedAccount.is_enabled.is_(True),
                    LinkedAccount.is_verified.is_(True),
                )
            )
            account = result.scalars().first()
            if account is None:
                logger.error(
                    "No enabled+verified Metaculus linked account found in DB. "
                    "Set up one first (see script docstring) or pass --user-id."
                )
                return 1

        target_user_id = account.user_id
        metaculus_user_id_str = account.external_identifier

        logger.info(
            "Found Metaculus account: user=%s  metaculus_id=%s  enabled=%s  verified=%s",
            target_user_id,
            metaculus_user_id_str,
            account.is_enabled,
            account.is_verified,
        )

        if not metaculus_user_id_str:
            logger.error("external_identifier is empty — set the Metaculus integer user ID")
            return 1

        try:
            metaculus_user_id = int(metaculus_user_id_str)
        except ValueError:
            logger.error("external_identifier %r is not a valid integer", metaculus_user_id_str)
            return 1

        token = decrypt_credential(account.credential_encrypted)
        if not token:
            logger.error(
                "Could not decrypt credential — check CREDENTIAL_ENCRYPTION_KEY and the "
                "credential_encrypted column value"
            )
            return 1

        # Phase 1 — API connectivity
        try:
            post_count = await _check_api_connection(token, metaculus_user_id)
        except Exception as exc:
            logger.error("API connectivity check failed: %s", exc)
            return 1

        if args.dry_run:
            logger.info("--dry-run: skipping DB sync and verification")
            logger.info("PASS: API connection OK, %d posts visible", post_count)
            return 0

        # Phase 2 — sync
        try:
            synced_count = await _run_sync(db, account)
        except Exception as exc:
            logger.error("_sync_metaculus raised an unexpected error: %s", exc, exc_info=True)
            return 1

        await db.commit()
        logger.info("DB commit OK — %d predictions upserted", synced_count)

        # Phase 3 — verify
        failures = await _verify_db(db, target_user_id)

    if failures:
        logger.error("FAIL — %d assertion(s) failed:", len(failures))
        for f in failures:
            logger.error("  • %s", f)
        return 1

    logger.info(
        "PASS — sync complete: %d post(s) from API, %d prediction(s) upserted",
        post_count,
        synced_count,
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
