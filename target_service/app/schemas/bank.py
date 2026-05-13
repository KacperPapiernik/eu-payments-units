from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class BankBase(BaseModel):
    bic: str = Field(..., max_length=11)
    name: str


class BankCreate(BankBase):
    pass


class BankResponse(BankBase):
    id: int
    is_blocked: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SettlementAccountResponse(BaseModel):
    id: int
    bank_id: int
    currency: str
    balance: Decimal
    available_balance: Decimal
    limit_debt: Decimal

    class Config:
        from_attributes = True


class BankDetailResponse(BankResponse):
    settlement_accounts: list[SettlementAccountResponse] = []

    class Config:
        from_attributes = True