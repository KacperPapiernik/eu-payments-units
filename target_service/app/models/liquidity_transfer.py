from sqlalchemy import Column, Integer, String, Numeric, DateTime, Enum
from datetime import datetime
import enum

from target_service.app.database import Base


class LiquidityTransferType(str, enum.Enum):
    INJECTION = "injection"
    WITHDRAWAL = "withdrawal"


class LiquidityTransfer(Base):
    __tablename__ = "liquidity_transfers"

    id = Column(Integer, primary_key=True, index=True)
    transfer_id = Column(String(36), unique=True, nullable=False, index=True)
    bank_bic = Column(String(11), nullable=False, index=True)
    amount = Column(Numeric(19, 2), nullable=False)
    transfer_type = Column(Enum(LiquidityTransferType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    settled = Column(String(20), default="pending")