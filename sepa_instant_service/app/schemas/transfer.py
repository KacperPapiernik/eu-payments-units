from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from decimal import Decimal


class InstantTransferRequest(BaseModel):
    sender_iban: str = Field(..., max_length=34)
    receiver_iban: str = Field(..., max_length=34)
    sender_bic: str = Field(..., max_length=11)
    receiver_bic: str = Field(..., max_length=11)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="EUR", max_length=3)
    description: Optional[str] = None
    bank_bic: str = Field(..., max_length=11)

    @field_validator('currency')
    @classmethod
    def validate_eur_only(cls, v: str) -> str:
        if v != "EUR":
            raise ValueError('SEPA transfers only support EUR currency')
        return v


class InstantTransferResponse(BaseModel):
    transfer_id: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransferStatusResponse(BaseModel):
    transfer_id: str
    status: str
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None