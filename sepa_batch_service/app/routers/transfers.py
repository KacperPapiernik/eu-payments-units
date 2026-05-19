from fastapi import APIRouter, Depends, HTTPException, Response, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from sepa_batch_service.app.database import get_db
from sepa_batch_service.app.models.batch_session import BatchSession, SessionStatus
from sepa_batch_service.app.models.queued_transfer import QueuedTransfer, TransferStatus
from sepa_batch_service.app.schemas.transfer import TransferRequest, TransferResponse
from shared.security.iban_validator import validate_iban
from shared.sepa_xml import parse_iso20022_payment_xml, build_payment_status_xml

router = APIRouter(prefix="/transfers", tags=["transfers"])


def validate_transfer_iban(iban: str, field_name: str):
    valid, error = validate_iban(iban)
    if not valid:
        raise HTTPException(status_code=400, detail=f"{field_name}: {error}")


async def queue_single_transfer(
    transfer: TransferRequest,
    db: AsyncSession,
) -> TransferResponse:
    validate_transfer_iban(transfer.sender_iban, "sender_iban")
    validate_transfer_iban(transfer.receiver_iban, "receiver_iban")

    result = await db.execute(
        select(BatchSession).where(BatchSession.status == SessionStatus.OPEN)
    )
    session = result.scalar_one_or_none()

    if not session:
        session = BatchSession(
            session_id=str(uuid.uuid4()),
            status=SessionStatus.OPEN,
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
        status=TransferStatus.QUEUED,
    )

    db.add(queued)
    session.transaction_count += 1

    await db.commit()
    await db.refresh(queued)

    return TransferResponse(
        transfer_id=queued.transfer_id,
        status=queued.status.value,
        session_id=session.session_id,
        created_at=queued.created_at,
    )


@router.post("", response_model=TransferResponse, include_in_schema=False) 
async def submit_transfer(
        transfer: TransferRequest, 
        db: AsyncSession = Depends(get_db), 
): 
    return await queue_single_transfer(transfer, db)

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

        transfer = TransferRequest(
            sender_iban=parsed["sender_iban"],
            receiver_iban=parsed["receiver_iban"],
            sender_bic=parsed["sender_bic"],
            receiver_bic=parsed["receiver_bic"],
            bank_bic=parsed["sender_bic"],
            amount=parsed["amount"],
            currency=parsed.get("currency") or "EUR",
            description=parsed.get("description") or "XML SEPA transfer",
        )

        result = await queue_single_transfer(transfer, db)

        xml_response = build_payment_status_xml(
            status="ACCP",
            transfer_id=result.transfer_id,
            session_id=result.session_id,
        )

        return Response(
            content=xml_response,
            media_type="application/xml",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))