from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from target_service.app.database import get_db
from target_service.app.models.bank import Bank, SettlementAccount
from target_service.app.schemas.bank import BankCreate, BankResponse, BankDetailResponse

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
    await db.refresh(bank)
    
    return bank


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