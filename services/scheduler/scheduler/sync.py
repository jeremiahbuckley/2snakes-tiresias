"""
Per-platform sync helpers.

Each `_sync_<platform>` function:
  1. Extracts the user's identifier and decrypts their credential (where applicable).
  2. Calls the platform's connector client + adapter directly (bypassing the
     sync-module wrappers) so we can pass per-user credentials.
  3. Upserts markets and predictions into the data layer within the provided session.
  4. Returns the number of predictions created/updated.

All functions are idempotent — safe to call multiple times without duplicating data.

`sync_one_user(db, user_id)` is the top-level entry point used by both:
  - sync_user_predictions() on-demand job (single user)
  - sync_all_markets() recurring job (iterates over all users)
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models.linked_account import LinkedAccount, Platform, MARKET_PLATFORMS
from data.crud.market import MarketCRUD
from data.crud.prediction import PredictionCRUD
from .credentials import decrypt_credential

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

async def sync_one_user(db: AsyncSession, user_id: UUID) -> int:
    """
    Sync all linked market accounts for a single user.

    Queries the DB for enabled, verified linked accounts, dispatches to the
    appropriate per-platform helper, and returns the total number of
    predictions upserted across all platforms.

    Errors on individual platforms are caught and logged so one failing
    connector does not abort the others.
    """
    result = await db.execute(
        select(LinkedAccount).where(
            LinkedAccount.user_id == user_id,
            LinkedAccount.is_enabled.is_(True),
            LinkedAccount.is_verified.is_(True),
            LinkedAccount.platform.in_([p.value for p in MARKET_PLATFORMS]),
        )
    )
    accounts = result.scalars().all()

    if not accounts:
        logger.debug("User %s has no active linked market accounts — skipping", user_id)
        return 0

    total = 0
    for account in accounts:
        platform = account.platform
        try:
            if platform == Platform.KALSHI:
                count = await _sync_kalshi(db, account)
            elif platform == Platform.MANIFOLD:
                count = await _sync_manifold(db, account)
            elif platform == Platform.METACULUS:
                count = await _sync_metaculus(db, account)
            elif platform == Platform.POLYMARKET:
                count = await _sync_polymarket(db, account)
            else:
                logger.warning("Unknown market platform %r — skipping", platform)
                count = 0

            logger.info(
                "Synced %d predictions from %s for user %s", count, platform, user_id
            )
            total += count

        except Exception as exc:
            logger.error(
                "Error syncing %s for user %s: %s", platform, user_id, exc, exc_info=True
            )

    return total


# ---------------------------------------------------------------------------
# Per-platform sync helpers
# ---------------------------------------------------------------------------

async def _sync_kalshi(db: AsyncSession, account: LinkedAccount) -> int:
    """
    Sync fills (bets) and settlements for a Kalshi-linked user.

    Kalshi uses RSA-PSS signing for authentication; the private key must be
    available via the KALSHI_PRIVATE_KEY_PATH environment variable. For V1
    a single org-level key is used. Per-user Kalshi credentials require
    passing PEM key bytes to KalshiClient, which is a planned improvement.

    Returns the number of predictions upserted.
    """
    from connector_kalshi.client import KalshiClient
    from connector_kalshi.adapter import normalise_fill, normalise_market, normalise_settlement

    user_id = str(account.user_id)
    logger.info("Syncing Kalshi for user %s", user_id)

    client = KalshiClient()  # reads KALSHI_KEY_ID + KALSHI_PRIVATE_KEY_PATH from env

    # Fetch fills and settlements in parallel-ish (sequential for simplicity)
    raw_fills = await client.get_fills()
    raw_settlements = await client.get_settlements()

    fills = [normalise_fill(f, user_id) for f in raw_fills]
    settlements = [normalise_settlement(s, user_id) for s in raw_settlements]

    # Build a settlement lookup by market ticker for resolution info
    settlement_by_ticker: dict[str, dict] = {}
    for s in settlements:
        ticker = s.get("market_external_id")
        if ticker:
            settlement_by_ticker[ticker] = s

    # Upsert unique markets first
    tickers = {f["market_external_id"] for f in fills if f.get("market_external_id")}
    market_id_map: dict[str, UUID] = {}  # ticker -> internal Market.id

    # Cache event and series lookups so markets in the same event/series share
    # a single API call rather than one per fill.
    event_cache: dict[str, dict] = {}
    series_cache: dict[str, dict] = {}

    for ticker in tickers:
        try:
            raw_market = await client.get_market(ticker)

            # Tags live on the series, not the market endpoint.
            # Walk market → event → series, caching each level.
            series: dict = {}
            event_ticker = raw_market.get("event_ticker")
            if event_ticker:
                if event_ticker not in event_cache:
                    try:
                        event_cache[event_ticker] = await client.get_event(event_ticker)
                    except Exception as exc:
                        logger.warning("Failed to fetch Kalshi event %s: %s", event_ticker, exc)
                        event_cache[event_ticker] = {}
                event = event_cache[event_ticker]
                series_ticker = event.get("series_ticker")
                if series_ticker:
                    if series_ticker not in series_cache:
                        try:
                            series_cache[series_ticker] = await client.get_series(series_ticker)
                        except Exception as exc:
                            logger.warning("Failed to fetch Kalshi series %s: %s", series_ticker, exc)
                            series_cache[series_ticker] = {}
                    series = series_cache.get(series_ticker, {})

            market_norm = normalise_market(raw_market, series=series or None)
            # Enrich with settlement resolution data if available
            if ticker in settlement_by_ticker and not market_norm.get("resolved"):
                settlement = settlement_by_ticker[ticker]
                result = settlement.get("market_result")
                if result:
                    market_norm["resolved"] = True
                    market_norm["outcome"] = result
            market = await MarketCRUD.upsert_from_sync(db, normalized=market_norm)
            market_id_map[ticker] = market.id
        except Exception as exc:
            logger.warning("Failed to sync Kalshi market %s: %s", ticker, exc)

    # Upsert predictions
    count = 0
    for fill in fills:
        ticker = fill.get("market_external_id")
        if not ticker or ticker not in market_id_map:
            continue
        pred = await PredictionCRUD.upsert_from_sync(
            db,
            normalized=fill,
            user_id=account.user_id,
            market_id=market_id_map[ticker],
        )
        if pred is not None:
            count += 1

    return count


async def _sync_manifold(db: AsyncSession, account: LinkedAccount) -> int:
    """
    Sync bets for a Manifold-linked user.

    Manifold's external_identifier is the user's Manifold username.
    The API key is optional for reading public bet history but required for
    private markets; we decrypt and pass it if available.

    Returns the number of predictions upserted.
    """
    from connector_manifold.client import ManifoldClient
    from connector_manifold.adapter import normalise_bet, normalise_market

    user_id = str(account.user_id)
    manifold_username = account.external_identifier

    if not manifold_username:
        logger.warning(
            "No external_identifier (Manifold username) for user %s — skipping", user_id
        )
        return 0

    api_key = decrypt_credential(account.credential_encrypted) or ""
    logger.info("Syncing Manifold for user %s (manifold username: %s)", user_id, manifold_username)

    client = ManifoldClient(api_key=api_key)
    raw_bets = await client.get_user_bets(manifold_username)

    # Filter out redemption bets (automated resolution events, not user decisions)
    bets = [
        normalise_bet(b, user_id)
        for b in raw_bets
        if not b.get("isRedemption", False)
    ]

    # Collect unique Manifold contract IDs
    contract_ids = {
        b["market_external_id"] for b in bets if b.get("market_external_id")
    }

    # Upsert markets
    market_id_map: dict[str, UUID] = {}
    for contract_id in contract_ids:
        try:
            raw_market = await client.get_market(contract_id)
            market_norm = normalise_market(raw_market)
            market = await MarketCRUD.upsert_from_sync(db, normalized=market_norm)
            market_id_map[contract_id] = market.id
        except Exception as exc:
            logger.warning("Failed to sync Manifold market %s: %s", contract_id, exc)

    # Upsert predictions (last bet per market wins, since bets are sorted newest-first)
    count = 0
    seen_markets: set[UUID] = set()
    for bet in bets:
        contract_id = bet.get("market_external_id")
        if not contract_id or contract_id not in market_id_map:
            continue
        internal_market_id = market_id_map[contract_id]
        if internal_market_id in seen_markets:
            # Already upserted a (newer) bet for this market this run
            continue
        pred = await PredictionCRUD.upsert_from_sync(
            db,
            normalized=bet,
            user_id=account.user_id,
            market_id=internal_market_id,
        )
        if pred is not None:
            count += 1
            seen_markets.add(internal_market_id)

    return count


async def _sync_metaculus(db: AsyncSession, account: LinkedAccount) -> int:
    """
    Sync forecasts for a Metaculus-linked user.

    external_identifier is the user's Metaculus integer user ID (stored as string).
    credential_encrypted holds the Metaculus API token (required for all requests).

    Returns the number of predictions upserted.
    """
    from connector_metaculus.client import MetaculusClient
    from connector_metaculus.adapter import normalise_forecast, normalise_market

    user_id = str(account.user_id)
    metaculus_id_str = account.external_identifier

    if not metaculus_id_str:
        logger.warning(
            "No external_identifier (Metaculus user ID) for user %s — skipping", user_id
        )
        return 0

    try:
        metaculus_user_id = int(metaculus_id_str)
    except ValueError:
        logger.error(
            "Invalid Metaculus user ID %r for user %s — skipping", metaculus_id_str, user_id
        )
        return 0

    token = decrypt_credential(account.credential_encrypted)
    if not token:
        logger.warning("No Metaculus token for user %s — skipping", user_id)
        return 0

    logger.info(
        "Syncing Metaculus for user %s (metaculus_id=%d)", user_id, metaculus_user_id
    )

    # Instantiate with per-user token directly (avoids touching env vars)
    client = MetaculusClient(token=token)
    raw_posts = await client.get_user_posts(metaculus_user_id)

    # Identify binary post IDs. The list endpoint does not include my_forecasts
    # (a Metaculus API quirk), so we use these IDs only for discovery and fetch
    # each post individually below — the detail endpoint includes my_forecasts.
    binary_post_ids = [
        post["id"]
        for post in raw_posts
        if (post.get("question") or {}).get("type") == "binary" and post.get("id")
    ]

    # Fetch each binary post individually. The detail endpoint returns my_forecasts,
    # which the list endpoint omits. Use the same response for both market and forecast.
    market_id_map: dict[str, UUID] = {}  # str(post_id) -> internal Market.id
    forecasts = []
    for post_id in binary_post_ids:
        await asyncio.sleep(1.0)  # stay inside ~60 req/min Metaculus rate limit
        try:
            raw_post = await client.get_post(post_id)
            market_norm = normalise_market(raw_post)
            market = await MarketCRUD.upsert_from_sync(db, normalized=market_norm)
            market_id_map[str(post_id)] = market.id
            forecasts.append(normalise_forecast(raw_post, user_id))
        except Exception as exc:
            logger.warning("Failed to sync Metaculus post %s: %s", post_id, exc, exc_info=True)

    # Upsert predictions
    count = 0
    for forecast in forecasts:
        ext_market_id = forecast.get("market_external_id")
        if not ext_market_id or ext_market_id not in market_id_map:
            continue
        pred = await PredictionCRUD.upsert_from_sync(
            db,
            normalized=forecast,
            user_id=account.user_id,
            market_id=market_id_map[ext_market_id],
        )
        if pred is not None:
            count += 1

    return count


async def _sync_polymarket(db: AsyncSession, account: LinkedAccount) -> int:
    """
    Sync trades and closed positions for a Polymarket-linked user.

    Polymarket's read APIs are fully public — no credentials needed.
    external_identifier is the user's Ethereum wallet address.

    Returns the number of predictions upserted.
    """
    from connector_polymarket.client import PolymarketClient
    from connector_polymarket.adapter import (
        normalise_trade,
        normalise_closed_position,
        normalise_market,
    )

    user_id = str(account.user_id)
    wallet_address = account.external_identifier

    if not wallet_address:
        logger.warning(
            "No external_identifier (wallet address) for Polymarket user %s — skipping",
            user_id,
        )
        return 0

    logger.info(
        "Syncing Polymarket for user %s (wallet: %s)", user_id, wallet_address
    )

    client = PolymarketClient()
    raw_trades = await client.get_user_trades(wallet_address)
    raw_closed = await client.get_closed_positions(wallet_address)

    trades = [normalise_trade(t, user_id) for t in raw_trades]
    closed = [normalise_closed_position(c, user_id) for c in raw_closed]

    # Build conditionId -> slug map from trades + closed positions
    # (slug is needed because the Gamma market lookup endpoint uses slugs)
    slug_by_condition: dict[str, str] = {}
    for record in (*trades, *closed):
        cid = record.get("market_external_id")
        slug = record.get("slug")
        if cid and slug:
            slug_by_condition[cid] = slug

    # Upsert markets using slugs
    market_id_map: dict[str, UUID] = {}  # conditionId -> internal Market.id
    for condition_id, slug in slug_by_condition.items():
        try:
            raw_market = await client.get_market_by_slug(slug)
            if raw_market is None:
                logger.warning("Polymarket market %s (slug=%s) not found", condition_id, slug)
                continue
            market_norm = normalise_market(raw_market)
            market = await MarketCRUD.upsert_from_sync(db, normalized=market_norm)
            market_id_map[condition_id] = market.id
        except Exception as exc:
            logger.warning("Failed to sync Polymarket market %s: %s", slug, exc)

    # Upsert predictions from trades (one prediction per market — latest trade wins)
    count = 0
    seen_markets: set[UUID] = set()

    for trade in trades:
        condition_id = trade.get("market_external_id")
        if not condition_id or condition_id not in market_id_map:
            continue
        internal_market_id = market_id_map[condition_id]
        if internal_market_id in seen_markets:
            continue
        pred = await PredictionCRUD.upsert_from_sync(
            db,
            normalized=trade,
            user_id=account.user_id,
            market_id=internal_market_id,
        )
        if pred is not None:
            count += 1
            seen_markets.add(internal_market_id)

    return count
