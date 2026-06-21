from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
import uuid

from target_service.app.database import get_db
from target_service.app.models.bank import Bank, SettlementAccount
from target_service.app.models.liquidity_transfer import LiquidityTransfer, LiquidityTransferType
from target_service.app.schemas.settlement import LiquidityInjectionRequest, LiquidityInjectionResponse

router = APIRouter(prefix="/liquidity", tags=["liquidity"])


@router.post("/injection", response_model=LiquidityInjectionResponse)
async def liquidity_injection(
    request: LiquidityInjectionRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Bank).where(Bank.bic == request.bank_bic))
    bank = result.scalar_one_or_none()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    
    account_result = await db.execute(
        select(SettlementAccount).where(SettlementAccount.bank_id == bank.id)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Settlement account not found for this bank")
    
    account.balance += request.amount
    account.available_balance += request.amount
    
    transfer = LiquidityTransfer(
        transfer_id=str(uuid.uuid4()),
        bank_bic=request.bank_bic,
        amount=request.amount,
        transfer_type=LiquidityTransferType.INJECTION,
        settled="completed"
    )
    db.add(transfer)

    try:
        await db.commit()
        await db.refresh(account)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during liquidity injection: {str(e)}")
    
    return LiquidityInjectionResponse(
        transfer_id=transfer.transfer_id,
        bank_bic=request.bank_bic,
        amount=request.amount,
        new_balance=account.balance
    )