from app.schemas.payment import PaymentRequest
from app.core.database import save_transaction
from datetime import datetime, timedelta
import pytz


async def process(req: PaymentRequest) -> dict:
    cet = pytz.timezone('Europe/Warsaw')
    now = datetime.now(cet)
    weekday = now.weekday()
    hour = now.hour
    
    if weekday >= 5 or hour >= 16:
        next_day = now + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        scheduled_for = next_day.replace(hour=7, minute=0, second=0, microsecond=0)
        
        tx = await save_transaction(
            sender_iban=req.sender_iban,
            receiver_iban=req.receiver_iban,
            amount=req.amount,
            currency=req.currency,
            payment_type="SEPA",
            description=req.description,
            status="SCHEDULED",
            scheduled_for=scheduled_for,
            message=f"SEPA transfer scheduled for {scheduled_for.strftime('%Y-%m-%d %H:%M')} CET"
        )
    else:
        tx = await save_transaction(
            sender_iban=req.sender_iban,
            receiver_iban=req.receiver_iban,
            amount=req.amount,
            currency=req.currency,
            payment_type="SEPA",
            description=req.description,
            status="RECEIVED",
            message="SEPA transfer received, awaiting processing"
        )
    
    return {
        "transaction_id": tx.id,
        "status": tx.status.value,
        "payment_type": "SEPA",
        "created_at": tx.created_at,
        "message": tx.message
    }