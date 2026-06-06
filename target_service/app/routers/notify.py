from fastapi import APIRouter, BackgroundTasks
from datetime import datetime

from target_service.app.schemas.notify import BatchTransferNotification
from target_service.app.services.webhook_notifier import send_webhook

router = APIRouter(tags=["notifications"])


@router.post("/batch-transfers")
async def notify_batch_transfers(
    notification: BatchTransferNotification,
    background_tasks: BackgroundTasks,
):
    for t in notification.transfers:
        background_tasks.add_task(
            send_webhook,
            receiver_bic=t.receiver_bic,
            event="batch.transfer.settled",
            transfer_id=t.transfer_id,
            sender_bic=t.sender_bic,
            amount=t.amount,
            currency=t.currency,
            description=t.description,
            settled_at=datetime.utcnow(),
            sender_iban=t.sender_iban,
            receiver_iban=t.receiver_iban,
        )

    return {
        "status": "notified",
        "transfers_count": len(notification.transfers),
    }
