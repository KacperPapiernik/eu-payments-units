from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime
from decimal import Decimal
import httpx
import json

from sepa_batch_service.app.database import get_db
from sepa_batch_service.app.models.batch_session import BatchSession, SessionStatus
from sepa_batch_service.app.models.queued_transfer import QueuedTransfer, TransferStatus
from sepa_batch_service.app.models.netting_result import NettingResult, SessionReport

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def perform_netting(session_id: str, db: AsyncSession):
    transfers_result = await db.execute(
        select(QueuedTransfer).where(
            QueuedTransfer.session_id == session_id,
            QueuedTransfer.status == TransferStatus.QUEUED
        )
    )
    transfers = transfers_result.scalars().all()
    
    if not transfers:
        return {
            "status": "no_transfers",
            "message": "No queued transfers in this session"
        }
    
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
    
    settlements_sent = 0
    total_amount = Decimal(0)
    netting_details = []
    blocked_banks = []
    
    from sepa_batch_service.app.config import settings
    
    for bank_bic, pos in bank_positions.items():
        netting = NettingResult(
            session_id=session_id,
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
            
            settlement_result = await send_to_target(
                sender_bic=sender_bic,
                receiver_bic=receiver_bic,
                amount=abs(netting.net_position),
                transaction_id=f"NETT-{session_id}-{bank_bic}",
                service="sepa_batch"
            )
            
            if netting.net_position < 0 and settlement_result.get("status") == "error":
                print(f"[NETTING] Settlement failed for {bank_bic}, blocking bank")
                try:
                    async with httpx.AsyncClient(verify=False, timeout=15.0) as block_client:
                        await block_client.post(
                            f"{settings.target_url}/banks/block/{bank_bic}"
                        )
                    blocked_banks.append(bank_bic)
                except Exception:
                    print(f"[NETTING] Failed to block {bank_bic} as well")
            
            settlements_sent += 1
            total_amount += abs(netting.net_position)
            netting_details.append({
                "bank_bic": bank_bic,
                "net_position": float(netting.net_position),
                "settlement_result": settlement_result
            })
    
    await notify_individual_transfers(transfers, settings.target_url)

    await notify_session_report(
        session_id=session_id,
        status="settled",
        bank_positions=bank_positions,
        target_url=settings.target_url,
    )

    for t in transfers:
        t.status = TransferStatus.PROCESSED
        t.processed_at = datetime.utcnow()

    await db.commit()
    
    return {
        "transfers_processed": len(transfers),
        "settlements_sent": settlements_sent,
        "total_amount": float(total_amount),
        "blocked_banks": blocked_banks,
        "bank_positions": {
            bic: {
                "credits": float(pos["credits"]),
                "debits": float(pos["debits"]),
                "net_position": float(pos["credits"] - pos["debits"])
            }
            for bic, pos in bank_positions.items()
        },
        "netting_details": netting_details
    }


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
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.post(
                f"{target_url}/notify/batch-transfers",
                json=payload,
            )
            response.raise_for_status()
    except Exception as e:
        print(f"Failed to notify individual transfers: {e}")


async def notify_session_report(session_id: str, status: str, bank_positions: dict, target_url: str):
    banks = [
        {
            "bank_bic": bic,
            "total_credits": float(pos["credits"]),
            "total_debits": float(pos["debits"]),
            "net_position": float(pos["credits"] - pos["debits"]),
        }
        for bic, pos in bank_positions.items()
    ]
    payload = {
        "session_id": session_id,
        "status": status,
        "total_transactions": len(banks),
        "banks": banks,
    }
    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            await client.post(
                f"{target_url}/notify/session-report",
                json=payload,
            )
    except Exception as e:
        print(f"Failed to notify session report: {e}")


async def send_to_target(sender_bic: str, receiver_bic: str, amount: Decimal, transaction_id: str, service: str):
    from sepa_batch_service.app.config import settings
    
    payload = {
        "transaction_id": transaction_id,
        "sender_bic": sender_bic,
        "receiver_bic": receiver_bic,
        "amount": float(amount),
        "currency": "EUR",
        "service": service
    }
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.post(
                f"{settings.target_url}/settle/payment",
                json=payload
            )
            return {"status": "success", "response": response.json()}
    except Exception as e:
        print(f"Failed to send to TARGET: {e}")
        return {"status": "error", "error": str(e)}


@router.get("")
async def get_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BatchSession).order_by(BatchSession.opened_at.desc()))
    sessions = result.scalars().all()
    return [
        {
            "session_id": s.session_id,
            "status": s.status.value,
            "opened_at": s.opened_at.isoformat(),
            "closed_at": s.closed_at.isoformat() if s.closed_at else None,
            "transaction_count": s.transaction_count,
            "total_credits": float(s.total_credits),
            "total_debits": float(s.total_debits)
        }
        for s in sessions
    ]


@router.get("/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BatchSession).where(BatchSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return {"error": "Session not found"}
    
    netting_result = await db.execute(
        select(NettingResult).where(NettingResult.session_id == session_id)
    )
    netting = netting_result.scalars().all()
    
    return {
        "session_id": session.session_id,
        "status": session.status.value,
        "opened_at": session.opened_at.isoformat(),
        "closed_at": session.closed_at.isoformat() if session.closed_at else None,
        "transaction_count": session.transaction_count,
        "total_credits": float(session.total_credits),
        "total_debits": float(session.total_debits),
        "netting_results": [
            {
                "bank_bic": n.bank_bic,
                "total_credits": float(n.total_credits),
                "total_debits": float(n.total_debits),
                "net_position": float(n.net_position)
            }
            for n in netting
        ]
    }


@router.get("/{session_id}/position/{bank_bic}")
async def get_bank_position(session_id: str, bank_bic: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BatchSession).where(BatchSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return {"error": "Session not found"}

    transfers_result = await db.execute(
        select(QueuedTransfer).where(
            QueuedTransfer.session_id == session_id,
            QueuedTransfer.status == TransferStatus.QUEUED
        )
    )
    transfers = transfers_result.scalars().all()

    credits = Decimal(0)
    debits = Decimal(0)
    transfer_list = []

    for t in transfers:
        if t.receiver_bic == bank_bic:
            credits += t.amount
            transfer_list.append({
                "direction": "incoming",
                "from": t.sender_bic,
                "amount": float(t.amount),
            })
        if t.sender_bic == bank_bic:
            debits += t.amount
            transfer_list.append({
                "direction": "outgoing",
                "to": t.receiver_bic,
                "amount": float(t.amount),
            })

    net_position = credits - debits

    return {
        "session_id": session_id,
        "session_status": session.status.value,
        "bank_bic": bank_bic,
        "total_credits": float(credits),
        "total_debits": float(debits),
        "net_position": float(net_position),
        "transaction_count": len(transfer_list),
        "transfers": transfer_list,
    }


@router.post("/close/{session_id}")
async def close_session(session_id: str, db: AsyncSession = Depends(get_db)):
    from datetime import datetime
    
    result = await db.execute(
        select(BatchSession).where(BatchSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return {"error": "Session not found"}
    
    if session.status != SessionStatus.OPEN:
        return {"error": f"Session is {session.status.value}, cannot close"}
    
    session.status = SessionStatus.CLOSED
    session.closed_at = datetime.utcnow()
    
    await db.commit()
    
    netting_result = await perform_netting(session_id, db)
    
    session.total_credits = Decimal(str(netting_result.get("total_amount", 0)))
    session.total_debits = Decimal(str(netting_result.get("total_amount", 0)))
    await db.commit()
    
    return {
        "session_id": session.session_id,
        "status": "closed",
        "closed_at": session.closed_at.isoformat(),
        "netting": netting_result
    }
