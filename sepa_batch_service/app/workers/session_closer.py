from sqlalchemy import select
from datetime import datetime
from decimal import Decimal
import httpx

from sepa_batch_service.app.config import settings
from sepa_batch_service.app.database import AsyncSessionLocal, init_db
from sepa_batch_service.app.models.batch_session import BatchSession, SessionStatus
from sepa_batch_service.app.models.queued_transfer import QueuedTransfer, TransferStatus
from sepa_batch_service.app.models.netting_result import NettingResult
from sepa_batch_service.app.workers.celery import celery_app

import asyncio

_loop = None


def _get_event_loop():
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


@celery_app.task(name="sepa_batch_service.app.workers.session_closer.close_session_and_settle")
def close_session_and_settle():
    async def _close_session():
        await init_db()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(BatchSession).where(BatchSession.status == SessionStatus.OPEN)
            )
            sessions = result.scalars().all()

            if not sessions:
                return {"status": "no_open_sessions"}

            results = []
            for session in sessions:
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
                        if netting.net_position > 0:
                            sender_bic = "ECBCLS00XXX"
                            receiver_bic = bank_bic
                        else:
                            sender_bic = bank_bic
                            receiver_bic = "ECBCLS00XXX"

                        await send_to_target(
                            sender_bic=sender_bic,
                            receiver_bic=receiver_bic,
                            amount=abs(netting.net_position),
                            transaction_id=f"NETT-{session.session_id}-{bank_bic}",
                            service="sepa_batch"
                        )

                await notify_individual_transfers(transfers, settings.target_url)

                for t in transfers:
                    t.status = TransferStatus.PROCESSED
                    t.processed_at = datetime.utcnow()

                session.status = SessionStatus.CLOSED
                session.closed_at = datetime.utcnow()
                session.total_credits = sum(p["credits"] for p in bank_positions.values())
                session.total_debits = sum(p["debits"] for p in bank_positions.values())

                results.append({
                    "session_id": session.session_id,
                    "transfers_processed": len(transfers),
                    "banks_in_netting": len(bank_positions)
                })

            await db.commit()

            return {"sessions_closed": len(results), "details": results}

    return _get_event_loop().run_until_complete(_close_session())


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

            response.raise_for_status()

            try:
                return response.json()
            except ValueError:
                return {
                    "status": "error",
                    "http_status": response.status_code,
                    "body": response.text
                }

    except Exception as e:
        print(f"Failed to send to TARGET: {e}")
        return {"error": str(e)}


async def notify_individual_transfers(transfers, target_url: str):
    payload = {
        "transfers": [
            {
                "transfer_id": t.transfer_id,
                "sender_bic": t.sender_bic,
                "receiver_bic": t.receiver_bic,
                "sender_iban": t.sender_iban,
                "receiver_iban": t.receiver_iban,
                "amount": float(t.amount),
                "currency": t.currency,
                "description": t.description,
            }
            for t in transfers
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{target_url}/notify/batch-transfers",
                json=payload,
            )
            response.raise_for_status()
    except Exception as e:
        print(f"Failed to notify individual transfers: {e}")


@celery_app.task(name="sepa_batch_service.app.workers.session_closer.periodic_session_close")
def periodic_session_close():
    return close_session_and_settle()