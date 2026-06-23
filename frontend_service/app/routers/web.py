from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from frontend_service.app.template_engine import templates
from frontend_service.app.auth import (
    USERS, AUTH_COOKIE, create_token,
    require_auth, optional_auth
)
from frontend_service.app.config import settings
from frontend_service.app.clients import clients

router = APIRouter(tags=["web"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: dict = Depends(optional_auth)):
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    user_data = USERS.get(username)
    if not user_data or user_data["password"] != password:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Nieprawidłowa nazwa użytkownika lub hasło"},
            status_code=401,
        )
    token = create_token(username, user_data["role"], user_data["name"], user_data.get("bank_bic"))
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=AUTH_COOKIE,
        value=token,
        httponly=True,
        max_age=settings.jwt_expire_minutes * 60,
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(AUTH_COOKIE)
    return response


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(require_auth)):
    target_health = None
    batch_health = None
    instant_health = None
    banks = []
    instant_transfers = []
    batch_sessions = []

    try:
        r = await clients.target.get("/health")
        target_health = r.json()
    except Exception:
        target_health = {"status": "unreachable", "service": "target"}

    try:
        r = await clients.batch.get("/health")
        batch_health = r.json()
    except Exception:
        batch_health = {"status": "unreachable", "service": "sepa_batch"}

    try:
        r = await clients.instant.get("/health")
        instant_health = r.json()
    except Exception:
        instant_health = {"status": "unreachable", "service": "sepa_instant"}

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

    try:
        r = await clients.batch.get("/sessions")
        data = r.json()
        batch_sessions = data if isinstance(data, list) else []
    except Exception:
        batch_sessions = []

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "target_health": target_health,
        "batch_health": batch_health,
        "instant_health": instant_health,
        "banks": banks,
        "instant_transfers": instant_transfers[:10],
        "batch_sessions": batch_sessions[:10],
    })
