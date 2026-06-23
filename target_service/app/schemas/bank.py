from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class SettlementAccountResponse(BaseModel):
    id: int
    bank_id: int
    currency: str
    balance: Decimal
    available_balance: Decimal
    limit_debt: Decimal

    class Config:
        from_attributes = True


class BankBase(BaseModel):
    bic: str = Field(..., max_length=11)
    name: str


class BankCreate(BankBase):
    pass


class BankResponse(BankBase):
    id: int
    is_blocked: bool
    created_at: datetime
    settlement_accounts: list[SettlementAccountResponse] = []

    class Config:
        from_attributes = True


class BankDetailResponse(BankResponse):
    pass


class BatchBalancesRequest(BaseModel):
    bics: list[str]


class UpdateLimitDebtRequest(BaseModel):
    limit_debt: Decimal = Field(..., ge=0)


class UpdateLimitDebtResponse(BaseModel):
    bic: str
    limit_debt: Decimal
    balance: Decimal
    available_balance: Decimal

    class Config:
        from_attributes = True