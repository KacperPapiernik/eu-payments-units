from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from frontend_service.app.template_engine import templates
from frontend_service.app.auth import require_auth
from frontend_service.app.clients import clients

router = APIRouter(prefix="/liquidity", tags=["liquidity"])


@router.get("/inject", response_class=HTMLResponse)
async def inject_page(request: Request, user: dict = Depends(require_auth)):
    banks = []
    try:
        r = await clients.target.get("/banks")
        banks = r.json() if isinstance(r.json(), list) else []
    except Exception:
        banks = []
    return templates.TemplateResponse("liquidity/inject.html", {
        "request": request, "user": user, "banks": banks
    })


@router.post("/inject")
async def inject_liquidity(request: Request, user: dict = Depends(require_auth)):
    form = await request.form()
    payload = {
        "bank_bic": form.get("bank_bic"),
        "amount": float(form.get("amount", 0)),
        "currency": "EUR",
    }
    try:
        r = await clients.target.post("/liquidity/injection", json=payload)
        result = r.json()
        if r.status_code == 200:
            bal = result.get("new_balance", result.get("balance", "?"))
            msg = f'<div class="alert alert-success">Wstrzyknięto! Nowe saldo: €{bal}</div>'
        else:
            msg = f'<div class="alert alert-danger">{result.get("detail", "Błąd")}</div>'
    except Exception as e:
        msg = f'<div class="alert alert-danger">Błąd połączenia: {str(e)}</div>'
    return HTMLResponse(msg)


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request, user: dict = Depends(require_auth)):
    alerts_list = []
    try:
        r = await clients.instant.get("/transfers")
        transfers = r.json() if isinstance(r.json(), list) else []
    except Exception:
        transfers = []
    return templates.TemplateResponse("liquidity/alerts.html", {
        "request": request, "user": user, "transfers": transfers
    })
