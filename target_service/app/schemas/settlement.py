from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from decimal import Decimal


class SettlementRequest(BaseModel):
    transaction_id: str
    sender_iban: Optional[str] = None
    receiver_iban: Optional[str] = None
    sender_bic: str = Field(..., max_length=11)
    receiver_bic: str = Field(..., max_length=11)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="EUR", max_length=3)
    description: Optional[str] = None
    service: str

    @field_validator('currency')
    @classmethod
    def validate_eur_only(cls, v: str) -> str:
        if v != "EUR":
            raise ValueError('SEPA transfers only support EUR currency')
        return v


class SettlementResponse(BaseModel):
    transaction_id: str
    status: str
    settled_at: Optional[datetime] = None
    sender_balance: Decimal
    receiver_balance: Decimal

    class Config:
        from_attributes = True


class LiquidityInjectionRequest(BaseModel):
    bank_bic: str = Field(..., max_length=11)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="EUR", max_length=3)

    @field_validator('currency')
    @classmethod
    def validate_eur_only(cls, v: str) -> str:
        if v != "EUR":
            raise ValueError('SEPA transfers only support EUR currency')
        return v


class LiquidityInjectionResponse(BaseModel):
    transfer_id: str
    bank_bic: str
    amount: Decimal
    new_balance: Decimal

    class Config:
        from_attributes = True