"""
NotificationPreferences model — per-user email/push notification settings.

One row per user (enforced by unique constraint on user_id).
Created with sensible defaults when a new account is registered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.database import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .user import User


class NotificationPreferences(TimestampMixin, Base):
    __tablename__ = "notification_preferences"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Email notifications
    email_on_resolution: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_on_badge: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_on_rank_change: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(
        "User", back_populates="notification_preferences", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<NotificationPreferences user={self.user_id}>"
