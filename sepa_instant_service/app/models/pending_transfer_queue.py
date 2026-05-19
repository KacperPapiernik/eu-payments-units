from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    Text
)

from datetime import datetime

from sepa_instant_service.app.database import Base


class PendingTransferQueue(Base):
    __tablename__ = "pending_transfer_queue"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    transfer_id = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True
    )

    sender_bic = Column(
        String(11),
        nullable=False,
        index=True
    )

    receiver_bic = Column(
        String(11),
        nullable=False,
        index=True
    )

    amount = Column(
        Numeric(19, 2),
        nullable=False
    )

    reason = Column(
        Text,
        nullable=True
    )

    status = Column(
        String(20),
        default="pending",
        nullable=False,
        index=True
    )

    retry_count = Column(
        Integer,
        default=0,
        nullable=False
    )

    next_retry_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    resolved_at = Column(
        DateTime,
        nullable=True
    )


class LiquidityAlert(Base):
    __tablename__ = "liquidity_alerts"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    bank_bic = Column(
        String(11),
        nullable=False,
        index=True
    )

    alert_type = Column(
        String(50),
        nullable=False,
        index=True
    )

    message = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    resolved = Column(
        String(20),
        default="open",
        nullable=False,
        index=True
    )