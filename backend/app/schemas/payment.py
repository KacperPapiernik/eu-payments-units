from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


class PaymentType(str, Enum):
    SEPA = "SEPA"
    SEPA_INSTANT = "SEPA_INSTANT"
    TARGET = "TARGET"


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class PaymentRequest(BaseModel):
    sender_iban: str = Field(..., min_length=15, max_length=34)
    receiver_iban: str = Field(..., min_length=15, max_length=34)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="EUR", pattern="^[A-Z]{3}$")
    type: PaymentType = Field(..., description="Payment type: SEPA, SEPA_INSTANT, or TARGET")
    description: Optional[str] = None


class PaymentResponse(BaseModel):
    transaction_id: str
    status: TransactionStatus
    payment_type: PaymentType
    created_at: datetime
    message: Optional[str] = None