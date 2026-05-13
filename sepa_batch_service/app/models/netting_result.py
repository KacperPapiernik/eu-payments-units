from sqlalchemy import Column, Integer, String, Numeric, DateTime, Text
from datetime import datetime

from sepa_batch_service.app.database import Base


class NettingResult(Base):
    __tablename__ = "netting_results"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    bank_bic = Column(String(11), nullable=False)
    total_credits = Column(Numeric(19, 2), default=0)
    total_debits = Column(Numeric(19, 2), default=0)
    net_position = Column(Numeric(19, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class SessionReport(Base):
    __tablename__ = "session_reports"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True)
    total_transactions = Column(Integer, default=0)
    total_credits = Column(Numeric(19, 2), default=0)
    total_debits = Column(Numeric(19, 2), default=0)
    net_settlement_amount = Column(Numeric(19, 2), default=0)
    report_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)