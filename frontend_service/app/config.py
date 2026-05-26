from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8004
    target_url: str = os.getenv("TARGET_URL", "http://localhost:8001")
    sepa_batch_url: str = os.getenv("SEPA_BATCH_URL", "http://localhost:8002")
    sepa_instant_url: str = os.getenv("SEPA_INSTANT_URL", "http://localhost:8003")
    jwt_secret: str = os.getenv("JWT_SECRET", "frontend-jwt-secret-change-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"

    class Config:
        env_file = ".env"


settings = Settings()
