"""
LinkedAccount model — connects a Tiresias user to an external platform.

Covers both prediction market sources (Kalshi, Polymarket, Manifold, Metaculus)
and social publishing targets (X, Bluesky).

- For market platforms: `is_enabled` controls whether trade data is pulled.
- For social platforms: `is_enabled` controls whether scores are auto-pushed.

Credentials are stored encrypted (Fernet or KMS — encryption is applied before
writes by the auth-service; this model stores the ciphertext).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.database import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .user import User


# ---------------------------------------------------------------------------
# Platform catalogue
# ---------------------------------------------------------------------------

class Platform(StrEnum):
    # Prediction market data sources
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"
    MANIFOLD = "manifold"
    METACULUS = "metaculus"
    # Social publishing targets
    X = "x"
    BLUESKY = "bluesky"


class PlatformType(StrEnum):
    MARKET = "market"
    SOCIAL = "social"


MARKET_PLATFORMS: frozenset[Platform] = frozenset(
    {Platform.KALSHI, Platform.POLYMARKET, Platform.MANIFOLD, Platform.METACULUS}
)
SOCIAL_PLATFORMS: frozenset[Platform] = frozenset({Platform.X, Platform.BLUESKY})

PLATFORM_TYPE_MAP: dict[Platform, PlatformType] = {
    **{p: PlatformType.MARKET for p in MARKET_PLATFORMS},
    **{p: PlatformType.SOCIAL for p in SOCIAL_PLATFORMS},
}


def platform_type(p: Platform) -> PlatformType:
    return PLATFORM_TYPE_MAP[p]


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class LinkedAccount(TimestampMixin, Base):
    """One row per (user, platform) pair."""

    __tablename__ = "linked_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uq_linked_accounts_user_platform"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_type: Mapped[str] = mapped_column(String(16), nullable=False)

    # The user's identity on the external platform (username, wallet address, user ID …)
    external_identifier: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # Encrypted credential (API key, OAuth access token, app password …).
    # The auth-service encrypts before writing; this column stores ciphertext only.
    credential_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Whether data should be pulled from (market) or pushed to (social) this platform
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # True once the auth-service has successfully verified the credential
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship (lazy to avoid N+1 in list endpoints)
    user: Mapped["User"] = relationship("User", back_populates="linked_accounts", lazy="raise")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_market(self) -> bool:
        return self.platform_type == PlatformType.MARKET

    @property
    def is_social(self) -> bool:
        return self.platform_type == PlatformType.SOCIAL

    def __repr__(self) -> str:
        return f"<LinkedAccount user={self.user_id} platform={self.platform!r} enabled={self.is_enabled}>"
