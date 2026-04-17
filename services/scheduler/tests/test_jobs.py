"""
Scheduler job tests.

Strategy
--------
All tests mock the database session and connector functions so that:
  - No live DB or external API is required.
  - The job logic (routing, error handling, notification dispatch) is tested in
    isolation from infrastructure.

Test structure
--------------
test_sync_user_predictions_*  — on-demand sync job
test_sync_all_markets_*       — full-user-base sync job
test_detect_and_score_*       — resolution detection and scoring job
test_rebuild_leaderboard_*    — full score recompute job
test_credentials_*            — credential decryption helpers
test_map_outcome_*            — platform outcome mapping
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_uuid() -> uuid.UUID:
    return uuid.uuid4()


def make_linked_account(
    platform: str = "manifold",
    external_identifier: str = "testuser",
    credential: str | None = None,
    is_enabled: bool = True,
    is_verified: bool = True,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    acct = MagicMock()
    acct.platform = platform
    acct.external_identifier = external_identifier
    acct.credential_encrypted = credential
    acct.is_enabled = is_enabled
    acct.is_verified = is_verified
    acct.user_id = user_id or make_uuid()
    return acct


def make_market(
    market_id: uuid.UUID | None = None,
    outcome: str | None = None,
    title: str = "Test Market",
    source: str = "manifold",
    external_id: str = "abc123",
) -> MagicMock:
    m = MagicMock()
    m.id = market_id or make_uuid()
    m.outcome = outcome
    m.title = title
    m.source = source
    m.external_id = external_id
    m.is_resolved = outcome is not None
    return m


def make_prediction(
    user_id: uuid.UUID | None = None,
    market_id: uuid.UUID | None = None,
    probability: float = 0.7,
    brier_score: float | None = None,
    source: str | None = "manifold",
) -> MagicMock:
    p = MagicMock()
    p.id = make_uuid()
    p.user_id = user_id or make_uuid()
    p.market_id = market_id or make_uuid()
    p.probability = probability
    p.brier_score = brier_score
    p.source = source
    return p


# ---------------------------------------------------------------------------
# credentials tests
# ---------------------------------------------------------------------------

class TestDecryptCredential:

    def test_returns_none_for_empty_input(self):
        from scheduler.credentials import decrypt_credential
        assert decrypt_credential(None) is None
        assert decrypt_credential("") is None

    def test_returns_none_when_key_not_set(self, monkeypatch):
        monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "")
        # Need to reimport to pick up the monkeypatched env at module level
        import importlib
        import scheduler.credentials as cred_mod
        importlib.reload(cred_mod)
        result = cred_mod.decrypt_credential("some_ciphertext")
        assert result is None

    def test_round_trip_encryption(self, monkeypatch):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        f = Fernet(key)
        plaintext = "my-secret-api-key"
        ciphertext = f.encrypt(plaintext.encode()).decode()

        monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", key)
        import importlib
        import scheduler.credentials as cred_mod
        importlib.reload(cred_mod)

        result = cred_mod.decrypt_credential(ciphertext)
        assert result == plaintext

    def test_returns_none_on_invalid_ciphertext(self, monkeypatch):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", key)
        import importlib
        import scheduler.credentials as cred_mod
        importlib.reload(cred_mod)

        result = cred_mod.decrypt_credential("not-valid-fernet-token")
        assert result is None


# ---------------------------------------------------------------------------
# _map_outcome tests
# ---------------------------------------------------------------------------

class TestMapOutcome:

    def test_kalshi_yes(self):
        from data.crud.market import _map_outcome
        from data.models.market import MarketOutcome
        assert _map_outcome("kalshi", "yes") == MarketOutcome.YES

    def test_kalshi_no(self):
        from data.crud.market import _map_outcome
        from data.models.market import MarketOutcome
        assert _map_outcome("kalshi", "no") == MarketOutcome.NO

    def test_manifold_mkt_is_ambiguous(self):
        from data.crud.market import _map_outcome
        from data.models.market import MarketOutcome
        assert _map_outcome("manifold", "MKT") == MarketOutcome.AMBIGUOUS

    def test_manifold_na_is_ambiguous(self):
        from data.crud.market import _map_outcome
        from data.models.market import MarketOutcome
        assert _map_outcome("manifold", "N/A") == MarketOutcome.AMBIGUOUS

    def test_metaculus_annulled_is_ambiguous(self):
        from data.crud.market import _map_outcome
        from data.models.market import MarketOutcome
        assert _map_outcome("metaculus", "annulled") == MarketOutcome.AMBIGUOUS

    def test_polymarket_yes_label(self):
        from data.crud.market import _map_outcome
        from data.models.market import MarketOutcome
        assert _map_outcome("polymarket", "Yes") == MarketOutcome.YES

    def test_polymarket_no_label(self):
        from data.crud.market import _map_outcome
        from data.models.market import MarketOutcome
        assert _map_outcome("polymarket", "No") == MarketOutcome.NO

    def test_polymarket_arbitrary_label_is_ambiguous(self):
        from data.crud.market import _map_outcome
        from data.models.market import MarketOutcome
        assert _map_outcome("polymarket", "Kansas City Chiefs") == MarketOutcome.AMBIGUOUS

    def test_none_input_returns_none(self):
        from data.crud.market import _map_outcome
        assert _map_outcome("kalshi", None) is None

    def test_empty_string_returns_none(self):
        from data.crud.market import _map_outcome
        assert _map_outcome("manifold", "") is None


# ---------------------------------------------------------------------------
# sync_user_predictions tests (on-demand job)
# ---------------------------------------------------------------------------

class TestSyncUserPredictions:

    @pytest.mark.asyncio
    async def test_calls_sync_one_user_with_correct_id(self):
        user_id = make_uuid()

        with (
            patch("scheduler.jobs.db_context") as mock_db_ctx,
            patch("scheduler.sync.sync_one_user", new_callable=AsyncMock) as mock_sync,
        ):
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_sync.return_value = 5

            from scheduler.jobs import sync_user_predictions
            await sync_user_predictions(str(user_id))

            mock_sync.assert_called_once()
            call_args = mock_sync.call_args
            assert call_args.args[1] == user_id  # second arg is uid

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises_value_error(self):
        from scheduler.jobs import sync_user_predictions
        with pytest.raises(ValueError):
            await sync_user_predictions("not-a-uuid")


# ---------------------------------------------------------------------------
# sync_all_markets tests
# ---------------------------------------------------------------------------

class TestSyncAllMarkets:

    @pytest.mark.asyncio
    async def test_syncs_all_active_users(self):
        users = [MagicMock(id=make_uuid()), MagicMock(id=make_uuid())]

        db_mock = AsyncMock()
        db_mock.__aenter__ = AsyncMock(return_value=db_mock)
        db_mock.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("scheduler.jobs.db_context", return_value=db_mock),
            patch("scheduler.jobs.UserCRUD.list_active", new_callable=AsyncMock, return_value=users),
            patch("scheduler.sync.sync_one_user", new_callable=AsyncMock, return_value=3) as mock_sync,
        ):
            from scheduler.jobs import sync_all_markets
            await sync_all_markets()

        assert mock_sync.call_count == len(users)

    @pytest.mark.asyncio
    async def test_continues_after_individual_user_error(self):
        users = [MagicMock(id=make_uuid()), MagicMock(id=make_uuid())]

        db_mock = AsyncMock()
        db_mock.__aenter__ = AsyncMock(return_value=db_mock)
        db_mock.__aexit__ = AsyncMock(return_value=False)

        call_count = 0

        async def failing_sync(db, uid):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Connector timeout")
            return 2

        with (
            patch("scheduler.jobs.db_context", return_value=db_mock),
            patch("scheduler.jobs.UserCRUD.list_active", new_callable=AsyncMock, return_value=users),
            patch("scheduler.sync.sync_one_user", side_effect=failing_sync),
        ):
            from scheduler.jobs import sync_all_markets
            # Should not raise even though first user fails
            await sync_all_markets()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_users_is_noop(self):
        db_mock = AsyncMock()
        db_mock.__aenter__ = AsyncMock(return_value=db_mock)
        db_mock.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("scheduler.jobs.db_context", return_value=db_mock),
            patch("scheduler.jobs.UserCRUD.list_active", new_callable=AsyncMock, return_value=[]),
            patch("scheduler.sync.sync_one_user", new_callable=AsyncMock) as mock_sync,
        ):
            from scheduler.jobs import sync_all_markets
            await sync_all_markets()

        mock_sync.assert_not_called()


# ---------------------------------------------------------------------------
# detect_and_score_resolutions tests
# ---------------------------------------------------------------------------

class TestDetectAndScoreResolutions:

    @pytest.mark.asyncio
    async def test_scores_predictions_for_resolved_market(self):
        from data.models.market import MarketOutcome

        market_id = make_uuid()
        user_id = make_uuid()
        market = make_market(market_id=market_id, outcome=MarketOutcome.YES)
        market.outcome = MarketOutcome.YES

        scored_pred = make_prediction(user_id=user_id, market_id=market_id, brier_score=0.09)

        db_mock = AsyncMock()
        db_mock.__aenter__ = AsyncMock(return_value=db_mock)
        db_mock.__aexit__ = AsyncMock(return_value=False)

        fake_score_result = MagicMock()
        fake_score_result.total_predictions = 1
        fake_score_result.brier_skill_score = 0.6
        fake_score_result.expected_calibration_error = 0.01
        fake_score_result.per_source = {"manifold": 0.09}

        user_score_row = MagicMock()
        user_score_row.badge_ids = []

        with (
            patch("scheduler.jobs.db_context", return_value=db_mock),
            patch("scheduler.jobs.MarketCRUD.list_resolved_with_unscored_predictions",
                  new_callable=AsyncMock, return_value=[market]),
            patch("scheduler.jobs.MarketCRUD.get",
                  new_callable=AsyncMock, return_value=market),
            patch("scheduler.jobs.PredictionCRUD.resolve_all_for_market",
                  new_callable=AsyncMock, return_value=[scored_pred]),
            patch("scheduler.jobs.PredictionCRUD.list_by_user",
                  new_callable=AsyncMock, return_value=[scored_pred]),
            patch("scheduler.jobs.ScoreCRUD.increment_for_user",
                  new_callable=AsyncMock, return_value=user_score_row),
            patch("scoring_engine.engine.score_user", return_value=fake_score_result),
            patch("badge_service.issuer.evaluate_badges", return_value=["first-prediction"]),
            patch("badge_service.issuer.diff_badges",
                  return_value=(["first-prediction"], [])),
            patch("scheduler.jobs._notify_market_resolved", new_callable=AsyncMock),
            patch("scheduler.jobs._notify_badge_earned", new_callable=AsyncMock),
        ):
            from scheduler.jobs import detect_and_score_resolutions
            await detect_and_score_resolutions()  # should not raise

    @pytest.mark.asyncio
    async def test_skips_ambiguous_markets(self):
        from data.models.market import MarketOutcome

        ambiguous_market = make_market(outcome=MarketOutcome.AMBIGUOUS)
        ambiguous_market.outcome = MarketOutcome.AMBIGUOUS

        db_mock = AsyncMock()
        db_mock.__aenter__ = AsyncMock(return_value=db_mock)
        db_mock.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("scheduler.jobs.db_context", return_value=db_mock),
            patch("scheduler.jobs.MarketCRUD.list_resolved_with_unscored_predictions",
                  new_callable=AsyncMock, return_value=[ambiguous_market]),
            patch("scheduler.jobs.MarketCRUD.get",
                  new_callable=AsyncMock, return_value=ambiguous_market),
            patch("scheduler.jobs.PredictionCRUD.resolve_all_for_market",
                  new_callable=AsyncMock) as mock_score,
        ):
            from scheduler.jobs import detect_and_score_resolutions
            await detect_and_score_resolutions()

        mock_score.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_scored_preds_is_noop(self):
        from data.models.market import MarketOutcome

        market = make_market(outcome=MarketOutcome.NO)
        market.outcome = MarketOutcome.NO

        db_mock = AsyncMock()
        db_mock.__aenter__ = AsyncMock(return_value=db_mock)
        db_mock.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("scheduler.jobs.db_context", return_value=db_mock),
            patch("scheduler.jobs.MarketCRUD.list_resolved_with_unscored_predictions",
                  new_callable=AsyncMock, return_value=[market]),
            patch("scheduler.jobs.MarketCRUD.get",
                  new_callable=AsyncMock, return_value=market),
            patch("scheduler.jobs.PredictionCRUD.resolve_all_for_market",
                  new_callable=AsyncMock, return_value=[]),
            patch("scheduler.jobs.ScoreCRUD.increment_for_user",
                  new_callable=AsyncMock) as mock_increment,
        ):
            from scheduler.jobs import detect_and_score_resolutions
            await detect_and_score_resolutions()

        mock_increment.assert_not_called()

    @pytest.mark.asyncio
    async def test_notification_errors_are_non_fatal(self):
        from data.models.market import MarketOutcome
        from notification_service.dispatcher import Notification

        market = make_market(outcome=MarketOutcome.YES)
        market.outcome = MarketOutcome.YES
        user_id = make_uuid()
        scored_pred = make_prediction(user_id=user_id, market_id=market.id, brier_score=0.04)

        db_mock = AsyncMock()
        db_mock.__aenter__ = AsyncMock(return_value=db_mock)
        db_mock.__aexit__ = AsyncMock(return_value=False)

        fake_score_result = MagicMock()
        fake_score_result.total_predictions = 1
        fake_score_result.brier_skill_score = None
        fake_score_result.expected_calibration_error = None
        fake_score_result.per_source = {}

        user_score_row = MagicMock()
        user_score_row.badge_ids = []

        async def raise_on_dispatch(notif):
            raise RuntimeError("Email provider down")

        with (
            patch("scheduler.jobs.db_context", return_value=db_mock),
            patch("scheduler.jobs.MarketCRUD.list_resolved_with_unscored_predictions",
                  new_callable=AsyncMock, return_value=[market]),
            patch("scheduler.jobs.MarketCRUD.get",
                  new_callable=AsyncMock, return_value=market),
            patch("scheduler.jobs.PredictionCRUD.resolve_all_for_market",
                  new_callable=AsyncMock, return_value=[scored_pred]),
            patch("scheduler.jobs.PredictionCRUD.list_by_user",
                  new_callable=AsyncMock, return_value=[scored_pred]),
            patch("scheduler.jobs.ScoreCRUD.increment_for_user",
                  new_callable=AsyncMock, return_value=user_score_row),
            patch("scoring_engine.engine.score_user", return_value=fake_score_result),
            patch("badge_service.issuer.evaluate_badges", return_value=[]),
            patch("badge_service.issuer.diff_badges", return_value=([], [])),
            patch("scheduler.jobs._notify_market_resolved",
                  new_callable=AsyncMock, side_effect=RuntimeError("boom")),
        ):
            from scheduler.jobs import detect_and_score_resolutions
            # Should not propagate the notification error
            await detect_and_score_resolutions()


# ---------------------------------------------------------------------------
# rebuild_leaderboard tests
# ---------------------------------------------------------------------------

class TestRebuildLeaderboard:

    @pytest.mark.asyncio
    async def test_calls_rebuild_for_each_user(self):
        users = [MagicMock(id=make_uuid()) for _ in range(3)]

        db_mock = AsyncMock()
        db_mock.__aenter__ = AsyncMock(return_value=db_mock)
        db_mock.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("scheduler.jobs.db_context", return_value=db_mock),
            patch("scheduler.jobs.UserCRUD.list_active",
                  new_callable=AsyncMock, return_value=users),
            patch("scheduler.jobs.ScoreCRUD.rebuild_for_user",
                  new_callable=AsyncMock) as mock_rebuild,
        ):
            from scheduler.jobs import rebuild_leaderboard
            await rebuild_leaderboard()

        assert mock_rebuild.call_count == len(users)

    @pytest.mark.asyncio
    async def test_continues_after_individual_user_error(self):
        users = [MagicMock(id=make_uuid()) for _ in range(3)]

        db_mock = AsyncMock()
        db_mock.__aenter__ = AsyncMock(return_value=db_mock)
        db_mock.__aexit__ = AsyncMock(return_value=False)

        call_count = 0

        async def failing_rebuild(db, uid):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("DB constraint violation")

        with (
            patch("scheduler.jobs.db_context", return_value=db_mock),
            patch("scheduler.jobs.UserCRUD.list_active",
                  new_callable=AsyncMock, return_value=users),
            patch("scheduler.jobs.ScoreCRUD.rebuild_for_user",
                  side_effect=failing_rebuild),
        ):
            from scheduler.jobs import rebuild_leaderboard
            await rebuild_leaderboard()  # should not raise

        assert call_count == 3  # all users attempted


# ---------------------------------------------------------------------------
# sync.py helper tests (per-platform)
# ---------------------------------------------------------------------------

class TestSyncOneUser:

    @pytest.mark.asyncio
    async def test_no_accounts_returns_zero(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))

        from scheduler.sync import sync_one_user
        result = await sync_one_user(db, make_uuid())
        assert result == 0

    @pytest.mark.asyncio
    async def test_error_in_platform_does_not_abort_others(self):
        manifold_account = make_linked_account(platform="manifold")
        metaculus_account = make_linked_account(platform="metaculus")
        user_id = manifold_account.user_id

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            manifold_account, metaculus_account
        ]
        db.execute = AsyncMock(return_value=mock_result)

        async def mock_manifold_sync(db, acct):
            raise RuntimeError("Manifold is down")

        async def mock_metaculus_sync(db, acct):
            return 4

        with (
            patch("scheduler.sync._sync_manifold", side_effect=mock_manifold_sync),
            patch("scheduler.sync._sync_metaculus", side_effect=mock_metaculus_sync),
        ):
            from scheduler.sync import sync_one_user
            result = await sync_one_user(db, user_id)

        # Only metaculus succeeded; total = 4
        assert result == 4


class TestSyncManifold:

    @pytest.mark.asyncio
    async def test_skips_when_no_external_identifier(self):
        acct = make_linked_account(platform="manifold", external_identifier="")
        db = AsyncMock()

        from scheduler.sync import _sync_manifold
        result = await _sync_manifold(db, acct)
        assert result == 0

    @pytest.mark.asyncio
    async def test_upserts_markets_and_predictions(self):
        user_id = make_uuid()
        acct = make_linked_account(
            platform="manifold",
            external_identifier="alice",
            user_id=user_id,
        )
        db = AsyncMock()

        market_id = make_uuid()

        raw_bets = [
            {
                "id": "bet1",
                "contractId": "market_ext_1",
                "isRedemption": False,
                "outcome": "YES",
                "probBefore": 0.65,
                "probAfter": 0.67,
                "amount": 50,
                "createdTime": 1700000000000,
            }
        ]
        market_norm = {
            "external_id": "market_ext_1",
            "source": "manifold",
            "title": "Will X happen?",
            "resolved": True,
            "outcome": "YES",
        }

        mock_market = make_market(market_id=market_id)
        mock_pred = make_prediction(user_id=user_id, market_id=market_id)

        with (
            patch(
                "connector_manifold.client.ManifoldClient.get_user_bets",
                new_callable=AsyncMock,
                return_value=raw_bets,
            ),
            patch(
                "connector_manifold.client.ManifoldClient.get_market",
                new_callable=AsyncMock,
                return_value={"id": "market_ext_1", "question": "Will X happen?", "isResolved": True, "resolution": "YES"},
            ),
            patch(
                "data.crud.market.MarketCRUD.upsert_from_sync",
                new_callable=AsyncMock,
                return_value=mock_market,
            ),
            patch(
                "data.crud.prediction.PredictionCRUD.upsert_from_sync",
                new_callable=AsyncMock,
                return_value=mock_pred,
            ),
        ):
            from scheduler.sync import _sync_manifold
            count = await _sync_manifold(db, acct)

        assert count == 1


class TestSyncPolymarket:

    @pytest.mark.asyncio
    async def test_skips_when_no_wallet_address(self):
        acct = make_linked_account(platform="polymarket", external_identifier="")
        db = AsyncMock()

        from scheduler.sync import _sync_polymarket
        result = await _sync_polymarket(db, acct)
        assert result == 0


class TestSyncMetaculus:

    @pytest.mark.asyncio
    async def test_skips_when_no_token(self):
        acct = make_linked_account(
            platform="metaculus",
            external_identifier="12345",
            credential=None,
        )
        db = AsyncMock()

        with patch("scheduler.sync.decrypt_credential", return_value=None):
            from scheduler.sync import _sync_metaculus
            result = await _sync_metaculus(db, acct)

        assert result == 0

    @pytest.mark.asyncio
    async def test_skips_when_invalid_user_id(self):
        acct = make_linked_account(
            platform="metaculus",
            external_identifier="not-an-integer",
            credential="encrypted",
        )
        db = AsyncMock()

        with patch("scheduler.sync.decrypt_credential", return_value="valid-token"):
            from scheduler.sync import _sync_metaculus
            result = await _sync_metaculus(db, acct)

        assert result == 0

    @pytest.mark.asyncio
    async def test_skips_when_no_external_identifier(self):
        acct = make_linked_account(
            platform="metaculus",
            external_identifier="",
            credential="encrypted",
        )
        db = AsyncMock()

        with patch("scheduler.sync.decrypt_credential", return_value="valid-token"):
            from scheduler.sync import _sync_metaculus
            result = await _sync_metaculus(db, acct)

        assert result == 0

    @pytest.mark.asyncio
    async def test_happy_path_upserts_markets_and_predictions(self):
        """Full path: posts fetched → markets upserted → predictions upserted → count returned."""
        user_id = make_uuid()
        acct = make_linked_account(
            platform="metaculus",
            external_identifier="98765",
            credential="encrypted-token",
            user_id=user_id,
        )
        db = AsyncMock()

        binary_post = {
            "id": 201,
            "title": "Will fusion power be commercially viable before 2035?",
            "resolved": False,
            "categories": [{"id": 1, "name": "Science", "slug": "science", "description": ""}],
            "question": {
                "id": 301,
                "type": "binary",
                "status": "open",
                "resolution": None,
                "actual_close_time": None,
                "scheduled_close_time": "2034-12-31T23:59:59Z",
                "actual_resolve_time": None,
                "scheduled_resolve_time": "2035-06-01T00:00:00Z",
                "my_forecasts": [
                    {"probability_yes": 0.20, "start_time": "2025-02-01T00:00:00Z", "end_time": None},
                ],
            },
        }

        market_id = make_uuid()
        mock_market = make_market(market_id=market_id, source="metaculus", external_id="201")
        mock_pred = make_prediction(user_id=user_id, market_id=market_id, source="metaculus")

        with (
            patch("scheduler.sync.decrypt_credential", return_value="raw-token"),
            patch(
                "connector_metaculus.client.MetaculusClient.get_user_posts",
                new_callable=AsyncMock,
                return_value=[binary_post],
            ),
            patch(
                "connector_metaculus.client.MetaculusClient.get_post",
                new_callable=AsyncMock,
                return_value=binary_post,
            ),
            patch(
                "data.crud.market.MarketCRUD.upsert_from_sync",
                new_callable=AsyncMock,
                return_value=mock_market,
            ) as mock_market_upsert,
            patch(
                "data.crud.prediction.PredictionCRUD.upsert_from_sync",
                new_callable=AsyncMock,
                return_value=mock_pred,
            ) as mock_pred_upsert,
        ):
            from scheduler.sync import _sync_metaculus
            count = await _sync_metaculus(db, acct)

        assert count == 1
        mock_market_upsert.assert_called_once()
        mock_pred_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_per_user_token_not_env_var(self):
        """The decrypted token is passed directly to MetaculusClient, not via env var."""
        user_id = make_uuid()
        acct = make_linked_account(
            platform="metaculus",
            external_identifier="55555",
            credential="fernet-ciphertext",
            user_id=user_id,
        )
        db = AsyncMock()

        captured_token = []

        def capture_client_init(self, token):
            captured_token.append(token)
            self._base = "https://www.metaculus.com"
            self._headers = {"Authorization": f"Token {token}"}

        with (
            patch("scheduler.sync.decrypt_credential", return_value="decrypted-secret"),
            patch("connector_metaculus.client.MetaculusClient.__init__", capture_client_init),
            patch(
                "connector_metaculus.client.MetaculusClient.get_user_posts",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            from scheduler.sync import _sync_metaculus
            await _sync_metaculus(db, acct)

        assert captured_token == ["decrypted-secret"]

    @pytest.mark.asyncio
    async def test_non_binary_posts_are_skipped(self):
        """Posts with numeric/multiple_choice questions produce no predictions."""
        user_id = make_uuid()
        acct = make_linked_account(
            platform="metaculus",
            external_identifier="77777",
            credential="enc",
            user_id=user_id,
        )
        db = AsyncMock()

        numeric_post = {
            "id": 501,
            "title": "What temperature in 2030?",
            "resolved": False,
            "categories": [],
            "question": {
                "id": 601,
                "type": "numeric",
                "status": "open",
                "resolution": None,
                "my_forecasts": [
                    {"probability_yes": None, "start_time": "2025-01-01T00:00:00Z", "end_time": None},
                ],
            },
        }

        with (
            patch("scheduler.sync.decrypt_credential", return_value="tok"),
            patch(
                "connector_metaculus.client.MetaculusClient.get_user_posts",
                new_callable=AsyncMock,
                return_value=[numeric_post],
            ),
            patch(
                "data.crud.market.MarketCRUD.upsert_from_sync",
                new_callable=AsyncMock,
            ) as mock_market_upsert,
            patch(
                "data.crud.prediction.PredictionCRUD.upsert_from_sync",
                new_callable=AsyncMock,
            ) as mock_pred_upsert,
        ):
            from scheduler.sync import _sync_metaculus
            count = await _sync_metaculus(db, acct)

        assert count == 0
        mock_market_upsert.assert_not_called()
        mock_pred_upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_market_fetch_failure_skips_prediction_but_continues(self):
        """If get_post raises for a market, that market+prediction is skipped but sync continues."""
        user_id = make_uuid()
        acct = make_linked_account(
            platform="metaculus",
            external_identifier="22222",
            credential="enc",
            user_id=user_id,
        )
        db = AsyncMock()

        post_a = {
            "id": 301,
            "title": "Post A",
            "resolved": False,
            "categories": [],
            "question": {
                "id": 401,
                "type": "binary",
                "status": "open",
                "resolution": None,
                "actual_close_time": None,
                "scheduled_close_time": "2027-01-01T00:00:00Z",
                "my_forecasts": [{"probability_yes": 0.4, "start_time": "2025-01-01T00:00:00Z", "end_time": None}],
            },
        }
        post_b = {
            "id": 302,
            "title": "Post B",
            "resolved": False,
            "categories": [],
            "question": {
                "id": 402,
                "type": "binary",
                "status": "open",
                "resolution": None,
                "actual_close_time": None,
                "scheduled_close_time": "2027-06-01T00:00:00Z",
                "my_forecasts": [{"probability_yes": 0.7, "start_time": "2025-01-01T00:00:00Z", "end_time": None}],
            },
        }

        market_id_b = make_uuid()
        mock_market_b = make_market(market_id=market_id_b, source="metaculus", external_id="302")
        mock_pred_b = make_prediction(user_id=user_id, market_id=market_id_b, source="metaculus")

        async def get_post_side_effect(post_id):
            if post_id == 301:
                raise Exception("HTTP 404 — post not found")
            return post_b

        with (
            patch("scheduler.sync.decrypt_credential", return_value="tok"),
            patch(
                "connector_metaculus.client.MetaculusClient.get_user_posts",
                new_callable=AsyncMock,
                return_value=[post_a, post_b],
            ),
            patch(
                "connector_metaculus.client.MetaculusClient.get_post",
                new_callable=AsyncMock,
                side_effect=get_post_side_effect,
            ),
            patch(
                "data.crud.market.MarketCRUD.upsert_from_sync",
                new_callable=AsyncMock,
                return_value=mock_market_b,
            ) as mock_market_upsert,
            patch(
                "data.crud.prediction.PredictionCRUD.upsert_from_sync",
                new_callable=AsyncMock,
                return_value=mock_pred_b,
            ) as mock_pred_upsert,
        ):
            from scheduler.sync import _sync_metaculus
            count = await _sync_metaculus(db, acct)

        # post_a market fetch failed → skipped; post_b succeeded → 1 prediction
        assert count == 1
        mock_market_upsert.assert_called_once()
        mock_pred_upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_prediction_with_none_probability_is_skipped(self):
        """A forecast with no probability (empty my_forecasts) produces count=0."""
        user_id = make_uuid()
        acct = make_linked_account(
            platform="metaculus",
            external_identifier="33333",
            credential="enc",
            user_id=user_id,
        )
        db = AsyncMock()

        post_no_forecast = {
            "id": 401,
            "title": "Some question",
            "resolved": False,
            "categories": [],
            "question": {
                "id": 501,
                "type": "binary",
                "status": "open",
                "resolution": None,
                "actual_close_time": None,
                "scheduled_close_time": "2027-01-01T00:00:00Z",
                "my_forecasts": [],  # empty → probability_yes=None → upsert skipped
            },
        }

        market_id = make_uuid()
        mock_market = make_market(market_id=market_id, source="metaculus", external_id="401")

        with (
            patch("scheduler.sync.decrypt_credential", return_value="tok"),
            patch(
                "connector_metaculus.client.MetaculusClient.get_user_posts",
                new_callable=AsyncMock,
                return_value=[post_no_forecast],
            ),
            patch(
                "connector_metaculus.client.MetaculusClient.get_post",
                new_callable=AsyncMock,
                return_value=post_no_forecast,
            ),
            patch(
                "data.crud.market.MarketCRUD.upsert_from_sync",
                new_callable=AsyncMock,
                return_value=mock_market,
            ),
            patch(
                "data.crud.prediction.PredictionCRUD.upsert_from_sync",
                new_callable=AsyncMock,
                return_value=None,  # upsert_from_sync returns None when probability is None
            ) as mock_pred_upsert,
        ):
            from scheduler.sync import _sync_metaculus
            count = await _sync_metaculus(db, acct)

        assert count == 0

    @pytest.mark.asyncio
    async def test_multiple_posts_all_succeed(self):
        """Three binary posts → three markets upserted, three predictions returned."""
        user_id = make_uuid()
        acct = make_linked_account(
            platform="metaculus",
            external_identifier="44444",
            credential="enc",
            user_id=user_id,
        )
        db = AsyncMock()

        def make_post(post_id: int, prob: float) -> dict:
            return {
                "id": post_id,
                "title": f"Post {post_id}",
                "resolved": False,
                "categories": [],
                "question": {
                    "id": post_id + 10000,
                    "type": "binary",
                    "status": "open",
                    "resolution": None,
                    "actual_close_time": None,
                    "scheduled_close_time": "2027-01-01T00:00:00Z",
                    "my_forecasts": [
                        {"probability_yes": prob, "start_time": "2025-01-01T00:00:00Z", "end_time": None}
                    ],
                },
            }

        posts = [make_post(1001, 0.3), make_post(1002, 0.5), make_post(1003, 0.8)]

        def make_mock_market(post_id):
            return make_market(source="metaculus", external_id=str(post_id))

        def make_mock_pred():
            return make_prediction(user_id=user_id, source="metaculus")

        with (
            patch("scheduler.sync.decrypt_credential", return_value="tok"),
            patch(
                "connector_metaculus.client.MetaculusClient.get_user_posts",
                new_callable=AsyncMock,
                return_value=posts,
            ),
            patch(
                "connector_metaculus.client.MetaculusClient.get_post",
                new_callable=AsyncMock,
                side_effect=lambda pid: posts[[p["id"] for p in posts].index(pid)],
            ),
            patch(
                "data.crud.market.MarketCRUD.upsert_from_sync",
                new_callable=AsyncMock,
                side_effect=lambda db, normalized: make_mock_market(int(normalized["external_id"])),
            ),
            patch(
                "data.crud.prediction.PredictionCRUD.upsert_from_sync",
                new_callable=AsyncMock,
                return_value=make_mock_pred(),
            ),
        ):
            from scheduler.sync import _sync_metaculus
            count = await _sync_metaculus(db, acct)

        assert count == 3
