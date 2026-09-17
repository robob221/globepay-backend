import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum

from sqlmodel import Field, SQLModel

from src.common.db_types import named_enum_column, tz_aware_column


class VaultFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class VaultStatus(StrEnum):
    ACTIVE = "active"
    MATURED = "matured"
    WITHDRAWN = "withdrawn"
    CANCELLED = "cancelled"


class ContributionStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


class WithdrawalStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class RecurringStatus(StrEnum):
    INACTIVE = "inactive"  # never set up, or cancelled
    ACTIVE = "active"
    PAUSED = "paused"  # user-paused
    SUSPENDED = "suspended"  # auto-paused after too many consecutive charge failures


class Vault(SQLModel, table=True):
    __tablename__ = "vaults"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    name: str
    target_amount: Decimal = Field(max_digits=14, decimal_places=2)
    contribution_amount: Decimal = Field(max_digits=14, decimal_places=2)
    frequency: VaultFrequency

    balance: Decimal = Field(default=Decimal("0.00"), max_digits=14, decimal_places=2)
    lock_until: date
    status: VaultStatus = Field(default=VaultStatus.ACTIVE)

    # Recurring/scheduled savings - reuses contribution_amount and
    # frequency above as the standing-order parameters rather than
    # duplicating them on a separate record, since a vault only ever has
    # one active schedule at a time. Requires the owner to have a saved
    # card (User.paystack_authorization_code) before this can be enabled -
    # see src/vaults/service.py.
    recurring_status: RecurringStatus = Field(
        default=RecurringStatus.INACTIVE, sa_column=named_enum_column(RecurringStatus, "vault_recurring_status")
    )
    next_charge_date: date | None = Field(default=None)
    recurring_consecutive_failures: int = Field(default=0)
    recurring_last_failure_reason: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=tz_aware_column())
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=tz_aware_column())


class VaultContribution(SQLModel, table=True):
    __tablename__ = "vault_contributions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    vault_id: uuid.UUID = Field(foreign_key="vaults.id", index=True)

    amount: Decimal = Field(max_digits=14, decimal_places=2)
    status: ContributionStatus = Field(
        default=ContributionStatus.PENDING,
        sa_column=named_enum_column(ContributionStatus, "vault_contribution_status"),
    )
    payment_reference: str | None = Field(default=None, index=True)

    paid_at: datetime | None = Field(default=None, sa_column=tz_aware_column(nullable=True))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=tz_aware_column())


class VaultWithdrawal(SQLModel, table=True):
    __tablename__ = "vault_withdrawals"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    vault_id: uuid.UUID = Field(foreign_key="vaults.id", index=True)

    gross_amount: Decimal = Field(max_digits=14, decimal_places=2)
    platform_fee: Decimal = Field(max_digits=14, decimal_places=2)
    net_amount: Decimal = Field(max_digits=14, decimal_places=2)

    status: WithdrawalStatus = Field(default=WithdrawalStatus.PENDING)
    payout_reference: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=tz_aware_column())
