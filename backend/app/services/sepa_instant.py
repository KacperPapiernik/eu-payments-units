from app.schemas.payment import PaymentRequest
from app.core.database import save_transaction


async def process(req: PaymentRequest) -> dict:
    tx = await save_transaction(
        sender_iban=req.sender_iban,
        receiver_iban=req.receiver_iban,
        amount=req.amount,
        currency=req.currency,
        payment_type="SEPA_INSTANT",
        description=req.description,
        status="RECEIVED",
        message="SEPA Instant transfer received, processing immediately (target: <10s)"
    )
    
    return {
        "transaction_id": tx.id,
        "status": tx.status.value,
        "payment_type": "SEPA_INSTANT",
        "created_at": tx.created_at,
        "message": tx.message
    }