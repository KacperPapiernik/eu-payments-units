from sqlalchemy import Column, Integer, String, Numeric, DateTime, Text
from datetime import datetime

from sepa_instant_service.app.database import Base


class PendingTransferQueue(Base):
    __tablename__ = "pending_transfer_queue"

    id = Column(Integer, primary_key=True, index=True)
    transfer_id = Column(String(36), unique=True, nullable=False, index=True)
    sender_bic = Column(String(11), nullable=False)
    receiver_bic = Column(String(11), nullable=False)
    amount = Column(Numeric(19, 2), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class LiquidityAlert(Base):
    __tablename__ = "liquidity_alerts"

    id = Column(Integer, primary_key=True, index=True)
    bank_bic = Column(String(11), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(String(20), default="open")