import os
import ssl

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from sepa_instant_service.app.config import settings
from sepa_instant_service.app.database import init_db
from sepa_instant_service.app.routers import transfers


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="SEPA Instant Service",
    description="SEPA Instant Real-time Payments & Gridlock Resolution",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transfers.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "sepa_instant"}


@app.get("/")
async def root():
    return {"service": "SEPA Instant", "version": "1.0.0"}


if __name__ == "__main__":
    cert_path = settings.service_cert_path
    key_path = settings.service_key_path
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            ssl_keyfile=key_path,
            ssl_certfile=cert_path
        )
    else:
        print(f"Warning: SSL certs not found. Using HTTP.")
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port
        )