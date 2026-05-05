import uuid
import enum
from sqlalchemy import Column, String, Float, DateTime, Enum as SQLEnum, Text
from sqlalchemy.sql import func
from app.core.database import Base


class PaymentType(str, enum.Enum):
    SEPA = "SEPA"
    SEPA_INSTANT = "SEPA_INSTANT"
    TARGET = "TARGET"


class TransactionStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    SCHEDULED = "SCHEDULED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    SETTLED = "SETTLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_iban = Column(String(34), nullable=False, index=True)
    receiver_iban = Column(String(34), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="EUR")
    payment_type = Column(SQLEnum(PaymentType), nullable=False, index=True)
    status = Column(SQLEnum(TransactionStatus), nullable=False, default=TransactionStatus.RECEIVED, index=True)
    description = Column(Text, nullable=True)
    message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    scheduled_for = Column(DateTime(timezone=True), nullable=True, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(String(10), default="0")