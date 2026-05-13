from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from sepa_batch_service.app.database import get_db
from sepa_batch_service.app.models.batch_session import BatchSession, SessionStatus
from sepa_batch_service.app.models.queued_transfer import QueuedTransfer, TransferStatus
from sepa_batch_service.app.schemas.transfer import TransferRequest, TransferResponse, BatchSubmissionRequest, BatchSubmissionResponse
from shared.security.iban_validator import validate_iban

router = APIRouter(prefix="/transfers", tags=["transfers"])


def validate_transfer_iban(iban: str, field_name: str):
    valid, error = validate_iban(iban)
    if not valid:
        raise HTTPException(status_code=400, detail=f"{field_name}: {error}")


@router.post("", response_model=TransferResponse)
async def submit_transfer(transfer: TransferRequest, db: AsyncSession = Depends(get_db)):
    validate_transfer_iban(transfer.sender_iban, "sender_iban")
    validate_transfer_iban(transfer.receiver_iban, "receiver_iban")
    
    result = await db.execute(
        select(BatchSession).where(BatchSession.status == SessionStatus.OPEN)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        session = BatchSession(
            session_id=str(uuid.uuid4()),
            status=SessionStatus.OPEN
        )
        db.add(session)
        await db.flush()
    
    transfer_id = str(uuid.uuid4())
    
    queued = QueuedTransfer(
        transfer_id=transfer_id,
        session_id=session.session_id,
        sender_iban=transfer.sender_iban,
        receiver_iban=transfer.receiver_iban,
        sender_bic=transfer.sender_bic,
        receiver_bic=transfer.receiver_bic,
        amount=transfer.amount,
        currency=transfer.currency,
        description=transfer.description,
        status=TransferStatus.QUEUED
    )
    db.add(queued)
    
    session.transaction_count += 1
    
    await db.commit()
    await db.refresh(queued)
    
    return TransferResponse(
        transfer_id=queued.transfer_id,
        status=queued.status.value,
        session_id=session.session_id,
        created_at=queued.created_at
    )


@router.post("/batch", response_model=BatchSubmissionResponse)
async def submit_batch(batch: BatchSubmissionRequest, db: AsyncSession = Depends(get_db)):
    for t in batch.transfers:
        validate_transfer_iban(t.sender_iban, "sender_iban")
        validate_transfer_iban(t.receiver_iban, "receiver_iban")
    
    result = await db.execute(
        select(BatchSession).where(BatchSession.status == SessionStatus.OPEN)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        session_id = batch.session_id or str(uuid.uuid4())
        session = BatchSession(
            session_id=session_id,
            status=SessionStatus.OPEN
        )
        db.add(session)
        await db.flush()
    
    for t in batch.transfers:
        transfer_id = str(uuid.uuid4())
        queued = QueuedTransfer(
            transfer_id=transfer_id,
            session_id=session.session_id,
            sender_iban=t.sender_iban,
            receiver_iban=t.receiver_iban,
            sender_bic=t.sender_bic,
            receiver_bic=t.receiver_bic,
            amount=t.amount,
            currency=t.currency,
            description=t.description,
            status=TransferStatus.QUEUED
        )
        db.add(queued)
        session.transaction_count += 1
    
    await db.commit()
    
    return BatchSubmissionResponse(
        session_id=session.session_id,
        transfers_queued=len(batch.transfers),
        status="queued"
    )