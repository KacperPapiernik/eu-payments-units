from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import uuid

from target_service.app.database import get_db
from target_service.app.models.bank import Bank, SettlementAccount
from target_service.app.models.settlement_transaction import (
    SettlementTransaction,
    TransactionStatus,
)
from target_service.app.schemas.settlement import (
    SettlementRequest,
    SettlementResponse,
)
from shared.security.iban_validator import validate_iban
from target_service.app.services.webhook_notifier import send_webhook

router = APIRouter(prefix="/settle", tags=["settlement"])


def validate_iban_strict(iban: str, field_name: str):
    valid, error = validate_iban(iban)
    if not valid:
        raise HTTPException(status_code=400, detail=f"{field_name}: {error}")


async def get_bank_by_bic_cached(db: AsyncSession, bic: str):
    result = await db.execute(
        select(Bank).where(Bank.bic == bic)
    )
    bank = result.scalar_one_or_none()
    return bank


@router.post("/payment", response_model=SettlementResponse)
async def settle_payment(
    payment: SettlementRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    if payment.sender_iban:
        validate_iban_strict(payment.sender_iban, "sender_iban")
    if payment.receiver_iban:
        validate_iban_strict(payment.receiver_iban, "receiver_iban")

    sender = await get_bank_by_bic_cached(
        db,
        payment.sender_bic
    )

    receiver = await get_bank_by_bic_cached(
        db,
        payment.receiver_bic
    )

    if sender is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sender bank not found: {payment.sender_bic}"
        )

    if receiver is None:
        raise HTTPException(
            status_code=404,
            detail=f"Receiver bank not found: {payment.receiver_bic}"
        )

    if sender.is_blocked:
        raise HTTPException(
            status_code=400,
            detail=f"Sender bank is blocked: {payment.sender_bic}"
        )

    if receiver.is_blocked:
        raise HTTPException(
            status_code=400,
            detail=f"Receiver bank is blocked: {payment.receiver_bic}"
        )

    sender_account_result = await db.execute(
        select(SettlementAccount).where(
            SettlementAccount.bank_id == sender.id
        )
    )
    sender_account = sender_account_result.scalar_one_or_none()

    receiver_account_result = await db.execute(
        select(SettlementAccount).where(
            SettlementAccount.bank_id == receiver.id
        )
    )
    receiver_account = receiver_account_result.scalar_one_or_none()

    if sender_account is None:
        raise HTTPException(
            status_code=404,
            detail=f"Settlement account not found for sender: {payment.sender_bic}"
        )

    if receiver_account is None:
        raise HTTPException(
            status_code=404,
            detail=f"Settlement account not found for receiver: {payment.receiver_bic}"
        )

    available = sender_account.available_balance

    if available < payment.amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient funds. "
                f"Available: {available}, "
                f"Required: {payment.amount}"
            )
        )

    sender_account.balance -= payment.amount
    sender_account.available_balance -= payment.amount

    receiver_account.balance += payment.amount
    receiver_account.available_balance += payment.amount

    transaction = SettlementTransaction(
        transaction_id=payment.transaction_id or str(uuid.uuid4()),
        sender_iban=payment.sender_iban,
        receiver_iban=payment.receiver_iban,
        sender_bic=payment.sender_bic,
        receiver_bic=payment.receiver_bic,
        amount=payment.amount,
        currency=payment.currency,
        status=TransactionStatus.SETTLED,
        description=payment.description,
        settled_at=datetime.utcnow(),
        service=payment.service,
    )

    db.add(transaction)

    try:
        await db.commit()
        await db.refresh(transaction)
        await db.refresh(sender_account)
        await db.refresh(receiver_account)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during settlement: {str(e)}")

    background_tasks.add_task(
        send_webhook,
        receiver_bic=payment.receiver_bic,
        event="payment.settled",
        transfer_id=transaction.transaction_id,
        sender_bic=payment.sender_bic,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        settled_at=transaction.settled_at,
        sender_iban=payment.sender_iban,
        receiver_iban=payment.receiver_iban,
    )

    return SettlementResponse(
        transaction_id=transaction.transaction_id,
        status="settled",
        settled_at=transaction.settled_at,
        sender_balance=sender_account.balance,
        receiver_balance=receiver_account.balance,
    )