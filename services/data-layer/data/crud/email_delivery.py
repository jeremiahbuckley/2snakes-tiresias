"""
CRUD operations for EmailDelivery.

The primary entry point is ``claim()``. It atomically reserves a
(user_id, event_type, dedupe_key) slot using PostgreSQL's
``INSERT ... ON CONFLICT DO NOTHING ... RETURNING id``:

- Returns an EmailDelivery row if the caller holds the slot (i.e. the
  insert inserted one row, so no prior delivery exists).
- Returns ``None`` if a prior row already occupies the slot — the caller
  should skip sending, because the email was already sent (or attempted)
  by an earlier run.

The caller then attempts the actual send and calls ``mark_sent()`` or
``mark_failed()`` to update the row.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from data.models.email_delivery import EmailDelivery


class EmailDeliveryCRUD:

    async def claim(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        event_type: str,
        dedupe_key: str,
    ) -> Optional[EmailDelivery]:
        """
        Atomically claim a delivery slot.

        Returns the inserted row (status="sent" provisionally) if the slot
        was free. Returns None if a row already exists — caller should
        skip sending.
        """
        stmt = (
            pg_insert(EmailDelivery)
            .values(
                user_id=user_id,
                event_type=event_type,
                dedupe_key=dedupe_key,
                status="sent",  # provisional — updated after send attempt
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "event_type", "dedupe_key"]
            )
            .returning(EmailDelivery)
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            await db.flush()
        return row

    async def mark_sent(
        self,
        db: AsyncSession,
        *,
        delivery: EmailDelivery,
        provider_message_id: Optional[str],
    ) -> EmailDelivery:
        delivery.status = "sent"
        delivery.provider_message_id = provider_message_id
        db.add(delivery)
        await db.flush()
        return delivery

    async def mark_failed(
        self,
        db: AsyncSession,
        *,
        delivery: EmailDelivery,
    ) -> EmailDelivery:
        delivery.status = "failed"
        db.add(delivery)
        await db.flush()
        return delivery

    async def get(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        event_type: str,
        dedupe_key: str,
    ) -> Optional[EmailDelivery]:
        result = await db.execute(
            select(EmailDelivery).where(
                EmailDelivery.user_id == user_id,
                EmailDelivery.event_type == event_type,
                EmailDelivery.dedupe_key == dedupe_key,
            )
        )
        return result.scalar_one_or_none()


EmailDeliveryCRUD = EmailDeliveryCRUD()
