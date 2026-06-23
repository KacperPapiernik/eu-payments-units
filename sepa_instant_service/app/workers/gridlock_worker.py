from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime, timedelta
import httpx
import logging
from decimal import Decimal
from collections import defaultdict

from sepa_instant_service.app.config import settings
from sepa_instant_service.app.models.instant_transfer import (
    InstantTransfer,
    InstantTransferStatus
)
from sepa_instant_service.app.models.pending_transfer_queue import (
    PendingTransferQueue,
    LiquidityAlert
)
from sepa_instant_service.app.workers.celery import celery_app

logger = logging.getLogger(__name__)

MAX_RETRIES = 20


class _EngineSession:
    def __init__(self):
        self._engine = None

    async def __aenter__(self):
        self._engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            connect_args={"server_settings": {"search_path": settings.service_name}},
        )
        self._session = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )()
        return await self._session.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.__aexit__(exc_type, exc_val, exc_tb)
        if self._engine:
            await self._engine.dispose()


@celery_app.task(
    name="sepa_instant_service.app.workers.gridlock_worker.resolve_pending_transfers"
)
def resolve_pending_transfers():
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_resolve_pending_gridlock())
    finally:
        loop.close()


async def _fetch_balances(client, bics: set) -> dict[str, Decimal]:
    try:
        resp = await client.post(
            f"{settings.target_url}/banks/balances",
            json={"bics": list(bics)}
        )
        if resp.status_code == 200:
            data = resp.json()
            result = {}
            for bd in data["balances"]:
                av = Decimal(bd["available_balance"])
                lim = Decimal(bd["limit_debt"])
                result[bd["bic"]] = av + lim
            return result
    except Exception as e:
        logger.warning("Batch balance fetch failed: %s", e)

    result = {}
    for bic in bics:
        try:
            resp = await client.get(f"{settings.target_url}/banks/{bic}")
            if resp.status_code == 200:
                bank = resp.json()
                acct = bank["settlement_accounts"][0]
                av = Decimal(str(acct["available_balance"]))
                lim = Decimal(str(acct["limit_debt"]))
                result[bic] = av + lim
        except Exception as e:
            logger.warning("Individual balance fetch failed for %s: %s", bic, e)
            continue
    return result


async def _try_settle(client, transfer_id, sender_bic, receiver_bic, amount, service="sepa_instant_retry") -> bool:
    try:
        resp = await client.post(
            f"{settings.target_url}/settle/payment",
            json={
                "transaction_id": transfer_id,
                "sender_bic": sender_bic,
                "receiver_bic": receiver_bic,
                "amount": float(amount),
                "currency": "EUR",
                "service": service,
            }
        )
        if resp.status_code == 200:
            settled = resp.json().get("status") == "settled"
            if not settled:
                logger.warning("Settle returned non-settled status for %s: %s", transfer_id, resp.text)
            return settled
        else:
            logger.warning("Settle failed for %s (sender=%s, amount=%s): HTTP %d %s",
                           transfer_id, sender_bic, amount, resp.status_code, resp.text)
    except Exception as e:
        logger.error("Settle exception for %s (sender=%s, amount=%s): %s",
                     transfer_id, sender_bic, amount, e)
    return False


async def _mark_resolved(db, pending, resolved_ids, now):
    pending.resolved_at = now
    pending.status = "resolved"
    resolved_ids.add(pending.id)

    tr_result = await db.execute(
        select(InstantTransfer).where(
            InstantTransfer.transfer_id == pending.transfer_id
        )
    )
    tr = tr_result.scalar_one_or_none()
    if tr:
        tr.status = InstantTransferStatus.SETTLED
        tr.processed_at = now


async def _resolve_pending_gridlock():
    async with _EngineSession() as db:
        now = datetime.utcnow()

        result = await db.execute(
            select(PendingTransferQueue)
            .where(
                PendingTransferQueue.resolved_at == None,
                PendingTransferQueue.retry_count < MAX_RETRIES,
                PendingTransferQueue.next_retry_at <= now,
            )
            .order_by(PendingTransferQueue.created_at)
        )
        all_pending = result.scalars().all()

        if not all_pending:
            return {"status": "no_pending"}

        bics = set()
        for p in all_pending:
            bics.add(p.sender_bic)
            bics.add(p.receiver_bic)

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            effective = await _fetch_balances(client, bics)
            resolved_ids = set()
            pending_list = list(all_pending)

            while True:
                progress = False

                pending_list.sort(
                    key=lambda p: effective.get(p.sender_bic, Decimal(0)) - p.amount,
                    reverse=True
                )

                for p in pending_list:
                    if p.id in resolved_ids:
                        continue
                    sender_eff = effective.get(p.sender_bic, Decimal(0))
                    if sender_eff >= p.amount:
                        if await _try_settle(client, p.transfer_id, p.sender_bic, p.receiver_bic, p.amount):
                            effective[p.sender_bic] = sender_eff - p.amount
                            effective[p.receiver_bic] = effective.get(p.receiver_bic, Decimal(0)) + p.amount
                            await _mark_resolved(db, p, resolved_ids, now)
                            progress = True

                if progress:
                    continue

                remaining = [x for x in pending_list if x.id not in resolved_ids]
                for i, p1 in enumerate(remaining):
                    if p1.id in resolved_ids:
                        continue
                    for p2 in remaining[i + 1:]:
                        if p2.id in resolved_ids:
                            continue
                        if p1.sender_bic == p2.receiver_bic and p1.receiver_bic == p2.sender_bic:
                            if p1.amount >= p2.amount:
                                bigger, smaller = p1, p2
                            else:
                                bigger, smaller = p2, p1

                            net_amount = bigger.amount - smaller.amount

                            if net_amount > 0:
                                sender_eff = effective.get(bigger.sender_bic, Decimal(0))
                                if sender_eff >= net_amount:
                                    net_tx_id = f"NET-{bigger.transfer_id}-{smaller.transfer_id}"
                                    if await _try_settle(
                                        client, net_tx_id,
                                        bigger.sender_bic, bigger.receiver_bic,
                                        net_amount,
                                        "sepa_instant_gridlock_net"
                                    ):
                                        effective[bigger.sender_bic] -= net_amount
                                        effective[bigger.receiver_bic] += net_amount
                                        await _mark_resolved(db, bigger, resolved_ids, now)
                                        await _mark_resolved(db, smaller, resolved_ids, now)
                                        progress = True
                                        break
                    if progress:
                        break

                if progress:
                    continue

                remaining = [x for x in pending_list if x.id not in resolved_ids]
                if len(remaining) >= 2:
                    edges_by_sender = defaultdict(list)
                    for p in remaining:
                        edges_by_sender[p.sender_bic].append((p.receiver_bic, p))

                    def _find_cycle():
                        path = []
                        path_set = set()
                        visited = set()

                        def dfs(node):
                            if node in path_set:
                                idx = path.index(node)
                                return path[idx:]
                            if node in visited:
                                return None
                            visited.add(node)
                            path.append(node)
                            path_set.add(node)
                            for neighbor, _ in edges_by_sender.get(node, []):
                                result = dfs(neighbor)
                                if result:
                                    return result
                            path.pop()
                            path_set.discard(node)
                            return None

                        for node in list(edges_by_sender.keys()):
                            if node not in visited:
                                result = dfs(node)
                                if result and len(result) >= 2:
                                    return result
                        return None

                    cycle_nodes = _find_cycle()
                    if cycle_nodes:
                        cycle_edges = []
                        for i in range(len(cycle_nodes)):
                            sender = cycle_nodes[i]
                            receiver = cycle_nodes[(i + 1) % len(cycle_nodes)]
                            for neighbor, p_obj in edges_by_sender.get(sender, []):
                                if neighbor == receiver and p_obj.id not in resolved_ids:
                                    cycle_edges.append(p_obj)
                                    break

                        if len(cycle_edges) >= 2:
                            for start in range(len(cycle_edges)):
                                v_eff = dict(effective)
                                v_ok_ids = set()
                                ordered = cycle_edges[start:] + cycle_edges[:start]

                                sim_ok = True
                                for edge in ordered:
                                    if v_eff.get(edge.sender_bic, Decimal(0)) >= edge.amount:
                                        v_eff[edge.sender_bic] -= edge.amount
                                        v_eff[edge.receiver_bic] = v_eff.get(edge.receiver_bic, Decimal(0)) + edge.amount
                                        v_ok_ids.add(edge.id)
                                    else:
                                        sim_ok = False
                                        break

                                if sim_ok and len(v_ok_ids) == len(cycle_edges):
                                    for edge in ordered:
                                        if await _try_settle(
                                            client, edge.transfer_id,
                                            edge.sender_bic, edge.receiver_bic,
                                            edge.amount,
                                            "sepa_instant_gridlock_cycle"
                                        ):
                                            effective[edge.sender_bic] -= edge.amount
                                            effective[edge.receiver_bic] += edge.amount
                                            await _mark_resolved(db, edge, resolved_ids, now)
                                        else:
                                            break
                                    progress = True
                                    break

                if not progress:
                    break

            stuck = [x for x in pending_list if x.id not in resolved_ids]
            for p in stuck:
                p.retry_count += 1
                delay = min(p.retry_count * 2, 30)
                p.next_retry_at = now + timedelta(minutes=delay)

            await db.commit()

            logger.info(
                "Gridlock resolution: processed=%d settled=%d stuck=%d",
                len(pending_list), len(resolved_ids), len(stuck)
            )

            return {
                "processed": len(pending_list),
                "settled": len(resolved_ids),
                "stuck": len(stuck),
                "timestamp": now.isoformat()
            }


@celery_app.task(
    name="sepa_instant_service.app.workers.gridlock_worker.check_liquidity_alerts"
)
def check_liquidity_alerts():
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_check_alerts())
    finally:
        loop.close()


async def _check_alerts():
    async with _EngineSession() as db:
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
        blocked_banks = []

        async with httpx.AsyncClient(
            verify=False,
            timeout=15.0
        ) as client:
            for alert in alerts:
                if alert.created_at < two_hours_ago:
                    alert.resolved = "expired"
                    blocked_banks.append(alert.bank_bic)

                    try:
                        block_resp = await client.post(
                            f"{settings.target_url}/banks/block/{alert.bank_bic}"
                        )
                        block_ok = block_resp.status_code == 200
                    except Exception as e:
                        logger.warning("Block failed for %s: %s", alert.bank_bic, e)
                        block_ok = False

                    alert_msg = LiquidityAlert(
                        bank_bic=alert.bank_bic,
                        alert_type="bank_blocked_2h",
                        message=(
                            f"Bank {alert.bank_bic} "
                            f"blocked due to prolonged "
                            f"liquidity shortage"
                            f"{' (TARGET block OK)' if block_ok else ' (TARGET block FAILED)'}"
                        )
                    )
                    db.add(alert_msg)
                    expired_count += 1

        await db.commit()

        return {
            "expired_alerts": expired_count,
            "blocked_banks": blocked_banks,
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
