from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal


class BatchTransferItem(BaseModel):
    transfer_id: str = Field(..., max_length=36)
    sender_bic: str = Field(..., max_length=11)
    receiver_bic: str = Field(..., max_length=11)
    sender_iban: str = Field(..., max_length=34)
    receiver_iban: str = Field(..., max_length=34)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="EUR", max_length=3)
    description: Optional[str] = None


class BatchTransferNotification(BaseModel):
    transfers: List[BatchTransferItem]
