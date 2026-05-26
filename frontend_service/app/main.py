import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from frontend_service.app.config import settings
from frontend_service.app.clients import clients
from frontend_service.app.auth import get_current_user, AUTH_COOKIE, PUBLIC_PATHS
from frontend_service.app.routers import web, banks, payments, batch, liquidity


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await clients.close()


app = FastAPI(
    title="Settlement UI",
    description="Panel zarządzania systemem rozliczeniowym",
    version="1.0.0",
    lifespan=lifespan,
)

static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if any(path.startswith(p) for p in PUBLIC_PATHS):
        return await call_next(request)
    user = get_current_user(request)
    if user is None:
        if path.startswith("/api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return RedirectResponse(url="/login", status_code=303)
    return await call_next(request)


app.include_router(web.router)
app.include_router(banks.router)
app.include_router(payments.router)
app.include_router(batch.router)
app.include_router(liquidity.router)


if __name__ == "__main__":
    uvicorn.run(
        "frontend_service.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
