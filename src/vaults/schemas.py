import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from src.vaults.models import ContributionStatus, RecurringStatus, VaultFrequency, VaultStatus, WithdrawalStatus


class VaultCreate(BaseModel):
    name: str
    target_amount: Decimal
    contribution_amount: Decimal
    frequency: VaultFrequency
    lock_until: date


class VaultRead(BaseModel):
    id: uuid.UUID
    name: str
    target_amount: Decimal
    contribution_amount: Decimal
    frequency: VaultFrequency
    balance: Decimal
    lock_until: date
    status: VaultStatus
    recurring_status: RecurringStatus
    next_charge_date: date | None
    recurring_consecutive_failures: int
    recurring_last_failure_reason: str | None
    created_at: datetime


class ContributionInitiate(BaseModel):
    amount: Decimal
    email: str


class ContributionInitiateResponse(BaseModel):
    authorization_url: str
    reference: str


class ContributionRead(BaseModel):
    id: uuid.UUID
    amount: Decimal
    status: ContributionStatus
    paid_at: datetime | None
    created_at: datetime


class WithdrawalRequest(BaseModel):
    momo_number: str
    momo_network_bank_code: str
    account_name: str


class WithdrawalRead(BaseModel):
    id: uuid.UUID
    gross_amount: Decimal
    platform_fee: Decimal
    net_amount: Decimal
    status: WithdrawalStatus
    created_at: datetime
