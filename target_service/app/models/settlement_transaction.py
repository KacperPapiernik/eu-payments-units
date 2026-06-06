from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum, Text
from datetime import datetime
import enum

from target_service.app.database import Base


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    SETTLED = "settled"
    REJECTED = "rejected"
    FAILED = "failed"


class SettlementTransaction(Base):
    __tablename__ = "settlement_transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(100), unique=True, nullable=False, index=True)
    sender_iban = Column(String(34), nullable=True)
    receiver_iban = Column(String(34), nullable=True)
    sender_bic = Column(String(11), nullable=False, index=True)
    receiver_bic = Column(String(11), nullable=False, index=True)
    amount = Column(Numeric(19, 2), nullable=False)
    currency = Column(String(3), default="EUR")
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    settled_at = Column(DateTime, nullable=True)
    service = Column(String(50), nullable=False)