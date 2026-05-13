import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class AuditEventType(Enum):
    TRANSFER_RECEIVED = "transfer_received"
    TRANSFER_SETTLED = "transfer_settled"
    TRANSFER_REJECTED = "transfer_rejected"
    BANK_BLOCKED = "bank_blocked"
    BANK_UNBLOCKED = "bank_unblocked"
    LIQUIDITY_INJECTED = "liquidity_injected"
    SESSION_OPENED = "session_opened"
    SESSION_CLOSED = "session_closed"
    SESSION_NETTING_COMPLETE = "session_netting_complete"
    GRIDLOCK_DETECTED = "gridlock_detected"
    GRIDLOCK_RESOLVED = "gridlock_resolved"


class AuditLogger:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logging.getLogger(f"audit.{service_name}")
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_event(
        self,
        event_type: AuditEventType,
        details: Dict[str, Any],
        bank_bic: Optional[str] = None,
        amount: Optional[float] = None,
        reference: Optional[str] = None
    ):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "event_type": event_type.value,
            "bank_bic": bank_bic,
            "amount": amount,
            "reference": reference,
            "details": details
        }
        
        self.logger.info(json.dumps(event))

    def log_transfer_received(self, bank_bic: str, transfer_id: str, amount: float):
        self.log_event(
            AuditEventType.TRANSFER_RECEIVED,
            {"transfer_id": transfer_id},
            bank_bic=bank_bic,
            amount=amount,
            reference=transfer_id
        )

    def log_transfer_settled(self, transfer_id: str, bank_bic: str, amount: float):
        self.log_event(
            AuditEventType.TRANSFER_SETTLED,
            {"transfer_id": transfer_id},
            bank_bic=bank_bic,
            amount=amount,
            reference=transfer_id
        )

    def log_bank_blocked(self, bank_bic: str, reason: str):
        self.log_event(
            AuditEventType.BANK_BLOCKED,
            {"reason": reason},
            bank_bic=bank_bic
        )

    def log_bank_unblocked(self, bank_bic: str):
        self.log_event(
            AuditEventType.BANK_UNBLOCKED,
            {},
            bank_bic=bank_bic
        )

    def log_liquidity_injected(self, bank_bic: str, amount: float):
        self.log_event(
            AuditEventType.LIQUIDITY_INJECTED,
            {},
            bank_bic=bank_bic,
            amount=amount
        )

    def log_session_closed(self, session_id: str, total_amount: float):
        self.log_event(
            AuditEventType.SESSION_CLOSED,
            {"session_id": session_id},
            amount=total_amount,
            reference=session_id
        )


def create_audit_logger(service_name: str) -> AuditLogger:
    return AuditLogger(service_name)