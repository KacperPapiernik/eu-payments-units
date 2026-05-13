from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from target_service.app.database import Base


class Bank(Base):
    __tablename__ = "banks"

    id = Column(Integer, primary_key=True, index=True)
    bic = Column(String(11), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    settlement_accounts = relationship("SettlementAccount", back_populates="bank")


class SettlementAccount(Base):
    __tablename__ = "settlement_accounts"

    id = Column(Integer, primary_key=True, index=True)
    bank_id = Column(Integer, ForeignKey("banks.id"), nullable=False, index=True)
    currency = Column(String(3), default="EUR")
    balance = Column(Numeric(19, 2), default=0)
    available_balance = Column(Numeric(19, 2), default=0)
    limit_debt = Column(Numeric(19, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    bank = relationship("Bank", back_populates="settlement_accounts")