import uuid

from fastapi import APIRouter, Depends, Header
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.idempotency import run_idempotently
from src.crossborder import service
from src.crossborder.schemas import CrossBorderInitiate, CrossBorderInitiateResponse, CrossBorderRead
from src.db.main import get_session

router = APIRouter(prefix="/crossborder", tags=["crossborder (sandbox demo only)"])


@router.post("/transfers", response_model=CrossBorderInitiateResponse)
async def initiate_transfer(
    data: CrossBorderInitiate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    async def _handler() -> dict:
        return await service.initiate_transfer(session, current_user, data)

    if idempotency_key:
        return await run_idempotently(
            session, current_user.id, idempotency_key, "POST /crossborder/transfers",
            data.model_dump(mode="json"), _handler,
        )
    return await _handler()


@router.get("/transfers", response_model=list[CrossBorderRead])
async def my_transfers(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.list_my_transfers(session, current_user.id)


@router.get("/transfers/{transfer_id}", response_model=CrossBorderRead)
async def get_transfer(
    transfer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.get_transfer(session, transfer_id, current_user.id)


@router.post("/transfers/{transfer_id}/retry", response_model=CrossBorderRead)
async def retry_transfer(
    transfer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    transfer = await service.get_transfer(session, transfer_id, current_user.id)
    return await service.retry_delivery(session, transfer)


@router.post("/transfers/{transfer_id}/refund", response_model=CrossBorderRead)
async def refund_transfer(
    transfer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    transfer = await service.get_transfer(session, transfer_id, current_user.id)
    return await service.refund_delivery_failure(session, transfer)
