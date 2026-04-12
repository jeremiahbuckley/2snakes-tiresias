"""
Auth & user-settings FastAPI router.

Auth endpoints:
  POST /auth/register                    — create account + issue JWT
  POST /auth/login                       — exchange credentials for JWT
  GET  /auth/me                          — current user info
  PATCH /auth/me/profile                 — update display name, bio, avatar

Linked-account endpoints (market sources + social publishing targets):
  GET    /auth/me/linked-accounts                 — list all linked accounts
  PUT    /auth/me/linked-accounts/{platform}      — add or update a linked account
  PATCH  /auth/me/linked-accounts/{platform}      — toggle is_enabled
  DELETE /auth/me/linked-accounts/{platform}      — remove a linked account

Share-token endpoints (anonymous sharing):
  GET    /auth/me/share-tokens           — list active share tokens
  POST   /auth/me/share-tokens           — generate a new share token
  DELETE /auth/me/share-tokens/{token}   — deactivate a share token

Notification-preference endpoint:
  GET    /auth/me/notifications          — get email notification prefs
  PATCH  /auth/me/notifications          — update email notification prefs
"""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.database import get_db
from data.models.linked_account import LinkedAccount, Platform, platform_type, MARKET_PLATFORMS
from data.models.notification_preferences import NotificationPreferences
from data.models.share_token import ShareToken, generate_token
from data.models.user import User

from .jwt import create_access_token, decode_access_token
from .linked_accounts import Platform  # re-export for pydantic validators

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer()

# ---------------------------------------------------------------------------
# Shorthand type aliases
# ---------------------------------------------------------------------------

DB = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Auth dependency — validates JWT and returns the authenticated user
# ---------------------------------------------------------------------------

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Schemas — Auth
# ---------------------------------------------------------------------------

class RegisterIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8)
    display_name: Optional[str] = Field(default=None, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    display_name: Optional[str]
    bio: Optional[str]
    avatar_url: Optional[str]
    is_verified: bool

    @classmethod
    def from_orm(cls, user: User) -> "UserOut":
        return cls(
            id=str(user.id),
            email=user.email,
            username=user.username,
            display_name=user.display_name,
            bio=user.bio,
            avatar_url=user.avatar_url,
            is_verified=user.is_verified,
        )


class ProfileIn(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=128)
    bio: Optional[str] = Field(default=None, max_length=2000)
    avatar_url: Optional[str] = Field(default=None, max_length=2048)


# ---------------------------------------------------------------------------
# Schemas — Linked accounts
# ---------------------------------------------------------------------------

class LinkedAccountIn(BaseModel):
    external_identifier: str = Field(max_length=256)
    credential: str = Field(description="API key, OAuth token, or app password (plaintext — encrypted server-side)")
    is_enabled: bool = True


class LinkedAccountToggleIn(BaseModel):
    is_enabled: bool


class LinkedAccountOut(BaseModel):
    platform: str
    platform_type: str
    external_identifier: Optional[str]
    is_enabled: bool
    is_verified: bool
    linked_at: str  # ISO-8601

    @classmethod
    def from_orm(cls, acct: LinkedAccount) -> "LinkedAccountOut":
        return cls(
            platform=acct.platform,
            platform_type=acct.platform_type,
            external_identifier=acct.external_identifier,
            is_enabled=acct.is_enabled,
            is_verified=acct.is_verified,
            linked_at=acct.created_at.isoformat(),
        )


# ---------------------------------------------------------------------------
# Schemas — Share tokens
# ---------------------------------------------------------------------------

class ShareTokenIn(BaseModel):
    label: Optional[str] = Field(default=None, max_length=128)
    show_scores: bool = True
    show_badges: bool = True
    show_predictions: bool = False


class ShareTokenOut(BaseModel):
    token: str
    label: Optional[str]
    show_scores: bool
    show_badges: bool
    show_predictions: bool
    is_active: bool
    created_at: str

    @classmethod
    def from_orm(cls, t: ShareToken) -> "ShareTokenOut":
        return cls(
            token=t.token,
            label=t.label,
            show_scores=t.show_scores,
            show_badges=t.show_badges,
            show_predictions=t.show_predictions,
            is_active=t.is_active,
            created_at=t.created_at.isoformat(),
        )


# ---------------------------------------------------------------------------
# Schemas — Notification preferences
# ---------------------------------------------------------------------------

class NotificationPrefsOut(BaseModel):
    email_on_resolution: bool
    email_on_badge: bool
    email_on_rank_change: bool


class NotificationPrefsIn(BaseModel):
    email_on_resolution: Optional[bool] = None
    email_on_badge: Optional[bool] = None
    email_on_rank_change: Optional[bool] = None


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, db: DB) -> TokenOut:
    """Create a new account and return a JWT."""
    # Check for conflicts
    existing_email = await db.execute(select(User).where(User.email == body.email))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    existing_username = await db.execute(select(User).where(User.username == body.username))
    if existing_username.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
        display_name=body.display_name or body.username,
    )
    db.add(user)
    await db.flush()  # assigns user.id before creating prefs

    # Create default notification preferences
    prefs = NotificationPreferences(user_id=user.id)
    db.add(prefs)

    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    return TokenOut(access_token=token, token_type="bearer", user_id=str(user.id))


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db: DB) -> TokenOut:
    """Exchange email + password for a JWT."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    token = create_access_token(str(user.id))
    return TokenOut(access_token=token, token_type="bearer", user_id=str(user.id))


@router.get("/me", response_model=UserOut)
async def get_me(current_user: CurrentUser) -> UserOut:
    """Return the authenticated user's profile."""
    return UserOut.from_orm(current_user)


@router.patch("/me/profile", response_model=UserOut)
async def update_profile(body: ProfileIn, current_user: CurrentUser, db: DB) -> UserOut:
    """Update display name, bio, and/or avatar URL."""
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.bio is not None:
        current_user.bio = body.bio
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    await db.commit()
    await db.refresh(current_user)
    return UserOut.from_orm(current_user)


# ---------------------------------------------------------------------------
# Linked account routes
# ---------------------------------------------------------------------------

@router.get("/me/linked-accounts", response_model=list[LinkedAccountOut])
async def list_linked_accounts(current_user: CurrentUser, db: DB) -> list[LinkedAccountOut]:
    """Return all linked accounts for the current user (markets + social)."""
    result = await db.execute(
        select(LinkedAccount).where(LinkedAccount.user_id == current_user.id)
    )
    accounts = result.scalars().all()
    return [LinkedAccountOut.from_orm(a) for a in accounts]


@router.put("/me/linked-accounts/{platform}", response_model=LinkedAccountOut)
async def upsert_linked_account(
    platform: Platform,
    body: LinkedAccountIn,
    current_user: CurrentUser,
    db: DB,
) -> LinkedAccountOut:
    """
    Add or update a linked account for the given platform.

    Credentials are accepted in plaintext and must be encrypted before
    being persisted.  TODO: integrate Fernet encryption here.

    Verification against the external platform API is attempted but
    failures are non-fatal during development (is_verified stays False).
    """
    result = await db.execute(
        select(LinkedAccount).where(
            LinkedAccount.user_id == current_user.id,
            LinkedAccount.platform == platform.value,
        )
    )
    account = result.scalar_one_or_none()

    # TODO: encrypt body.credential before storing
    encrypted_credential = body.credential  # placeholder — swap for Fernet encrypt()

    if account is None:
        account = LinkedAccount(
            user_id=current_user.id,
            platform=platform.value,
            platform_type=platform_type(platform).value,
            external_identifier=body.external_identifier,
            credential_encrypted=encrypted_credential,
            is_enabled=body.is_enabled,
        )
        db.add(account)
    else:
        account.external_identifier = body.external_identifier
        account.credential_encrypted = encrypted_credential
        account.is_enabled = body.is_enabled
        account.is_verified = False  # re-verify after credential change

    await db.commit()
    await db.refresh(account)
    return LinkedAccountOut.from_orm(account)


@router.patch("/me/linked-accounts/{platform}", response_model=LinkedAccountOut)
async def toggle_linked_account(
    platform: Platform,
    body: LinkedAccountToggleIn,
    current_user: CurrentUser,
    db: DB,
) -> LinkedAccountOut:
    """Enable or disable data pull/push for a linked platform without changing credentials."""
    result = await db.execute(
        select(LinkedAccount).where(
            LinkedAccount.user_id == current_user.id,
            LinkedAccount.platform == platform.value,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No linked account found for platform '{platform}'",
        )

    account.is_enabled = body.is_enabled
    await db.commit()
    await db.refresh(account)
    return LinkedAccountOut.from_orm(account)


@router.delete("/me/linked-accounts/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_linked_account(
    platform: Platform,
    current_user: CurrentUser,
    db: DB,
) -> None:
    """Remove a linked account and its stored credential."""
    result = await db.execute(
        select(LinkedAccount).where(
            LinkedAccount.user_id == current_user.id,
            LinkedAccount.platform == platform.value,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No linked account found for platform '{platform}'",
        )
    await db.delete(account)
    await db.commit()


# ---------------------------------------------------------------------------
# Share-token routes
# ---------------------------------------------------------------------------

@router.get("/me/share-tokens", response_model=list[ShareTokenOut])
async def list_share_tokens(current_user: CurrentUser, db: DB) -> list[ShareTokenOut]:
    """Return all active share tokens for the current user."""
    result = await db.execute(
        select(ShareToken).where(
            ShareToken.user_id == current_user.id,
            ShareToken.is_active == True,  # noqa: E712
        )
    )
    tokens = result.scalars().all()
    return [ShareTokenOut.from_orm(t) for t in tokens]


@router.post("/me/share-tokens", response_model=ShareTokenOut, status_code=status.HTTP_201_CREATED)
async def create_share_token(
    body: ShareTokenIn,
    current_user: CurrentUser,
    db: DB,
) -> ShareTokenOut:
    """Generate a new anonymous share link."""
    token = ShareToken(
        user_id=current_user.id,
        token=generate_token(),
        label=body.label,
        show_scores=body.show_scores,
        show_badges=body.show_badges,
        show_predictions=body.show_predictions,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return ShareTokenOut.from_orm(token)


@router.delete("/me/share-tokens/{token_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share_token(
    token_slug: str,
    current_user: CurrentUser,
    db: DB,
) -> None:
    """Deactivate (soft-delete) a share token so its URL stops resolving."""
    result = await db.execute(
        select(ShareToken).where(
            ShareToken.token == token_slug,
            ShareToken.user_id == current_user.id,
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share token not found")
    token.is_active = False
    await db.commit()


# ---------------------------------------------------------------------------
# Notification preferences routes
# ---------------------------------------------------------------------------

@router.get("/me/notifications", response_model=NotificationPrefsOut)
async def get_notification_prefs(current_user: CurrentUser, db: DB) -> NotificationPrefsOut:
    """Return email notification preferences for the current user."""
    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs is None:
        # Create defaults on demand (handles accounts created before migration)
        prefs = NotificationPreferences(user_id=current_user.id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)

    return NotificationPrefsOut(
        email_on_resolution=prefs.email_on_resolution,
        email_on_badge=prefs.email_on_badge,
        email_on_rank_change=prefs.email_on_rank_change,
    )


@router.patch("/me/notifications", response_model=NotificationPrefsOut)
async def update_notification_prefs(
    body: NotificationPrefsIn,
    current_user: CurrentUser,
    db: DB,
) -> NotificationPrefsOut:
    """Update one or more email notification toggles (partial update)."""
    result = await db.execute(
        select(NotificationPreferences).where(NotificationPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs is None:
        prefs = NotificationPreferences(user_id=current_user.id)
        db.add(prefs)

    if body.email_on_resolution is not None:
        prefs.email_on_resolution = body.email_on_resolution
    if body.email_on_badge is not None:
        prefs.email_on_badge = body.email_on_badge
    if body.email_on_rank_change is not None:
        prefs.email_on_rank_change = body.email_on_rank_change

    await db.commit()
    await db.refresh(prefs)

    return NotificationPrefsOut(
        email_on_resolution=prefs.email_on_resolution,
        email_on_badge=prefs.email_on_badge,
        email_on_rank_change=prefs.email_on_rank_change,
    )


# ---------------------------------------------------------------------------
# Public share-token lookup (no auth required)
# ---------------------------------------------------------------------------

@router.get("/share/{token_slug}")
async def resolve_share_token(token_slug: str, db: DB) -> dict:
    """
    Public endpoint — returns scores/badges for the user behind a share token.

    Called by the public-profile /share/[token] page.
    Returns only the fields the token owner opted to share.
    Identity fields (email, username, display_name) are never included.
    """
    result = await db.execute(
        select(ShareToken).where(ShareToken.token == token_slug)
    )
    token = result.scalar_one_or_none()

    if token is None or not token.is_valid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found or expired")

    # Fetch the user's score
    from data.models.score import UserScore
    from data.models.linked_account import LinkedAccount

    score_result = await db.execute(
        select(UserScore).where(UserScore.user_id == token.user_id)
    )
    score = score_result.scalar_one_or_none()

    payload: dict = {
        "token": token.token,
        "label": token.label,
        "show_scores": token.show_scores,
        "show_badges": token.show_badges,
        "show_predictions": token.show_predictions,
    }

    if token.show_scores and score:
        payload["scores"] = {
            "total_predictions": score.total_predictions,
            "resolved_predictions": score.resolved_predictions,
            "mean_brier_score": float(score.mean_brier_score) if score.mean_brier_score is not None else None,
            "calibration_score": float(score.calibration_score) if score.calibration_score is not None else None,
            "accuracy": float(score.accuracy) if score.accuracy is not None else None,
            "last_scored_at": score.last_scored_at.isoformat() if score.last_scored_at else None,
        }

    return payload
