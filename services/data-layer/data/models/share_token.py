"""
ShareToken model — anonymous share links.

A user can generate one or more tokens. Each token produces a public URL
(e.g. /share/<token>) that renders the user's scores and/or badges without
revealing their identity.

Visibility is configurable per-token so a user can share different views
with different audiences (e.g. scores only vs. scores + predictions).
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.database import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .user import User


TOKEN_BYTES = 24  # produces a 32-char URL-safe base64 string


def generate_token() -> str:
    """Return a cryptographically random URL-safe token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


class ShareToken(TimestampMixin, Base):
    __tablename__ = "share_tokens"

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

    # The random slug that appears in the URL.  Unique globally.
    token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        default=generate_token,
        index=True,
    )

    # Human-readable label the user assigns (helps them remember what they shared)
    label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Visibility toggles — what the recipient can see
    show_scores: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_badges: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_predictions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Soft-delete / expiry
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="share_tokens", lazy="raise")

    @property
    def is_valid(self) -> bool:
        """True if the token has not been deactivated and has not expired."""
        if not self.is_active:
            return False
        if self.expires_at is not None:
            from datetime import timezone
            return datetime.now(tz=timezone.utc) < self.expires_at
        return True

    def __repr__(self) -> str:
        return f"<ShareToken token={self.token!r} user={self.user_id} active={self.is_active}>"
