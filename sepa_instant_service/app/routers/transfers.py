from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import uuid
import httpx
from decimal import Decimal

from sepa_instant_service.app.database import get_db
from sepa_instant_service.app.models.instant_transfer import InstantTransfer, InstantTransferStatus
from sepa_instant_service.app.models.pending_transfer_queue import PendingTransferQueue, LiquidityAlert
from sepa_instant_service.app.schemas.transfer import InstantTransferRequest, InstantTransferResponse, TransferStatusResponse
from shared.security.iban_validator import validate_iban

router = APIRouter(prefix="/transfers", tags=["transfers"])


def validate_iban_strict(iban: str, field_name: str):
    valid, error = validate_iban(iban)
    if not valid:
        raise HTTPException(status_code=400, detail=f"{field_name}: {error}")


async def send_to_target(sender_bic: str, receiver_bic: str, amount: Decimal, transaction_id: str, service: str, target_url: str, cert_path: str, key_path: str):
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
                f"{target_url}/settle/payment",
                json=payload
            )
            return response.json()
    except Exception as e:
        return {"error": str(e)}


@router.post("", response_model=InstantTransferResponse)
async def submit_instant_transfer(
    transfer: InstantTransferRequest,
    db: AsyncSession = Depends(get_db)
):
    from sepa_instant_service.app.config import settings
    
    validate_iban_strict(transfer.sender_iban, "sender_iban")
    validate_iban_strict(transfer.receiver_iban, "receiver_iban")
    
    transfer_id = str(uuid.uuid4())
    
    instant_transfer = InstantTransfer(
        transfer_id=transfer_id,
        sender_iban=transfer.sender_iban,
        receiver_iban=transfer.receiver_iban,
        sender_bic=transfer.sender_bic,
        receiver_bic=transfer.receiver_bic,
        amount=transfer.amount,
        currency=transfer.currency,
        description=transfer.description,
        status=InstantTransferStatus.PROCESSING
    )
    db.add(instant_transfer)
    await db.flush()
    
    result = await send_to_target(
        sender_bic=transfer.sender_bic,
        receiver_bic=transfer.receiver_bic,
        amount=transfer.amount,
        transaction_id=transfer_id,
        service="sepa_instant",
        target_url=settings.target_url,
        cert_path=settings.service_cert_path,
        key_path=settings.service_key_path
    )
    
    if "error" in result:
        pending = PendingTransferQueue(
            transfer_id=transfer_id,
            sender_bic=transfer.sender_bic,
            receiver_bic=transfer.receiver_bic,
            amount=transfer.amount,
            reason=result.get("error", "Unknown error")
        )
        db.add(pending)
        
        alert_result = await db.execute(
            select(LiquidityAlert).where(
                LiquidityAlert.bank_bic == transfer.sender_bic,
                LiquidityAlert.resolved == "open"
            )
        )
        existing_alert = alert_result.scalar_one_or_none()
        
        if not existing_alert:
            alert = LiquidityAlert(
                bank_bic=transfer.sender_bic,
                alert_type="insufficient_liquidity",
                message=f"Transfer {transfer_id} queued due to insufficient liquidity"
            )
            db.add(alert)
        
        instant_transfer.status = InstantTransferStatus.PENDING
    else:
        instant_transfer.status = InstantTransferStatus.SETTLED
        instant_transfer.processed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(instant_transfer)
    
    return InstantTransferResponse(
        transfer_id=instant_transfer.transfer_id,
        status=instant_transfer.status.value,
        created_at=instant_transfer.created_at
    )


@router.get("/{transfer_id}", response_model=TransferStatusResponse)
async def get_transfer_status(transfer_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InstantTransfer).where(InstantTransfer.transfer_id == transfer_id)
    )
    transfer = result.scalar_one_or_none()
    
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    
    return TransferStatusResponse(
        transfer_id=transfer.transfer_id,
        status=transfer.status.value,
        processed_at=transfer.processed_at,
        error_message=transfer.error_message
    )


@router.get("")
async def get_transfers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InstantTransfer).order_by(InstantTransfer.created_at.desc()).limit(100)
    )
    transfers = result.scalars().all()
    
    return [
        {
            "transfer_id": t.transfer_id,
            "sender_bic": t.sender_bic,
            "receiver_bic": t.receiver_bic,
            "amount": float(t.amount),
            "status": t.status.value,
            "created_at": t.created_at.isoformat()
        }
        for t in transfers
    ]