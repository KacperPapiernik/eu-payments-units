from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from frontend_service.app.template_engine import templates
from frontend_service.app.auth import require_auth
from frontend_service.app.clients import clients

router = APIRouter(prefix="/emergency", tags=["emergency"])


@router.get("", response_class=HTMLResponse)
async def emergency_page(request: Request, user: dict = Depends(require_auth)):
    banks = []
    instant_transfers = []
    try:
        r = await clients.target.get("/banks")
        banks = r.json() if isinstance(r.json(), list) else []
    except Exception:
        banks = []
    try:
        r = await clients.instant.get("/transfers")
        data = r.json()
        instant_transfers = data if isinstance(data, list) else []
    except Exception:
        instant_transfers = []

    blocked_banks = [b for b in banks if b.get("is_blocked")]
    pending_transfers = [t for t in instant_transfers if t.get("status") in ("pending", "failed")]

    return templates.TemplateResponse("emergency.html", {
        "request": request, "user": user,
        "blocked_banks": blocked_banks,
        "pending_transfers": pending_transfers,
        "banks": banks,
    })
