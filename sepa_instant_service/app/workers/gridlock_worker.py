from sqlalchemy import select
from datetime import datetime, timedelta
import httpx

from sepa_instant_service.app.config import settings
from sepa_instant_service.app.database import AsyncSessionLocal
from sepa_instant_service.app.models.instant_transfer import (
    InstantTransfer,
    InstantTransferStatus
)
from sepa_instant_service.app.models.pending_transfer_queue import (
    PendingTransferQueue,
    LiquidityAlert
)
from sepa_instant_service.app.workers.celery import celery_app


MAX_RETRIES = 20


@celery_app.task(
    name="sepa_instant_service.app.workers.gridlock_worker.resolve_pending_transfers"
)
def resolve_pending_transfers():
    import asyncio
    return asyncio.run(_resolve_pending())


async def _resolve_pending():

    async with AsyncSessionLocal() as db:

        now = datetime.utcnow()

        pending_result = await db.execute(
            select(PendingTransferQueue)
            .where(
                PendingTransferQueue.resolved_at == None,
                PendingTransferQueue.retry_count < MAX_RETRIES,
                PendingTransferQueue.next_retry_at <= now
            )
            .order_by(PendingTransferQueue.created_at)
        )

        pending_transfers = pending_result.scalars().all()

        settled = 0
        failed = 0
        retried = 0

        async with httpx.AsyncClient(
            verify=False,
            timeout=30.0
        ) as client:

            for pending in pending_transfers:

                try:

                    transfer_result = await db.execute(
                        select(InstantTransfer).where(
                            InstantTransfer.transfer_id == pending.transfer_id
                        )
                    )
                    orig = transfer_result.scalar_one_or_none()

                    response = await client.post(
                        f"{settings.target_url}/settle/payment",
                        json={
                            "transaction_id": pending.transfer_id,
                            "sender_iban": orig.sender_iban if orig else None,
                            "receiver_iban": orig.receiver_iban if orig else None,
                            "sender_bic": pending.sender_bic,
                            "receiver_bic": pending.receiver_bic,
                            "amount": float(pending.amount),
                            "currency": "EUR",
                            "description": orig.description if orig else None,
                            "service": "sepa_instant_retry"
                        }
                    )

                    data = response.json()

                    print(
                        f"[GRIDLOCK] Retrying transfer "
                        f"{pending.transfer_id} "
                        f"status={response.status_code}"
                    )

                    if response.status_code == 200:

                        settlement_status = data.get("status")

                        if settlement_status == "settled":

                            pending.resolved_at = datetime.utcnow()
                            pending.status = "resolved"

                            transfer_result = await db.execute(
                                select(InstantTransfer).where(
                                    InstantTransfer.transfer_id
                                    == pending.transfer_id
                                )
                            )

                            transfer = transfer_result.scalar_one_or_none()

                            if transfer:
                                transfer.status = (
                                    InstantTransferStatus.SETTLED
                                )
                                transfer.processed_at = datetime.utcnow()

                            settled += 1

                            print(
                                f"[GRIDLOCK] Transfer settled "
                                f"{pending.transfer_id}"
                            )

                        elif settlement_status == "pending":

                            pending.retry_count += 1

                            retry_delay = min(
                                pending.retry_count * 2,
                                30
                            )

                            pending.next_retry_at = (
                                datetime.utcnow()
                                + timedelta(minutes=retry_delay)
                            )

                            retried += 1

                            print(
                                f"[GRIDLOCK] Still pending "
                                f"{pending.transfer_id} "
                                f"retry={pending.retry_count}"
                            )

                        else:

                            pending.status = "failed"
                            pending.resolved_at = datetime.utcnow()

                            failed += 1

                            print(
                                f"[GRIDLOCK] Failed permanently "
                                f"{pending.transfer_id}"
                            )

                    else:

                        pending.retry_count += 1

                        pending.next_retry_at = (
                            datetime.utcnow()
                            + timedelta(minutes=5)
                        )

                        print(
                            f"[GRIDLOCK] HTTP error "
                            f"{pending.transfer_id}"
                        )

                except Exception as e:

                    pending.retry_count += 1

                    pending.next_retry_at = (
                        datetime.utcnow()
                        + timedelta(minutes=5)
                    )

                    print(
                        f"[GRIDLOCK] Exception "
                        f"{pending.transfer_id}: {e}"
                    )

        await db.commit()

        return {
            "processed": len(pending_transfers),
            "settled": settled,
            "failed": failed,
            "retried": retried,
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(
    name="sepa_instant_service.app.workers.gridlock_worker.check_liquidity_alerts"
)
def check_liquidity_alerts():
    import asyncio
    return asyncio.run(_check_alerts())


async def _check_alerts():

    async with AsyncSessionLocal() as db:

        alerts_result = await db.execute(
            select(LiquidityAlert).where(
                LiquidityAlert.resolved == "open"
            )
        )

        alerts = alerts_result.scalars().all()

        two_hours_ago = (
            datetime.utcnow() - timedelta(hours=2)
        )

        expired_count = 0

        for alert in alerts:

            if alert.created_at < two_hours_ago:

                alert.resolved = "expired"

                alert_msg = LiquidityAlert(
                    bank_bic=alert.bank_bic,
                    alert_type="bank_blocked_2h",
                    message=(
                        f"Bank {alert.bank_bic} "
                        f"blocked due to prolonged "
                        f"liquidity shortage"
                    )
                )

                db.add(alert_msg)

                expired_count += 1

        await db.commit()

        return {
            "expired_alerts": expired_count,
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(
    name="sepa_instant_service.app.workers.gridlock_worker.gridlock_resolution"
)
def gridlock_resolution():
    return resolve_pending_transfers()


@celery_app.task(
    name="sepa_instant_service.app.workers.gridlock_worker.liquidity_monitoring"
)
def liquidity_monitoring():
    return check_liquidity_alerts()