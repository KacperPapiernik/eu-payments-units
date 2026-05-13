from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum, Text
from datetime import datetime
import enum

from sepa_instant_service.app.database import Base


class InstantTransferStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SETTLED = "settled"
    REJECTED = "rejected"
    FAILED = "failed"


class InstantTransfer(Base):
    __tablename__ = "instant_transfers"

    id = Column(Integer, primary_key=True, index=True)
    transfer_id = Column(String(36), unique=True, nullable=False, index=True)
    sender_iban = Column(String(34), nullable=False)
    receiver_iban = Column(String(34), nullable=False)
    sender_bic = Column(String(11), nullable=False)
    receiver_bic = Column(String(11), nullable=False)
    amount = Column(Numeric(19, 2), nullable=False)
    currency = Column(String(3), default="EUR")
    description = Column(Text, nullable=True)
    status = Column(Enum(InstantTransferStatus), default=InstantTransferStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)