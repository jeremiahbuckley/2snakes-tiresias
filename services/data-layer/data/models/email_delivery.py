"""
EmailDelivery model — audit log + dedupe key for transactional emails.

Used by notification-service to guarantee at-most-once delivery per
(user, event, entity). Before sending, the handler inserts a row with
ON CONFLICT DO NOTHING; if the insert returns zero rows, the email has
already been sent and is skipped.

Rows are also handy as a delivery audit trail — every send is recorded
with the provider message id returned by Resend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.database import Base, new_uuid

if TYPE_CHECKING:
    from .user import User


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"
    __table_args__ = (
        # One (user, event_type, dedupe_key) combination may only have one
        # delivery row. The handler uses INSERT ... ON CONFLICT DO NOTHING
        # to atomically claim the slot before calling the provider.
        UniqueConstraint(
            "user_id",
            "event_type",
            "dedupe_key",
            name="uq_email_delivery_dedupe",
        ),
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

    # e.g. "market_resolved" | "badge_earned" | "rank_change"
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)

    # Stable identifier for the underlying event. Examples:
    #   market_resolved  -> str(market_id)
    #   badge_earned     -> badge_id (str slug)
    #   rank_change      -> f"{milestone}:{rank}" (e.g. "top10:7")
    dedupe_key: Mapped[str] = mapped_column(String(256), nullable=False)

    # Resend message id returned on successful send (null if send failed
    # after the dedupe slot was claimed — row is kept so we don't retry).
    provider_message_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )

    # "sent" | "failed"
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="sent",
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", lazy="raise")

    def __repr__(self) -> str:
        return (
            f"<EmailDelivery user={self.user_id} "
            f"event={self.event_type} key={self.dedupe_key!r} "
            f"status={self.status}>"
        )
