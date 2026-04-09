"""
Integration tests for the data layer CRUD operations.

These tests require a running Postgres instance (podman compose up -d db).
The conftest creates a tiresias_test database and tears it down after the
session, and each test's writes are rolled back for full isolation.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# All tests in this module share the session-scoped event loop so they can
# use the session-scoped db_engine fixture without loop mismatch errors.
pytestmark = pytest.mark.asyncio(loop_scope="session")

from data.crud.user import UserCRUD
from data.crud.market import MarketCRUD
from data.crud.prediction import PredictionCRUD
from data.models.market import MarketOutcome
from data.schemas.user import UserCreate, UserUpdate
from data.schemas.market import MarketCreate
from data.schemas.prediction import PredictionCreate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(suffix: str = "") -> UserCreate:
    return UserCreate(
        email=f"test{suffix}@example.com",
        username=f"testuser{suffix}",
        password="securepassword123",
    )


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

async def test_create_user(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="hashed_pw")
    await db.flush()

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.username == "testuser"
    assert user.is_active is True
    assert user.is_verified is False


async def test_get_user_by_id(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="hashed_pw")
    await db.flush()

    fetched = await UserCRUD.get(db, user.id)
    assert fetched is not None
    assert fetched.id == user.id


async def test_get_user_by_email(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="hashed_pw")
    await db.flush()

    fetched = await UserCRUD.get_by_email(db, "test@example.com")
    assert fetched is not None
    assert fetched.id == user.id


async def test_get_user_by_username(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="hashed_pw")
    await db.flush()

    fetched = await UserCRUD.get_by_username(db, "testuser")
    assert fetched is not None
    assert fetched.id == user.id


async def test_email_exists(db: AsyncSession):
    await UserCRUD.create(db, obj_in=make_user(), hashed_password="hashed_pw")
    await db.flush()

    assert await UserCRUD.email_exists(db, "test@example.com") is True
    assert await UserCRUD.email_exists(db, "nobody@example.com") is False


async def test_username_exists(db: AsyncSession):
    await UserCRUD.create(db, obj_in=make_user(), hashed_password="hashed_pw")
    await db.flush()

    assert await UserCRUD.username_exists(db, "testuser") is True
    assert await UserCRUD.username_exists(db, "phantom") is False


async def test_update_user(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="hashed_pw")
    await db.flush()

    updated = await UserCRUD.update(
        db, db_obj=user, obj_in=UserUpdate(display_name="Test User", bio="Hello world")
    )
    assert updated.display_name == "Test User"
    assert updated.bio == "Hello world"


async def test_verify_email(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="hashed_pw")
    await db.flush()

    assert user.is_verified is False
    verified = await UserCRUD.verify_email(db, user)
    assert verified.is_verified is True


async def test_set_active(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="hashed_pw")
    await db.flush()

    deactivated = await UserCRUD.set_active(db, user, active=False)
    assert deactivated.is_active is False

    reactivated = await UserCRUD.set_active(db, deactivated, active=True)
    assert reactivated.is_active is True


async def test_delete_user(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="hashed_pw")
    await db.flush()

    await UserCRUD.delete(db, id=user.id)
    await db.flush()

    assert await UserCRUD.get(db, user.id) is None


async def test_list_users(db: AsyncSession):
    for i in range(3):
        await UserCRUD.create(db, obj_in=make_user(str(i)), hashed_password="pw")
    await db.flush()

    users = await UserCRUD.list(db)
    assert len(users) == 3


# ---------------------------------------------------------------------------
# Market CRUD
# ---------------------------------------------------------------------------

async def test_create_market(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="pw")
    await db.flush()

    market = await MarketCRUD.create(
        db,
        obj_in=MarketCreate(
            title="Will it rain in SF tomorrow?",
            category="weather",
        ),
        creator_id=user.id,
    )
    await db.flush()

    assert market.id is not None
    assert market.title == "Will it rain in SF tomorrow?"
    assert market.outcome is None
    assert market.is_resolved is False


async def test_market_is_open(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="pw")
    await db.flush()

    market = await MarketCRUD.create(
        db,
        obj_in=MarketCreate(title="Open market?"),
        creator_id=user.id,
    )
    await db.flush()

    assert market.is_open is True


# ---------------------------------------------------------------------------
# Prediction CRUD
# ---------------------------------------------------------------------------

async def test_create_prediction(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="pw")
    await db.flush()
    market = await MarketCRUD.create(
        db, obj_in=MarketCreate(title="Test market"), creator_id=user.id
    )
    await db.flush()

    prediction = await PredictionCRUD.create(
        db,
        obj_in=PredictionCreate(probability=0.75, market_id=market.id),
        user_id=user.id,
    )
    await db.flush()

    assert prediction.id is not None
    assert float(prediction.probability) == pytest.approx(0.75)
    assert prediction.brier_score is None
    assert prediction.is_resolved is False


async def test_brier_score_yes_outcome(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="pw")
    await db.flush()
    market = await MarketCRUD.create(
        db, obj_in=MarketCreate(title="Test market"), creator_id=user.id
    )
    await db.flush()

    prediction = await PredictionCRUD.create(
        db,
        obj_in=PredictionCreate(probability=0.80, market_id=market.id),
        user_id=user.id,
    )
    await db.flush()

    score = prediction.compute_brier_score(outcome_is_yes=True)
    # (0.80 - 1.0)² = 0.04
    assert score == pytest.approx(0.04)
    assert prediction.is_resolved is True


async def test_brier_score_no_outcome(db: AsyncSession):
    user = await UserCRUD.create(db, obj_in=make_user(), hashed_password="pw")
    await db.flush()
    market = await MarketCRUD.create(
        db, obj_in=MarketCreate(title="Test market"), creator_id=user.id
    )
    await db.flush()

    prediction = await PredictionCRUD.create(
        db,
        obj_in=PredictionCreate(probability=0.80, market_id=market.id),
        user_id=user.id,
    )
    await db.flush()

    score = prediction.compute_brier_score(outcome_is_yes=False)
    # (0.80 - 0.0)² = 0.64
    assert score == pytest.approx(0.64)
