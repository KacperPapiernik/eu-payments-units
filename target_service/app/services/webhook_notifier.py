import hmac
import hashlib
import base64
import json
from datetime import datetime
from decimal import Decimal
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from target_service.app.database import AsyncSessionLocal
from target_service.app.models.bank_webhook import BankWebhook


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def build_webhook_payload(
    event: str,
    transfer_id: str,
    sender_bic: str,
    receiver_bic: str,
    sender_iban: Optional[str],
    receiver_iban: Optional[str],
    amount: Decimal,
    currency: str,
    description: Optional[str],
    settled_at: datetime,
    secret: str,
) -> tuple[dict, str]:
    payload = {
        "event": event,
        "transfer_id": transfer_id,
        "sender_bic": sender_bic,
        "receiver_bic": receiver_bic,
        "sender_iban": sender_iban,
        "receiver_iban": receiver_iban,
        "amount": float(amount),
        "currency": currency,
        "description": description,
        "settled_at": settled_at.isoformat(),
    }

    payload_str = json.dumps(payload, sort_keys=True, cls=DecimalEncoder)

    signature = base64.b64encode(
        hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).digest()
    ).decode()

    payload["signature"] = signature
    return payload, signature


async def send_webhook(
    receiver_bic: str,
    event: str,
    transfer_id: str,
    sender_bic: str,
    amount: Decimal,
    currency: str,
    description: Optional[str],
    settled_at: datetime,
    sender_iban: Optional[str] = None,
    receiver_iban: Optional[str] = None,
):
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(BankWebhook).where(
                    BankWebhook.bank_bic == receiver_bic,
                    BankWebhook.is_active == True,
                )
            )
            webhook_config = result.scalar_one_or_none()

        if not webhook_config:
            return

        payload, _ = build_webhook_payload(
            event=event,
            transfer_id=transfer_id,
            sender_bic=sender_bic,
            receiver_bic=receiver_bic,
            sender_iban=sender_iban,
            receiver_iban=receiver_iban,
            amount=amount,
            currency=currency,
            description=description,
            settled_at=settled_at,
            secret=webhook_config.secret,
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                webhook_config.url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

        print(
            f"Webhook sent to {webhook_config.url} "
            f"for transfer {transfer_id} → {receiver_bic}: HTTP {response.status_code}"
        )

    except Exception as e:
        print(
            f"Webhook failed for transfer {transfer_id} → {receiver_bic}: {e}"
        )
