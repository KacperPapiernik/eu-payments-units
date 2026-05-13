from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://payments:payments_secret@localhost:5432/payments"
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    service_name: str = "sepa_batch"
    
    target_url: str = os.getenv("TARGET_URL", "https://localhost:8001")
    
    ca_cert_path: str = "/certs/ca.pem"
    service_cert_path: str = "/certs/sepa_batch.pem"
    service_key_path: str = "/certs/sepa_batch.key"
    
    host: str = "0.0.0.0"
    port: int = 8002
    
    session_close_interval: int = int(os.getenv("SESSION_CLOSE_INTERVAL", "300"))
    
    class Config:
        env_file = ".env"


settings = Settings()