import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr

from src.auth.models import KycStatus, KycTier, ReferralRewardStatus


class UserCreate(BaseModel):
    phone_number: str
    full_name: str
    email: EmailStr | None = None
    password: str
    referral_code: str | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    phone_number: str
    full_name: str
    email: str | None
    is_phone_verified: bool
    kyc_tier: KycTier
    kyc_status: KycStatus
    kyc_rejection_reason: str | None
    referral_code: str
    referral_reward_status: ReferralRewardStatus
    default_momo_number: str | None
    default_momo_bank_code: str | None
    round_up_vault_id: uuid.UUID | None
    round_up_denomination: Decimal


class ReferredUserRead(BaseModel):
    full_name: str
    referral_reward_status: ReferralRewardStatus
    created_at: datetime


class PayoutDestinationSet(BaseModel):
    momo_number: str
    momo_bank_code: str  # MTN / ATL / VOD
    account_name: str


class RoundUpSettingsSet(BaseModel):
    vault_id: uuid.UUID | None  # null disables round-up
    denomination: Decimal = Decimal("5.00")


class UserLogin(BaseModel):
    phone_number: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    phone_number: str


class PasswordResetConfirm(BaseModel):
    phone_number: str
    code: str
    new_password: str


class PhoneVerificationConfirm(BaseModel):
    code: str


class KycIdSubmit(BaseModel):
    ghana_card_number: str


class AccountClosureRequest(BaseModel):
    password: str
