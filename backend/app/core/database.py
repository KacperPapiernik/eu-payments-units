from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import select, update
from datetime import datetime, timezone

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from app.models.transaction import Transaction
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def save_transaction(
    sender_iban: str,
    receiver_iban: str,
    amount: float,
    currency: str,
    payment_type: str,
    description: str | None = None,
    status: str = "RECEIVED",
    scheduled_for: datetime | None = None,
    message: str | None = None
):
    from app.models.transaction import Transaction
    async with AsyncSessionLocal() as session:
        tx = Transaction(
            sender_iban=sender_iban,
            receiver_iban=receiver_iban,
            amount=amount,
            currency=currency,
            payment_type=payment_type,
            description=description,
            status=status,
            scheduled_for=scheduled_for,
            message=message
        )
        session.add(tx)
        await session.commit()
        await session.refresh(tx)
        return tx


async def get_ready_transactions():
    from app.models.transaction import Transaction, TransactionStatus
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        stmt = select(Transaction).where(
            Transaction.status.in_([TransactionStatus.RECEIVED, TransactionStatus.SCHEDULED]),
            (Transaction.scheduled_for == None) | (Transaction.scheduled_for <= now)
        ).order_by(Transaction.created_at)
        result = await session.execute(stmt)
        return result.scalars().all()


async def update_transaction_status(
    tx_id: str,
    status: str,
    message: str = None,
    error_code: str = None,
    error_message: str = None,
    processed_at: datetime = None,
    settled_at: datetime = None
):
    from app.models.transaction import Transaction
    async with AsyncSessionLocal() as session:
        stmt = update(Transaction).where(Transaction.id == tx_id).values(
            status=status,
            message=message,
            error_code=error_code,
            error_message=error_message,
            processed_at=processed_at,
            settled_at=settled_at,
            updated_at=datetime.now(timezone.utc)
        )
        await session.execute(stmt)
        await session.commit()


async def get_transaction_by_id(tx_id: str):
    from app.models.transaction import Transaction
    async with AsyncSessionLocal() as session:
        stmt = select(Transaction).where(Transaction.id == tx_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()