import uuid
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from frontend_service.app.template_engine import templates
from frontend_service.app.auth import require_auth
from frontend_service.app.clients import clients

router = APIRouter(prefix="/payments", tags=["payments"])


async def _check_sender_balance(bic: str, amount: float) -> str | None:
    try:
        r = await clients.target.get(f"/banks/{bic}")
        if r.status_code != 200:
            return "Nie znaleziono banku nadawcy"
        bank = r.json()
        acct = bank["settlement_accounts"][0]
        available = float(acct["available_balance"])
        limit = float(acct["limit_debt"])
        total = available + limit
        if total < amount:
            return f"Niewystarczające środki (dostępne: €{total:.2f}, wymagane: €{amount:.2f})"
        return None
    except Exception as e:
        return f"Błąd sprawdzania salda: {e}"


@router.get("/new", response_class=HTMLResponse)
async def new_payment(request: Request, user: dict = Depends(require_auth)):
    banks = []
    try:
        r = await clients.target.get("/banks")
        banks = r.json() if isinstance(r.json(), list) else []
    except Exception:
        banks = []
    return templates.TemplateResponse("payments/new.html", {
        "request": request, "user": user, "banks": banks
    })


@router.post("/target")
async def create_target_payment(request: Request, user: dict = Depends(require_auth)):
    form = await request.form()
    err = await _check_sender_balance(form.get("sender_bic"), float(form.get("amount", 0)))
    if err:
        return HTMLResponse(f'<div class="alert alert-danger">{err}</div>')
    payload = {
        "transaction_id": form.get("transaction_id", str(uuid.uuid4())[:16]),
        "sender_iban": form.get("sender_iban"),
        "receiver_iban": form.get("receiver_iban"),
        "sender_bic": form.get("sender_bic"),
        "receiver_bic": form.get("receiver_bic"),
        "amount": float(form.get("amount", 0)),
        "currency": "EUR",
        "description": form.get("description", ""),
        "service": "frontend",
    }
    try:
        r = await clients.target.post("/settle/payment", json=payload)
        result = r.json()
        if r.status_code == 200:
            msg = f'<div class="alert alert-success">Rozliczono! TxID: {result.get("transaction_id", "?")}</div>'
        else:
            msg = f'<div class="alert alert-danger">{result.get("detail", "Błąd")}</div>'
    except Exception as e:
        msg = f'<div class="alert alert-danger">Błąd połączenia: {str(e)}</div>'
    return HTMLResponse(msg)


@router.post("/batch")
async def create_batch_transfer(request: Request, user: dict = Depends(require_auth)):
    form = await request.form()
    err = await _check_sender_balance(form.get("sender_bic"), float(form.get("amount", 0)))
    if err:
        return HTMLResponse(f'<div class="alert alert-danger">{err}</div>')
    payload = {
        "transfer_id": str(uuid.uuid4()),
        "sender_iban": form.get("sender_iban"),
        "receiver_iban": form.get("receiver_iban"),
        "sender_bic": form.get("sender_bic"),
        "receiver_bic": form.get("receiver_bic"),
        "amount": float(form.get("amount", 0)),
        "currency": "EUR",
        "description": form.get("description", ""),
        "bank_bic": form.get("sender_bic"),
    }
    try:
        r = await clients.batch.post("/transfers", json=payload)
        result = r.json()
        if r.status_code == 200:
            msg = f'<div class="alert alert-success">Przyjęto do sesji {result.get("session_id", "?")}</div>'
        else:
            msg = f'<div class="alert alert-danger">{result.get("detail", "Błąd")}</div>'
    except Exception as e:
        msg = f'<div class="alert alert-danger">Błąd połączenia: {str(e)}</div>'
    return HTMLResponse(msg)


@router.post("/instant")
async def create_instant_transfer(request: Request, user: dict = Depends(require_auth)):
    form = await request.form()
    err = await _check_sender_balance(form.get("sender_bic"), float(form.get("amount", 0)))
    if err:
        return HTMLResponse(f'<div class="alert alert-danger">{err}</div>')
    payload = {
        "transfer_id": str(uuid.uuid4()),
        "sender_iban": form.get("sender_iban"),
        "receiver_iban": form.get("receiver_iban"),
        "sender_bic": form.get("sender_bic"),
        "receiver_bic": form.get("receiver_bic"),
        "amount": float(form.get("amount", 0)),
        "currency": "EUR",
        "description": form.get("description", ""),
        "bank_bic": form.get("sender_bic"),
    }
    try:
        r = await clients.instant.post("/transfers", json=payload)
        result = r.json()
        if r.status_code == 200:
            status = result.get("status", "?")
            badge = "success" if status == "settled" else "warning"
            msg = f'<div class="alert alert-{badge}">Status: {status} | ID: {result.get("transfer_id", "?")}</div>'
        else:
            msg = f'<div class="alert alert-danger">{result.get("detail", "Błąd")}</div>'
    except Exception as e:
        msg = f'<div class="alert alert-danger">Błąd połączenia: {str(e)}</div>'
    return HTMLResponse(msg)


@router.get("/history", response_class=HTMLResponse)
async def payment_history(
    request: Request,
    user: dict = Depends(require_auth),
    from_date: str = None,
    to_date: str = None,
):
    instant_transfers = []
    batch_sessions = []
    try:
        r = await clients.instant.get("/transfers")
        instant_transfers = r.json() if isinstance(r.json(), list) else []
    except Exception:
        pass
    try:
        r = await clients.batch.get("/sessions")
        batch_sessions = r.json() if isinstance(r.json(), list) else []
    except Exception:
        pass

    if from_date:
        instant_transfers = [t for t in instant_transfers if t.get("created_at", "")[:10] >= from_date]
        batch_sessions = [s for s in batch_sessions if s.get("opened_at", "")[:10] >= from_date]
    if to_date:
        instant_transfers = [t for t in instant_transfers if t.get("created_at", "")[:10] <= to_date]
        batch_sessions = [s for s in batch_sessions if s.get("opened_at", "")[:10] <= to_date]

    return templates.TemplateResponse("payments/history.html", {
        "request": request, "user": user,
        "instant_transfers": instant_transfers,
        "batch_sessions": batch_sessions,
        "from_date": from_date,
        "to_date": to_date,
    })
