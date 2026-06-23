from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import declarative_base

from target_service.app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"server_settings": {"search_path": settings.service_name}},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.service_name}"))
        await conn.execute(text(f"SET search_path TO {settings.service_name}"))
    
    from target_service.app.models.bank import Bank, SettlementAccount
    from target_service.app.models.settlement_transaction import SettlementTransaction
    from target_service.app.models.liquidity_transfer import LiquidityTransfer
    from target_service.app.models.rtgs_transfer import RtgsTransfer
    from target_service.app.models.bank_webhook import BankWebhook
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session