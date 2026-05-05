from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://payments_user:payments_pass@db:5432/payments_db"
    DATABASE_URL_SYNC: str = "postgresql://payments_user:payments_pass@db:5432/payments_db"

    MAX_SEPA_INSTANT_AMOUNT: float = 100000.0
    API_VERSION: str = "1.0.0"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()