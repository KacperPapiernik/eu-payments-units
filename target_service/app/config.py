from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://payments:payments_secret@localhost:5432/payments"
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    service_name: str = "target"
    
    ca_cert_path: str = "/certs/ca.pem"
    service_cert_path: str = "/certs/target.pem"
    service_key_path: str = "/certs/target.key"
    
    host: str = "0.0.0.0"
    port: int = 8001
    
    class Config:
        env_file = ".env"


settings = Settings()