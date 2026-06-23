from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request, HTTPException
from shared.security.jwt_handler import JWTHandler
from frontend_service.app.config import settings

USERS = {
    "admin": {"password": "admin123", "role": "admin", "name": "Administrator", "bank_bic": None},
    "operator": {"password": "operator123", "role": "operator", "name": "Operator Rozliczeniowy", "bank_bic": None},
}

jwt_handler = JWTHandler(secret_key=settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_token(username: str, role: str, name: str, bank_bic: str = None) -> str:
    return jwt_handler.create_token(
        {"sub": username, "role": role, "name": name, "bank_bic": bank_bic},
        expires_delta=timedelta(minutes=settings.jwt_expire_minutes),
    )


def verify_token(token: str) -> Optional[dict]:
    return jwt_handler.verify_token(token)


AUTH_COOKIE = "access_token"
PUBLIC_PATHS = {"/login", "/static"}


def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(AUTH_COOKIE)
    if not token:
        return None
    payload = verify_token(token)
    if payload is None:
        return None
    return {
        "username": payload.get("sub"),
        "role": payload.get("role"),
        "name": payload.get("name"),
        "bank_bic": payload.get("bank_bic"),
    }


async def require_auth(request: Request):
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=303, detail="Unauthorized", headers={"Location": "/login"})
    return user


async def optional_auth(request: Request) -> Optional[dict]:
    return get_current_user(request)
