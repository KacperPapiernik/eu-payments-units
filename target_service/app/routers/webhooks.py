import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from target_service.app.database import get_db
from target_service.app.models.bank import Bank
from target_service.app.models.bank_webhook import BankWebhook
from target_service.app.schemas.webhook import (
    WebhookRegistrationRequest,
    WebhookRegistrationResponse,
    WebhookConfigResponse,
)

router = APIRouter(prefix="/banks/{bic}/webhook", tags=["webhooks"])


async def get_bank_or_404(bic: str, db: AsyncSession):
    result = await db.execute(select(Bank).where(Bank.bic == bic))
    bank = result.scalar_one_or_none()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    return bank


@router.post("", response_model=WebhookRegistrationResponse)
async def register_webhook(
    bic: str,
    request: WebhookRegistrationRequest,
    db: AsyncSession = Depends(get_db),
):
    await get_bank_or_404(bic, db)

    result = await db.execute(
        select(BankWebhook).where(BankWebhook.bank_bic == bic)
    )
    existing = result.scalar_one_or_none()

    secret = request.secret or secrets.token_hex(32)

    if existing:
        existing.url = request.url
        existing.secret = secret
        existing.is_active = True
    else:
        webhook = BankWebhook(
            bank_bic=bic,
            url=request.url,
            secret=secret,
        )
        db.add(webhook)

    await db.commit()

    return WebhookRegistrationResponse(
        bank_bic=bic,
        url=request.url,
        secret=secret,
    )


@router.get("", response_model=WebhookConfigResponse)
async def get_webhook(
    bic: str,
    db: AsyncSession = Depends(get_db),
):
    await get_bank_or_404(bic, db)

    result = await db.execute(
        select(BankWebhook).where(BankWebhook.bank_bic == bic)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not configured")

    return webhook


@router.delete("")
async def delete_webhook(
    bic: str,
    db: AsyncSession = Depends(get_db),
):
    await get_bank_or_404(bic, db)

    result = await db.execute(
        select(BankWebhook).where(BankWebhook.bank_bic == bic)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not configured")

    webhook.is_active = False
    await db.commit()

    return {"status": "deleted", "bank_bic": bic}
