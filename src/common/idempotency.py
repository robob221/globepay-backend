"""Idempotency support for payment-initiation endpoints.

A client that double-taps "Pay" (or retries after a dropped response) can
otherwise trigger two separate Paystack checkout initializations for the
same logical action - two payment_reference rows, two authorization_urls,
and a genuinely confusing "which one do I pay?" for the user. Callers pass
an optional `Idempotency-Key` header (client-generated, one per logical
action); the same key + same request body replays the first response
instead of re-running the handler. Idempotency is opt-in: a request with
no key runs exactly as before, unaffected.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.common.db_types import tz_aware_column


class IdempotencyKey(SQLModel, table=True):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "key", "endpoint", name="uq_idempotency_key_scope"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    key: str
    endpoint: str
    request_hash: str
    status: str = Field(default="pending")  # pending | completed
    response_body: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=tz_aware_column())


def _hash_request(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()


async def _find_existing(
    session: AsyncSession, user_id: uuid.UUID, key: str, endpoint: str
) -> IdempotencyKey | None:
    result = await session.exec(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.key == key,
            IdempotencyKey.endpoint == endpoint,
        )
    )
    return result.first()


def _resolve_existing(existing: IdempotencyKey, request_hash: str) -> dict:
    if existing.request_hash != request_hash:
        raise HTTPException(
            status_code=409, detail="This Idempotency-Key was already used with a different request"
        )
    if existing.status == "pending":
        raise HTTPException(
            status_code=409, detail="A request with this Idempotency-Key is still being processed"
        )
    return existing.response_body


async def run_idempotently(
    session: AsyncSession,
    user_id: uuid.UUID,
    key: str,
    endpoint: str,
    request_body: dict[str, Any],
    handler: Callable[[], Awaitable[dict]],
) -> dict:
    request_hash = _hash_request(request_body)

    existing = await _find_existing(session, user_id, key, endpoint)
    if existing is not None:
        return _resolve_existing(existing, request_hash)

    record = IdempotencyKey(user_id=user_id, key=key, endpoint=endpoint, request_hash=request_hash)
    session.add(record)
    try:
        await session.commit()
    except IntegrityError:
        # Lost a race against a concurrent identical request that claimed
        # this key first (unique constraint on user_id+key+endpoint).
        await session.rollback()
        existing = await _find_existing(session, user_id, key, endpoint)
        if existing is None:
            raise
        return _resolve_existing(existing, request_hash)

    try:
        response = await handler()
    except Exception:
        # Don't permanently burn the key on a failed attempt - delete the
        # pending record so a legitimate retry with the same key can go
        # through instead of hitting "still being processed" forever.
        await session.delete(record)
        await session.commit()
        raise

    record.status = "completed"
    record.response_body = response
    session.add(record)
    await session.commit()
    return response
