"""
Generic async CRUD base — subclass with a concrete Model and Create/Update schema.
"""

from __future__ import annotations

from typing import Any, Generic, Optional, Sequence, Type, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.database import Base

ModelT = TypeVar("ModelT", bound=Base)
CreateSchemaT = TypeVar("CreateSchemaT", bound=BaseModel)
UpdateSchemaT = TypeVar("UpdateSchemaT", bound=BaseModel)


class CRUDBase(Generic[ModelT, CreateSchemaT, UpdateSchemaT]):
    def __init__(self, model: Type[ModelT]) -> None:
        self.model = model

    # -------------------------------------------------------------------------
    # Reads
    # -------------------------------------------------------------------------

    async def get(self, db: AsyncSession, id: UUID) -> Optional[ModelT]:
        result = await db.get(self.model, id)
        return result

    async def get_or_404(self, db: AsyncSession, id: UUID) -> ModelT:
        obj = await self.get(db, id)
        if obj is None:
            raise ValueError(f"{self.model.__name__} with id={id} not found")
        return obj

    async def list(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[ModelT]:
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count(self, db: AsyncSession) -> int:
        from sqlalchemy import func
        result = await db.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()

    # -------------------------------------------------------------------------
    # Writes
    # -------------------------------------------------------------------------

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaT, **extra: Any) -> ModelT:
        data = obj_in.model_dump(exclude_unset=False)
        data.update(extra)
        db_obj = self.model(**data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelT,
        obj_in: UpdateSchemaT | dict[str, Any],
    ) -> ModelT:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, id: UUID) -> Optional[ModelT]:
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.flush()
        return obj
