"""
User model — authentication identity + public profile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.database import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .market import Market
    from .prediction import Prediction
    from .score import UserScore


class User(TimestampMixin, Base):
    __tablename__ = "users"

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # -------------------------------------------------------------------------
    # Public profile
    # -------------------------------------------------------------------------
    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    # Flexible bag for social links, e.g. {"twitter": "...", "manifold": "..."}
    social_links: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    markets: Mapped[List["Market"]] = relationship(
        "Market", back_populates="creator", lazy="selectin"
    )
    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction", back_populates="user", lazy="selectin"
    )
    score: Mapped[Optional["UserScore"]] = relationship(
        "UserScore", back_populates="user", uselist=False, lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
