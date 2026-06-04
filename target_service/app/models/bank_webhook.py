from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime

from target_service.app.database import Base


class BankWebhook(Base):
    __tablename__ = "bank_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    bank_bic = Column(String(11), unique=True, nullable=False, index=True)
    url = Column(String(512), nullable=False)
    secret = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
