import enum
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum, Text
from datetime import datetime

from target_service.app.database import Base


class RtgsTransferStatus(str, enum.Enum):
    PENDING = "pending"
    SETTLED = "settled"
    REJECTED = "rejected"
    FAILED = "failed"
    RECALLED = "recalled"


class RtgsTransfer(Base):
    __tablename__ = "rtgs_transfers"

    id = Column(Integer, primary_key=True, index=True)
    transfer_id = Column(String(100), unique=True, nullable=False, index=True)
    sender_iban = Column(String(34), nullable=False)
    receiver_iban = Column(String(34), nullable=False)
    sender_bic = Column(String(11), nullable=False, index=True)
    receiver_bic = Column(String(11), nullable=False, index=True)
    amount = Column(Numeric(19, 2), nullable=False)
    currency = Column(String(3), default="EUR")
    description = Column(Text, nullable=True)
    status = Column(Enum(RtgsTransferStatus), default=RtgsTransferStatus.PENDING)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
