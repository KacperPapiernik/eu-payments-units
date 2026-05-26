from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from frontend_service.app.template_engine import templates
from frontend_service.app.auth import require_auth
from frontend_service.app.clients import clients

router = APIRouter(prefix="/batch", tags=["batch"])


@router.get("", response_class=HTMLResponse)
async def session_list(request: Request, user: dict = Depends(require_auth)):
    sessions = []
    try:
        r = await clients.batch.get("/sessions")
        sessions = r.json() if isinstance(r.json(), list) else []
    except Exception:
        sessions = []
    return templates.TemplateResponse("batch/sessions.html", {
        "request": request, "user": user, "sessions": sessions
    })


@router.get("/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, session_id: str, user: dict = Depends(require_auth)):
    session = None
    try:
        r = await clients.batch.get(f"/sessions/{session_id}")
        session = r.json()
    except Exception:
        pass
    if not session:
        return templates.TemplateResponse("batch/sessions.html", {
            "request": request, "user": user, "sessions": [],
            "error": f"Sesja {session_id} nie znaleziona"
        })
    return templates.TemplateResponse("batch/session_detail.html", {
        "request": request, "user": user, "session": session
    })


@router.post("/{session_id}/close")
async def close_session(request: Request, session_id: str, user: dict = Depends(require_auth)):
    try:
        r = await clients.batch.post(f"/sessions/close/{session_id}")
        result = r.json()
        if r.status_code == 200:
            msg = f'<div class="alert alert-success">Sesja zamknięta! Netting rozliczony.</div>'
        else:
            msg = f'<div class="alert alert-danger">{result.get("detail", "Błąd")}</div>'
    except Exception as e:
        msg = f'<div class="alert alert-danger">Błąd: {str(e)}</div>'
    return HTMLResponse(msg)


@router.get("/{session_id}/visualize")
async def visualize_netting(request: Request, session_id: str, user: dict = Depends(require_auth)):
    session = None
    try:
        r = await clients.batch.get(f"/sessions/{session_id}")
        session = r.json()
    except Exception:
        pass
    if not session:
        return HTMLResponse('<div class="alert alert-danger">Nie znaleziono sesji</div>')

    netting_results = session.get("netting_results", []) or []
    session_report = session.get("session_report") or {}
    labels = []
    values = []
    colors = []
    payers = []
    receivers = []
    for nr in netting_results:
        bic = nr.get("bank_bic", "?")
        pos = float(nr.get("net_position", 0))
        labels.append(bic)
        values.append(pos)
        colors.append("rgba(40, 167, 69, 0.8)" if pos >= 0 else "rgba(220, 53, 69, 0.8)")
        if pos < 0:
            payers.append({"bic": bic, "amount": round(-pos, 2)})
        elif pos > 0:
            receivers.append({"bic": bic, "amount": round(pos, 2)})

    return templates.TemplateResponse("batch/partials/netting_viz.html", {
        "request": request,
        "session": session,
        "netting_results": netting_results,
        "session_report": session_report,
        "chart_labels": labels,
        "chart_values": values,
        "chart_colors": colors,
        "payers": payers,
        "receivers": receivers,
    })
