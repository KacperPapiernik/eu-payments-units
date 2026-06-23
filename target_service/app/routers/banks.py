from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from decimal import Decimal

from target_service.app.database import get_db
from target_service.app.models.bank import Bank, SettlementAccount
from target_service.app.schemas.bank import (
    BankCreate, BankResponse, BankDetailResponse,
    UpdateLimitDebtRequest, UpdateLimitDebtResponse,
    BatchBalancesRequest,
)

router = APIRouter(prefix="/banks", tags=["banks"])


@router.get("", response_model=list[BankResponse])
async def get_banks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Bank).options(selectinload(Bank.settlement_accounts))
    )
    return result.scalars().all()


@router.get("/{bic}", response_model=BankDetailResponse)
async def get_bank(bic: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Bank)
        .where(Bank.bic == bic)
        .options(selectinload(Bank.settlement_accounts))
    )
    bank = result.scalar_one_or_none()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    return bank


@router.post("", response_model=BankResponse)
async def create_bank(bank_data: BankCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Bank).where(Bank.bic == bank_data.bic))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Bank already exists")

    bank = Bank(**bank_data.model_dump())
    db.add(bank)
    await db.flush()

    account = SettlementAccount(
        bank_id=bank.id,
        currency="EUR",
        balance=0,
        available_balance=0,
        limit_debt=0
    )
    db.add(account)
    await db.commit()

    result = await db.execute(
        select(Bank)
        .where(Bank.id == bank.id)
        .options(selectinload(Bank.settlement_accounts))
    )
    bank = result.scalar_one()

    return bank


@router.post("/balances")
async def get_batch_balances(
    request: BatchBalancesRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Bank)
        .where(Bank.bic.in_(request.bics))
        .options(selectinload(Bank.settlement_accounts))
    )
    banks = result.scalars().all()
    balances = []
    for bank in banks:
        if bank.settlement_accounts:
            acct = bank.settlement_accounts[0]
            balances.append({
                "bic": bank.bic,
                "available_balance": str(acct.available_balance),
                "limit_debt": str(acct.limit_debt),
                "balance": str(acct.balance),
            })
    return {"balances": balances}


@router.post("/block/{bic}")
async def block_bank(bic: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Bank).where(Bank.bic == bic))
    bank = result.scalar_one_or_none()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    
    bank.is_blocked = True
    await db.commit()
    return {"status": "blocked", "bic": bic}


@router.post("/unblock/{bic}")
async def unblock_bank(bic: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Bank).where(Bank.bic == bic))
    bank = result.scalar_one_or_none()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    
    bank.is_blocked = False
    await db.commit()
    return {"status": "unblocked", "bic": bic}


@router.post("/{bic}/limit-debt", response_model=UpdateLimitDebtResponse)
async def update_limit_debt(
    bic: str,
    request: UpdateLimitDebtRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Bank).where(Bank.bic == bic)
        .options(selectinload(Bank.settlement_accounts))
    )
    bank = result.scalar_one_or_none()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")

    if not bank.settlement_accounts:
        raise HTTPException(status_code=404, detail="No settlement account for this bank")

    account = bank.settlement_accounts[0]
    account.limit_debt = request.limit_debt

    try:
        await db.commit()
        await db.refresh(account)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return UpdateLimitDebtResponse(
        bic=bic,
        limit_debt=account.limit_debt,
        balance=account.balance,
        available_balance=account.available_balance,
    )