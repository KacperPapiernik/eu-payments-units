from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from decimal import Decimal
import uuid

from target_service.app.database import get_db
from target_service.app.models.bank import Bank, SettlementAccount
from target_service.app.models.settlement_transaction import SettlementTransaction, TransactionStatus
from target_service.app.schemas.settlement import SettlementRequest, SettlementResponse

router = APIRouter(prefix="/settle", tags=["settlement"])


@router.post("/payment", response_model=SettlementResponse)
async def settle_payment(payment: SettlementRequest, db: AsyncSession = Depends(get_db)):
    sender_result = await db.execute(
        select(Bank).where(Bank.bic == payment.sender_bic)
    )
    sender = sender_result.scalar_one_or_none()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender bank not found")
    
    receiver_result = await db.execute(
        select(Bank).where(Bank.bic == payment.receiver_bic)
    )
    receiver = receiver_result.scalar_one_or_none()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver bank not found")
    
    if sender.is_blocked or receiver.is_blocked:
        raise HTTPException(status_code=400, detail="One of the banks is blocked")
    
    sender_account_result = await db.execute(
        select(SettlementAccount).where(SettlementAccount.bank_id == sender.id)
    )
    sender_account = sender_account_result.scalar_one()
    
    receiver_account_result = await db.execute(
        select(SettlementAccount).where(SettlementAccount.bank_id == receiver.id)
    )
    receiver_account = receiver_account_result.scalar_one()
    
    available = sender_account.available_balance
    if available < payment.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Available: {available}, Required: {payment.amount}"
        )
    
    sender_account.balance -= payment.amount
    sender_account.available_balance -= payment.amount
    
    receiver_account.balance += payment.amount
    receiver_account.available_balance += payment.amount
    
    transaction = SettlementTransaction(
        transaction_id=payment.transaction_id or str(uuid.uuid4()),
        sender_bic=payment.sender_bic,
        receiver_bic=payment.receiver_bic,
        amount=payment.amount,
        currency=payment.currency,
        status=TransactionStatus.SETTLED,
        description=payment.description,
        settled_at=datetime.utcnow(),
        service=payment.service
    )
    db.add(transaction)
    
    await db.commit()
    await db.refresh(sender_account)
    await db.refresh(receiver_account)
    
    return SettlementResponse(
        transaction_id=transaction.transaction_id,
        status="settled",
        settled_at=transaction.settled_at,
        sender_balance=sender_account.balance,
        receiver_balance=receiver_account.balance
    )