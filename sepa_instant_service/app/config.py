from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://payments:payments_secret@localhost:5432/payments"
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/2")
    service_name: str = "sepa_instant"
    
    target_url: str = os.getenv("TARGET_URL", "https://localhost:8001")
    
    ca_cert_path: str = "/certs/ca.pem"
    service_cert_path: str = "/certs/sepa_instant.pem"
    service_key_path: str = "/certs/sepa_instant.key"
    
    host: str = "0.0.0.0"
    port: int = 8003
    
    class Config:
        env_file = ".env"


settings = Settings()