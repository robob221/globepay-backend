"""Per-KYC-tier transaction volume limits - mirrors the shape of Bank of
Ghana's tiered e-money framework (higher verification unlocks higher
allowed volume). One shared ledger (TransactionVolumeLog) rather than
separate counters per module, so a user can't dodge the cap by spreading
one large amount across a vault contribution and a wallet transfer instead
of one big payment.

Two-step by design, split across two different points in each payment
flow:
  - check_transaction_limit() runs in the *initiate* step, before a
    Paystack checkout is even created, using only already-confirmed
    volume.
  - record_transaction_volume() runs in the *confirm* step (the webhook
    handler), only once Paystack has verified the charge actually
    succeeded.
Recording on confirmation rather than on initiation is deliberate: a
failed or abandoned checkout attempt must not permanently eat into a
real limit meant to cap money actually moved, not payment attempts.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Field, SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.models import KycTier, User
from src.common.db_types import tz_aware_column

# (daily limit, monthly limit) in GHS.
TIER_LIMITS: dict[KycTier, tuple[Decimal, Decimal]] = {
    KycTier.UNVERIFIED: (Decimal("500"), Decimal("2000")),
    KycTier.PHONE_VERIFIED: (Decimal("5000"), Decimal("20000")),
    KycTier.ID_VERIFIED: (Decimal("20000"), Decimal("100000")),
}


class TransactionVolumeLog(SQLModel, table=True):
    __tablename__ = "transaction_volume_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    source: str  # e.g. "vault_contribution", "wallet_transfer"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=tz_aware_column())


async def _confirmed_volume_since(session: AsyncSession, user_id: uuid.UUID, since: datetime) -> Decimal:
    result = await session.exec(
        select(func.coalesce(func.sum(TransactionVolumeLog.amount), 0)).where(
            TransactionVolumeLog.user_id == user_id, TransactionVolumeLog.created_at >= since
        )
    )
    return result.one()


async def check_transaction_limit(session: AsyncSession, user: User, amount: Decimal) -> None:
    daily_limit, monthly_limit = TIER_LIMITS[user.kyc_tier]
    now = datetime.now(timezone.utc)
    next_tier_hint = "phone number" if user.kyc_tier == KycTier.UNVERIFIED else "ID"

    daily_total = await _confirmed_volume_since(session, user.id, now - timedelta(hours=24))
    if daily_total + amount > daily_limit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"This would exceed your daily transaction limit of GHS {daily_limit} for your verification "
                f"level. Verify your {next_tier_hint} to raise it."
            ),
        )

    monthly_total = await _confirmed_volume_since(session, user.id, now - timedelta(days=30))
    if monthly_total + amount > monthly_limit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"This would exceed your monthly transaction limit of GHS {monthly_limit} for your verification "
                f"level. Verify your {next_tier_hint} to raise it."
            ),
        )


def record_transaction_volume(session: AsyncSession, user_id: uuid.UUID, amount: Decimal, source: str) -> None:
    session.add(TransactionVolumeLog(user_id=user_id, amount=amount, source=source))
