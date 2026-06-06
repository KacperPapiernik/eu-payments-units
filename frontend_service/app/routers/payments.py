import uuid
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from frontend_service.app.template_engine import templates
from frontend_service.app.auth import require_auth
from frontend_service.app.clients import clients

router = APIRouter(prefix="/payments", tags=["payments"])


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
    payload = {
        "transaction_id": form.get("transaction_id", str(uuid.uuid4())[:8]),
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
async def payment_history(request: Request, user: dict = Depends(require_auth)):
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
    return templates.TemplateResponse("payments/history.html", {
        "request": request, "user": user,
        "instant_transfers": instant_transfers,
        "batch_sessions": batch_sessions,
    })
