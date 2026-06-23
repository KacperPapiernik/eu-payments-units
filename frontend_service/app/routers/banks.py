from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
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


@router.get("/create-form")
async def bank_create_form(request: Request, user: dict = Depends(require_auth)):
    return HTMLResponse('''
<form hx-post="/banks/create" hx-target="#create-result" hx-swap="innerHTML" class="row g-3 align-items-end border border-secondary rounded p-3 mb-3">
  <div class="col-md-4">
    <label class="small text-secondary mb-1">BIC (11 znak\u00f3w)</label>
    <input type="text" name="bic" maxlength="11" class="form-control form-control-sm" placeholder="Np. BANKPLPW" required>
  </div>
  <div class="col-md-6">
    <label class="small text-secondary mb-1">Nazwa banku</label>
    <input type="text" name="name" class="form-control form-control-sm" placeholder="Np. Bank Polski A" required>
  </div>
  <div class="col-md-2">
    <label class="small text-secondary mb-1">&nbsp;</label>
    <button type="submit" class="btn btn-sm btn-success w-100">
      <i class="bi bi-plus-circle me-1"></i>Utw\u00f3rz
    </button>
  </div>
</form>
<div id="create-result"></div>
    ''')


@router.post("/create")
async def bank_create(request: Request, user: dict = Depends(require_auth)):
    form = await request.form()
    bic = form.get("bic", "").strip().upper()
    name = form.get("name", "").strip()

    if not bic or len(bic) > 11:
        return HTMLResponse('<div class="alert alert-danger">BIC wymagany, max 11 znak\u00f3w</div>')
    if not name:
        return HTMLResponse('<div class="alert alert-danger">Nazwa banku jest wymagana</div>')

    try:
        r = await clients.target.post("/banks", json={"bic": bic, "name": name})
        if r.status_code in (200, 201):
            return HTMLResponse(
                f'<div class="alert alert-success">Bank <strong>{bic}</strong> utworzony!</div>'
                f'<script>setTimeout(() => htmx.trigger("#bank-table", "refresh"), 500)</script>'
            )
        detail = r.json().get("detail", "Nieznany b\u0142\u0105d")
    except Exception as e:
        detail = str(e)

    return HTMLResponse(f'<div class="alert alert-danger">B\u0142\u0105d: {detail}</div>')


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
            f'<div class="alert alert-danger">B\u0142\u0105d: {str(e)}</div>'
        )
    return HTMLResponse(
        f'<div class="alert alert-success">Bank {bic} zosta\u0142 zablokowany</div>'
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
            f'<div class="alert alert-danger">B\u0142\u0105d: {str(e)}</div>'
        )
    return HTMLResponse(
        f'<div class="alert alert-success">Bank {bic} zosta\u0142 odblokowany</div>'
        f'<button hx-post="/banks/{bic}/block" hx-target="#bank-action-result" '
        f'class="btn btn-warning btn-sm">Zablokuj</button>'
    )


@router.get("/{bic}/limit-form")
async def limit_debt_form(request: Request, bic: str, user: dict = Depends(require_auth)):
    return HTMLResponse(f'''
<form hx-post="/banks/{bic}/limit-debt" hx-target="#limit-result" class="row g-2 align-items-end">
  <div class="col-auto">
    <label class="small text-secondary">{bic} — nowy limit debetu (EUR):</label>
    <input type="number" name="limit_debt" step="0.01" min="0" class="form-control form-control-sm" style="width:140px" required>
  </div>
  <div class="col-auto">
    <label class="small text-secondary">&nbsp;</label>
    <button type="submit" class="btn btn-sm btn-primary form-control-sm">
      <i class="bi bi-check-lg me-1"></i>Zapisz
    </button>
  </div>
</form>
<div id="limit-result" class="mt-2"></div>
    ''')


@router.post("/{bic}/limit-debt")
async def update_limit_debt(request: Request, bic: str, user: dict = Depends(require_auth)):
    form = await request.form()
    payload = {
        "limit_debt": float(form.get("limit_debt", 0)),
    }
    try:
        r = await clients.target.post(f"/banks/{bic}/limit-debt", json=payload)
        result = r.json()
        if r.status_code == 200:
            return HTMLResponse(
                f'<div class="alert alert-success">Limit debetu dla {bic} zmieniony na \u20ac{float(result["limit_debt"]):.2f}</div>'
                f'<button class="btn btn-sm btn-outline-light" hx-get="/banks" hx-target="body">Od\u015bwie\u017c</button>'
            )
        else:
            msg = result.get("detail", "B\u0142\u0105d")
    except Exception as e:
        msg = str(e)
    return HTMLResponse(f'<div class="alert alert-danger">B\u0142\u0105d: {msg}</div>')
