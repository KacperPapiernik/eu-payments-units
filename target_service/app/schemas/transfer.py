from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from decimal import Decimal


class RtgsTransferRequest(BaseModel):
    sender_iban: str = Field(..., max_length=34)
    receiver_iban: str = Field(..., max_length=34)
    sender_bic: str = Field(..., max_length=11)
    receiver_bic: str = Field(..., max_length=11)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="EUR", max_length=3)
    description: Optional[str] = None

    @field_validator('currency')
    @classmethod
    def validate_eur_only(cls, v: str) -> str:
        if v != "EUR":
            raise ValueError('RTGS transfers only support EUR currency')
        return v


class RtgsTransferResponse(BaseModel):
    transfer_id: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransferStatusResponse(BaseModel):
    transfer_id: str
    status: str
    sender_bic: str
    receiver_bic: str
    amount: Decimal
    description: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
