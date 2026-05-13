import os
import ssl

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional

from target_service.app.config import settings
from target_service.app.database import init_db
from target_service.app.routers import banks, settlement, liquidity


def create_ssl_context() -> Optional[ssl.SSLContext]:
    cert_path = settings.service_cert_path
    key_path = settings.service_key_path
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            print(f"SSL enabled: using {cert_path}")
            return context
        except Exception as e:
            print(f"Warning: Failed to load SSL certs: {e}. Using HTTP.")
            return None
    else:
        print(f"Warning: SSL certs not found at {cert_path} or {key_path}. Using HTTP.")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="TARGET Service",
    description="Central Bank RTGS Settlement System",
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

app.include_router(banks.router)
app.include_router(settlement.router)
app.include_router(liquidity.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "target"}


@app.get("/")
async def root():
    return {"service": "TARGET", "version": "1.0.0"}


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