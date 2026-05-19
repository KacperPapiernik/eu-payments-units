from decimal import Decimal
from sqlalchemy import select

from target_service.app.models.bank import Bank, SettlementAccount


async def seed_system_bank(db):
    SYSTEM_BIC = "ECBCLS00XXX"

    result = await db.execute(
        select(Bank).where(Bank.bic == SYSTEM_BIC)
    )
    existing_bank = result.scalar_one_or_none()

    if existing_bank:
        print(f"System bank {SYSTEM_BIC} already exists.")
        return

    system_bank = Bank(
        bic=SYSTEM_BIC,
        name="ECB Clearing System Account",
        is_blocked=False,
    )

    db.add(system_bank)

    await db.flush()

    settlement_account = SettlementAccount(
        bank_id=system_bank.id,
        currency="EUR",
        balance=Decimal("1000000000.00"),
        available_balance=Decimal("1000000000.00"),
        limit_debt=Decimal("0.00"),
    )

    db.add(settlement_account)

    await db.commit()

    print(
        f"Created system settlement bank {SYSTEM_BIC} "
        f"with balance 1,000,000,000.00 EUR"
    )