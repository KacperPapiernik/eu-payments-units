from sqlalchemy import select
from datetime import datetime, timedelta
import httpx
from decimal import Decimal

from sepa_instant_service.app.config import settings
from sepa_instant_service.app.database import AsyncSessionLocal
from sepa_instant_service.app.models.instant_transfer import InstantTransfer, InstantTransferStatus
from sepa_instant_service.app.models.pending_transfer_queue import PendingTransferQueue, LiquidityAlert
from sepa_instant_service.app.workers.celery import celery_app


@celery_app.task(name="sepa_instant_service.app.workers.gridlock_worker.resolve_pending_transfers")
def resolve_pending_transfers():
    import asyncio
    return asyncio.run(_resolve_pending())


async def _resolve_pending():
    async with AsyncSessionLocal() as db:
        pending_result = await db.execute(
            select(PendingTransferQueue).where(PendingTransferQueue.resolved == None)
        )
        pending_transfers = pending_result.scalars().all()
        
        for pending in pending_transfers:
            try:
                async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                    response = await client.post(
                        f"{settings.target_url}/settle/payment",
                        json={
                            "transaction_id": pending.transfer_id,
                            "sender_bic": pending.sender_bic,
                            "receiver_bic": pending.receiver_bic,
                            "amount": float(pending.amount),
                            "currency": "EUR",
                            "service": "sepa_instant_retry"
                        }
                    )
                    
                    if response.status_code == 200:
                        pending.resolved_at = datetime.utcnow()
                        
                        transfer_result = await db.execute(
                            select(InstantTransfer).where(
                                InstantTransfer.transfer_id == pending.transfer_id
                            )
                        )
                        transfer = transfer_result.scalar_one_or_none()
                        if transfer:
                            transfer.status = InstantTransferStatus.SETTLED
                            transfer.processed_at = datetime.utcnow()
            except Exception as e:
                print(f"Failed to resolve transfer {pending.transfer_id}: {e}")
        
        await db.commit()
        
        return {
            "processed": len(pending_transfers),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(name="sepa_instant_service.app.workers.gridlock_worker.check_liquidity_alerts")
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
        
        two_hours_ago = datetime.utcnow() - timedelta(hours=2)
        
        for alert in alerts:
            if alert.created_at < two_hours_ago:
                alert.resolved = "expired"
                
                alert_msg = LiquidityAlert(
                    bank_bic=alert.bank_bic,
                    alert_type="bank_blocked_2h",
                    message=f"Bank {alert.bank_bic} blocked due to 2h lack of liquidity"
                )
                db.add(alert_msg)
        
        await db.commit()
        
        return {
            "expired_alerts": sum(1 for a in alerts if a.created_at < two_hours_ago),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(name="sepa_instant_service.app.workers.gridlock_worker.gridlock_resolution")
def gridlock_resolution():
    return resolve_pending_transfers()


@celery_app.task(name="sepa_instant_service.app.workers.gridlock_worker.liquidity_monitoring")
def liquidity_monitoring():
    return check_liquidity_alerts()