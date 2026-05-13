from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum
from datetime import datetime
import enum

from sepa_batch_service.app.database import Base


class SessionStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    NETTING_COMPLETE = "netting_complete"
    SETTLED = "settled"


class BatchSession(Base):
    __tablename__ = "batch_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.OPEN)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    total_credits = Column(Numeric(19, 2), default=0)
    total_debits = Column(Numeric(19, 2), default=0)
    transaction_count = Column(Integer, default=0)