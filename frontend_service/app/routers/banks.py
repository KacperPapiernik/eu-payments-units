from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from frontend_service.app.template_engine import templates
from frontend_service.app.auth import require_auth
from frontend_service.app.clients import clients

router = APIRouter(prefix="/banks", tags=["banks"])


@router.get("", response_class=HTMLResponse)
async def bank_list(request: Request, user: dict = Depends(require_auth)):
    banks = []
    try:
        r = await clients.target.get("/banks")
        banks = r.json() if isinstance(r.json(), list) else []
    except Exception:
        banks = []
    return templates.TemplateResponse("banks/list.html", {
        "request": request, "user": user, "banks": banks
    })


@router.get("/{bic}", response_class=HTMLResponse)
async def bank_detail(request: Request, bic: str, user: dict = Depends(require_auth)):
    bank = None
    try:
        r = await clients.target.get(f"/banks/{bic}")
        bank = r.json()
    except Exception:
        pass
    if not bank:
        return templates.TemplateResponse("banks/list.html", {
            "request": request, "user": user, "banks": [],
            "error": f"Bank {bic} nie znaleziony"
        })
    return templates.TemplateResponse("banks/detail.html", {
        "request": request, "user": user, "bank": bank
    })


@router.post("/{bic}/block")
async def block_bank(request: Request, bic: str, user: dict = Depends(require_auth)):
    try:
        r = await clients.target.post(f"/banks/block/{bic}")
        result = r.json()
    except Exception as e:
        return HTMLResponse(
            f'<div class="alert alert-danger">Błąd: {str(e)}</div>'
        )
    return HTMLResponse(
        f'<div class="alert alert-success">Bank {bic} został zablokowany</div>'
        f'<button hx-post="/banks/{bic}/unblock" hx-target="#bank-action-result" '
        f'class="btn btn-success btn-sm">Odblokuj</button>'
    )


@router.post("/{bic}/unblock")
async def unblock_bank(request: Request, bic: str, user: dict = Depends(require_auth)):
    try:
        r = await clients.target.post(f"/banks/unblock/{bic}")
        result = r.json()
    except Exception as e:
        return HTMLResponse(
            f'<div class="alert alert-danger">Błąd: {str(e)}</div>'
        )
    return HTMLResponse(
        f'<div class="alert alert-success">Bank {bic} został odblokowany</div>'
        f'<button hx-post="/banks/{bic}/block" hx-target="#bank-action-result" '
        f'class="btn btn-warning btn-sm">Zablokuj</button>'
    )
