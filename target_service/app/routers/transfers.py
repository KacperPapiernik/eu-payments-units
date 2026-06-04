from fastapi import APIRouter, Depends, HTTPException, Body, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from xml.etree import ElementTree as ET
import uuid

from target_service.app.database import get_db
from target_service.app.models.bank import Bank, SettlementAccount
from target_service.app.models.rtgs_transfer import RtgsTransfer, RtgsTransferStatus
from target_service.app.models.settlement_transaction import (
    SettlementTransaction,
    TransactionStatus,
)
from target_service.app.schemas.transfer import (
    RtgsTransferRequest,
    RtgsTransferResponse,
    TransferStatusResponse,
)
from shared.security.iban_validator import validate_iban
from shared.sepa_xml import parse_iso20022_payment_xml, build_payment_status_xml

router = APIRouter(prefix="/transfers", tags=["rtgs_transfers"])


def validate_iban_strict(iban: str, field_name: str):
    valid, error = validate_iban(iban)
    if not valid:
        raise HTTPException(status_code=400, detail=f"{field_name}: {error}")


async def process_rtgs_transfer(
    transfer: RtgsTransferRequest,
    db: AsyncSession,
) -> RtgsTransferResponse:
    validate_iban_strict(transfer.sender_iban, "sender_iban")
    validate_iban_strict(transfer.receiver_iban, "receiver_iban")

    sender_result = await db.execute(
        select(Bank).where(Bank.bic == transfer.sender_bic)
    )
    sender = sender_result.scalar_one_or_none()
    if not sender:
        raise HTTPException(
            status_code=404,
            detail=f"Sender bank not found: {transfer.sender_bic}"
        )

    receiver_result = await db.execute(
        select(Bank).where(Bank.bic == transfer.receiver_bic)
    )
    receiver = receiver_result.scalar_one_or_none()
    if not receiver:
        raise HTTPException(
            status_code=404,
            detail=f"Receiver bank not found: {transfer.receiver_bic}"
        )

    if sender.is_blocked:
        raise HTTPException(
            status_code=400,
            detail=f"Sender bank is blocked: {transfer.sender_bic}"
        )
    if receiver.is_blocked:
        raise HTTPException(
            status_code=400,
            detail=f"Receiver bank is blocked: {transfer.receiver_bic}"
        )

    sender_account_result = await db.execute(
        select(SettlementAccount).where(
            SettlementAccount.bank_id == sender.id
        )
    )
    sender_account = sender_account_result.scalar_one_or_none()
    if not sender_account:
        raise HTTPException(
            status_code=404,
            detail=f"Settlement account not found for sender: {transfer.sender_bic}"
        )

    receiver_account_result = await db.execute(
        select(SettlementAccount).where(
            SettlementAccount.bank_id == receiver.id
        )
    )
    receiver_account = receiver_account_result.scalar_one_or_none()
    if not receiver_account:
        raise HTTPException(
            status_code=404,
            detail=f"Settlement account not found for receiver: {transfer.receiver_bic}"
        )

    available = sender_account.available_balance
    if available < transfer.amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient funds. "
                f"Available: {available}, "
                f"Required: {transfer.amount}"
            )
        )

    transfer_id = str(uuid.uuid4())

    rtgs_transfer = RtgsTransfer(
        transfer_id=transfer_id,
        sender_iban=transfer.sender_iban,
        receiver_iban=transfer.receiver_iban,
        sender_bic=transfer.sender_bic,
        receiver_bic=transfer.receiver_bic,
        amount=transfer.amount,
        currency=transfer.currency,
        description=transfer.description,
        status=RtgsTransferStatus.PENDING,
    )
    db.add(rtgs_transfer)
    await db.flush()

    sender_account.balance -= transfer.amount
    sender_account.available_balance -= transfer.amount
    receiver_account.balance += transfer.amount
    receiver_account.available_balance += transfer.amount

    settlement = SettlementTransaction(
        transaction_id=transfer_id,
        sender_bic=transfer.sender_bic,
        receiver_bic=transfer.receiver_bic,
        amount=transfer.amount,
        currency=transfer.currency,
        status=TransactionStatus.SETTLED,
        description=transfer.description,
        settled_at=datetime.utcnow(),
        service="rtgs",
    )
    db.add(settlement)

    rtgs_transfer.status = RtgsTransferStatus.SETTLED
    rtgs_transfer.processed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(rtgs_transfer)

    return RtgsTransferResponse(
        transfer_id=rtgs_transfer.transfer_id,
        status=rtgs_transfer.status.value,
        created_at=rtgs_transfer.created_at,
    )


@router.post("", response_model=RtgsTransferResponse, include_in_schema=False)
async def submit_transfer(
    transfer: RtgsTransferRequest,
    db: AsyncSession = Depends(get_db),
):
    return await process_rtgs_transfer(transfer, db)


@router.post(
    "/xml",
    response_class=Response,
    responses={
        200: {
            "content": {"application/xml": {}},
            "description": "XML payment status response",
        }
    },
)
async def submit_transfer_xml(
    xml_body: str = Body(..., media_type="application/xml"),
    db: AsyncSession = Depends(get_db),
):
    try:
        parsed = parse_iso20022_payment_xml(xml_body)

        transfer = RtgsTransferRequest(
            sender_iban=parsed["sender_iban"],
            receiver_iban=parsed["receiver_iban"],
            sender_bic=parsed["sender_bic"],
            receiver_bic=parsed["receiver_bic"],
            amount=parsed["amount"],
            currency=parsed.get("currency") or "EUR",
            description=parsed.get("description") or "XML RTGS transfer",
        )

        result = await process_rtgs_transfer(transfer, db)

        xml_response = build_payment_status_xml(
            status="ACSC",
            transfer_id=result.transfer_id,
            session_id=None,
        )

        return Response(
            content=xml_response,
            media_type="application/xml",
        )

    except (ValueError, ET.ParseError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{transfer_id}", response_model=TransferStatusResponse)
async def get_transfer_status(
    transfer_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RtgsTransfer).where(RtgsTransfer.transfer_id == transfer_id)
    )
    transfer = result.scalar_one_or_none()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    return TransferStatusResponse(
        transfer_id=transfer.transfer_id,
        status=transfer.status.value,
        sender_bic=transfer.sender_bic,
        receiver_bic=transfer.receiver_bic,
        amount=transfer.amount,
        description=transfer.description,
        error_message=transfer.error_message,
        created_at=transfer.created_at,
        processed_at=transfer.processed_at,
    )


@router.get("")
async def get_transfers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RtgsTransfer)
        .order_by(RtgsTransfer.created_at.desc())
        .limit(100)
    )
    transfers = result.scalars().all()

    return [
        {
            "transfer_id": t.transfer_id,
            "sender_iban": t.sender_iban,
            "receiver_iban": t.receiver_iban,
            "sender_bic": t.sender_bic,
            "receiver_bic": t.receiver_bic,
            "amount": float(t.amount),
            "currency": t.currency,
            "description": t.description,
            "status": t.status.value,
            "error_message": t.error_message,
            "created_at": t.created_at.isoformat(),
            "processed_at": t.processed_at.isoformat() if t.processed_at else None,
        }
        for t in transfers
    ]
