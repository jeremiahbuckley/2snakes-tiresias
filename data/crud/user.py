"""
CRUD operations for User.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models.user import User
from data.schemas.user import UserCreate, UserUpdate
from .base import CRUDBase


class UserCRUD(CRUDBase[User, UserCreate, UserUpdate]):

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.username == username.lower()))
        return result.scalar_one_or_none()

    async def create(  # type: ignore[override]
        self,
        db: AsyncSession,
        *,
        obj_in: UserCreate,
        hashed_password: str,
    ) -> User:
        """
        Create a new user. Caller is responsible for hashing the password
        (keeps auth concerns out of the data layer).
        """
        user = User(
            email=obj_in.email.lower(),
            username=obj_in.username.lower(),
            hashed_password=hashed_password,
            display_name=obj_in.display_name or obj_in.username,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    async def email_exists(self, db: AsyncSession, email: str) -> bool:
        result = await db.execute(
            select(User.id).where(User.email == email.lower())
        )
        return result.scalar_one_or_none() is not None

    async def username_exists(self, db: AsyncSession, username: str) -> bool:
        result = await db.execute(
            select(User.id).where(User.username == username.lower())
        )
        return result.scalar_one_or_none() is not None

    async def set_active(self, db: AsyncSession, user: User, active: bool) -> User:
        user.is_active = active
        db.add(user)
        await db.flush()
        return user

    async def verify_email(self, db: AsyncSession, user: User) -> User:
        user.is_verified = True
        db.add(user)
        await db.flush()
        return user


UserCRUD = UserCRUD(User)
