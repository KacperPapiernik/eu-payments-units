from fastapi import APIRouter, BackgroundTasks
from datetime import datetime

from target_service.app.schemas.notify import BatchTransferNotification, SessionReportNotification
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


@router.post("/session-report")
async def notify_session_report(
    notification: SessionReportNotification,
    background_tasks: BackgroundTasks,
):
    for bank in notification.banks:
        background_tasks.add_task(
            send_webhook,
            receiver_bic=bank.bank_bic,
            event="session.completed",
            transfer_id=notification.session_id,
            sender_bic=notification.session_id,
            amount=abs(bank.net_position),
            currency="EUR",
            description=f"Session {notification.session_id[:12]}... completed. "
                        f"Credits: {bank.total_credits}, Debits: {bank.total_debits}, "
                        f"Net: {bank.net_position}",
            settled_at=datetime.utcnow(),
        )

    return {
        "status": "notified",
        "banks_count": len(notification.banks),
        "session_id": notification.session_id,
    }
