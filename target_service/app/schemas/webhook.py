from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class WebhookRegistrationRequest(BaseModel):
    url: str = Field(..., max_length=512)
    secret: Optional[str] = None


class WebhookRegistrationResponse(BaseModel):
    bank_bic: str
    url: str
    secret: str


class WebhookConfigResponse(BaseModel):
    bank_bic: str
    url: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
