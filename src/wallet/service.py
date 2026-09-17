import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.models import User
from src.auth.service import get_user_by_phone
from src.common.kyc_limits import check_transaction_limit, record_transaction_volume
from src.common.roundup import compute_roundup
from src.common.sms import send_sms
from src.config import settings
from src.payments import paystack
from src.vaults.service import credit_roundup
from src.wallet.models import TransferStatus, WalletTransfer
from src.wallet.schemas import TransferClaim, WalletSummary


async def get_transfer(session: AsyncSession, transfer_id: uuid.UUID) -> WalletTransfer:
    transfer = await session.get(WalletTransfer, transfer_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return transfer


async def initiate_transfer(
    session: AsyncSession,
    sender: User,
    recipient_phone_number: str,
    amount: Decimal,
    note: str | None,
    sender_email: str,
) -> dict:
    recipient = await get_user_by_phone(session, recipient_phone_number)
    if recipient is None:
        raise HTTPException(status_code=404, detail="No user found with that phone number")
    if recipient.id == sender.id:
        raise HTTPException(status_code=400, detail="Cannot send money to yourself")

    fee = (amount * Decimal(settings.PLATFORM_WITHDRAWAL_FEE_PERCENT) / Decimal(100)).quantize(
        Decimal("0.01")
    )
    net = amount - fee

    roundup = Decimal("0.00")
    if sender.round_up_vault_id is not None:
        roundup = compute_roundup(amount, sender.round_up_denomination)

    await check_transaction_limit(session, sender, amount + roundup)

    reference = f"wallet-{uuid.uuid4().hex[:14]}"
    transfer = WalletTransfer(
        sender_id=sender.id,
        recipient_id=recipient.id,
        gross_amount=amount,
        platform_fee=fee,
        net_amount=net,
        note=note,
        roundup_amount=roundup,
        payment_reference=reference,
    )
    session.add(transfer)
    await session.commit()
    await session.refresh(transfer)

    data = await paystack.initialize_transaction(
        email=sender_email,
        amount=amount + roundup,  # sender pays the transfer plus their round-up in one charge
        reference=reference,
        metadata={"type": "wallet_transfer", "transfer_id": str(transfer.id)},
    )
    return {"authorization_url": data["authorization_url"], "reference": reference}


async def _payout_to_destination(
    transfer: WalletTransfer, momo_number: str, momo_bank_code: str, account_name: str
) -> str:
    recipient_code = await paystack.create_transfer_recipient(
        name=account_name, account_number=momo_number, bank_code=momo_bank_code
    )
    reference = f"wallet-payout-{transfer.id}"
    result = await paystack.initiate_transfer(
        amount=transfer.net_amount,
        recipient_code=recipient_code,
        reason=transfer.note or "Wallet transfer",
        reference=reference,
    )
    return result.get("reference", reference)


async def confirm_transfer_payment(session: AsyncSession, reference: str) -> WalletTransfer:
    """Called from the Paystack webhook handler once the sender's charge succeeds."""
    result = await session.exec(
        select(WalletTransfer).where(WalletTransfer.payment_reference == reference)
    )
    transfer = result.first()
    if transfer is None:
        raise HTTPException(status_code=404, detail="Transfer not found")

    if transfer.status != TransferStatus.PENDING_PAYMENT:
        return transfer  # already processed

    verified = await paystack.verify_transaction(reference)
    if verified.get("status") != "success":
        transfer.status = TransferStatus.FAILED
        session.add(transfer)
        await session.commit()
        return transfer

    sender = await session.get(User, transfer.sender_id)
    if transfer.roundup_amount > 0 and sender.round_up_vault_id is not None:
        await credit_roundup(session, sender.round_up_vault_id, transfer.roundup_amount, f"{reference}-roundup")

    record_transaction_volume(
        session, sender.id, transfer.gross_amount + transfer.roundup_amount, "wallet_transfer"
    )

    recipient = await session.get(User, transfer.recipient_id)

    if recipient.default_momo_number and recipient.default_momo_bank_code:
        transfer.payout_reference = await _payout_to_destination(
            transfer,
            recipient.default_momo_number,
            recipient.default_momo_bank_code,
            recipient.default_account_name or recipient.full_name,
        )
        transfer.status = TransferStatus.COMPLETED
        transfer.completed_at = datetime.now(timezone.utc)
        await send_sms(
            recipient.phone_number,
            f"You've received GHS {transfer.net_amount} from {sender.full_name} "
            f"and it's on its way to your mobile money wallet.",
        )
    else:
        transfer.status = TransferStatus.AWAITING_RECIPIENT_PAYOUT_INFO
        await send_sms(
            recipient.phone_number,
            f"{sender.full_name} sent you GHS {transfer.net_amount}. "
            f"Open the app to add your mobile money details and claim it.",
        )

    session.add(transfer)
    await session.commit()
    await session.refresh(transfer)
    return transfer


async def claim_transfer(
    session: AsyncSession, transfer: WalletTransfer, requester_id: uuid.UUID, payload: TransferClaim
) -> WalletTransfer:
    if transfer.recipient_id != requester_id:
        raise HTTPException(status_code=403, detail="Only the recipient can claim this transfer")
    if transfer.status != TransferStatus.AWAITING_RECIPIENT_PAYOUT_INFO:
        raise HTTPException(status_code=400, detail="This transfer is not awaiting payout info")

    transfer.payout_reference = await _payout_to_destination(
        transfer, payload.momo_number, payload.momo_bank_code, payload.account_name
    )
    transfer.status = TransferStatus.COMPLETED
    transfer.completed_at = datetime.now(timezone.utc)
    session.add(transfer)

    if payload.save_as_default:
        recipient = await session.get(User, requester_id)
        recipient.default_momo_number = payload.momo_number
        recipient.default_momo_bank_code = payload.momo_bank_code
        recipient.default_account_name = payload.account_name
        session.add(recipient)

    await session.commit()
    await session.refresh(transfer)
    return transfer


async def list_incoming_pending(session: AsyncSession, user_id: uuid.UUID) -> list[WalletTransfer]:
    result = await session.exec(
        select(WalletTransfer).where(
            WalletTransfer.recipient_id == user_id,
            WalletTransfer.status == TransferStatus.AWAITING_RECIPIENT_PAYOUT_INFO,
        )
    )
    return list(result.all())


async def list_my_transfers(session: AsyncSession, user_id: uuid.UUID) -> list[WalletTransfer]:
    result = await session.exec(
        select(WalletTransfer)
        .where((WalletTransfer.sender_id == user_id) | (WalletTransfer.recipient_id == user_id))
        .order_by(WalletTransfer.created_at.desc())
    )
    return list(result.all())


async def get_wallet_summary(session: AsyncSession, user_id: uuid.UUID) -> WalletSummary:
    transfers = await list_my_transfers(session, user_id)
    completed = [transfer for transfer in transfers if transfer.status == TransferStatus.COMPLETED]
    received = sum((transfer.net_amount for transfer in completed if transfer.recipient_id == user_id), Decimal("0.00"))
    sent = sum((transfer.gross_amount for transfer in completed if transfer.sender_id == user_id), Decimal("0.00"))
    fees = sum((transfer.platform_fee for transfer in completed if transfer.sender_id == user_id), Decimal("0.00"))
    roundup = sum((transfer.roundup_amount for transfer in completed if transfer.sender_id == user_id), Decimal("0.00"))
    return WalletSummary(
        received_total=received,
        sent_total=sent,
        fee_total=fees,
        roundup_total=roundup,
        net_flow=received - sent - roundup,
    )
