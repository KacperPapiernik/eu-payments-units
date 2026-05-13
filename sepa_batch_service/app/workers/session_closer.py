from sqlalchemy import select
from datetime import datetime
from decimal import Decimal
import httpx

from sepa_batch_service.app.config import settings
from sepa_batch_service.app.database import AsyncSessionLocal
from sepa_batch_service.app.models.batch_session import BatchSession, SessionStatus
from sepa_batch_service.app.models.queued_transfer import QueuedTransfer, TransferStatus
from sepa_batch_service.app.models.netting_result import NettingResult
from sepa_batch_service.app.workers.celery import celery_app


@celery_app.task(name="sepa_batch_service.app.workers.session_closer.close_session_and_settle")
def close_session_and_settle():
    import asyncio
    
    async def _close_session():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(BatchSession).where(BatchSession.status == SessionStatus.OPEN)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                return {"status": "no_open_sessions"}
            
            transfers_result = await db.execute(
                select(QueuedTransfer).where(
                    QueuedTransfer.session_id == session.session_id,
                    QueuedTransfer.status == TransferStatus.QUEUED
                )
            )
            transfers = transfers_result.scalars().all()
            
            bank_positions = {}
            for t in transfers:
                sender = t.sender_bic
                receiver = t.receiver_bic
                amount = t.amount
                
                if sender not in bank_positions:
                    bank_positions[sender] = {"credits": Decimal(0), "debits": Decimal(0)}
                if receiver not in bank_positions:
                    bank_positions[receiver] = {"credits": Decimal(0), "debits": Decimal(0)}
                
                bank_positions[sender]["debits"] += amount
                bank_positions[receiver]["credits"] += amount
            
            for bank_bic, pos in bank_positions.items():
                netting = NettingResult(
                    session_id=session.session_id,
                    bank_bic=bank_bic,
                    total_credits=pos["credits"],
                    total_debits=pos["debits"],
                    net_position=pos["credits"] - pos["debits"]
                )
                db.add(netting)
                
                if netting.net_position != 0:
                    await send_to_target(
                        sender_bic="SEPA_BATCH",
                        receiver_bic=bank_bic,
                        amount=abs(netting.net_position),
                        transaction_id=f"NETT-{session.session_id}-{bank_bic}",
                        service="sepa_batch"
                    )
            
            for t in transfers:
                t.status = TransferStatus.PROCESSED
                t.processed_at = datetime.utcnow()
            
            session.status = SessionStatus.CLOSED
            session.closed_at = datetime.utcnow()
            session.total_credits = sum(p["credits"] for p in bank_positions.values())
            session.total_debits = sum(p["debits"] for p in bank_positions.values())
            
            await db.commit()
            
            return {
                "session_id": session.session_id,
                "transfers_processed": len(transfers),
                "banks_in_netting": len(bank_positions)
            }
    
    return asyncio.run(_close_session())


async def send_to_target(sender_bic: str, receiver_bic: str, amount: Decimal, transaction_id: str, service: str):
    target_url = settings.target_url
    cert_path = settings.service_cert_path
    key_path = settings.service_key_path
    ca_path = settings.ca_cert_path
    
    payload = {
        "transaction_id": transaction_id,
        "sender_bic": sender_bic,
        "receiver_bic": receiver_bic,
        "amount": float(amount),
        "currency": "EUR",
        "service": service
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{target_url}/settle/payment",
                json=payload,
                timeout=30.0
            )
            return response.json()
    except Exception as e:
        print(f"Failed to send to TARGET: {e}")
        return {"error": str(e)}


@celery_app.task(name="sepa_batch_service.app.workers.session_closer.periodic_session_close")
def periodic_session_close():
    return close_session_and_settle()