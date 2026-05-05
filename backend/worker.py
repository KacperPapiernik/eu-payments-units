import asyncio
import sys
from datetime import datetime, timezone

sys.path.insert(0, '.')

from app.core.database import init_db, get_ready_transactions, update_transaction_status


async def process_transaction(tx):
    from app.models.transaction import TransactionStatus
    
    print(f"Processing transaction {tx.id} ({tx.payment_type})...")
    
    await update_transaction_status(
        tx_id=tx.id,
        status=TransactionStatus.PROCESSING.value,
        message=f"Processing {tx.payment_type} transfer"
    )
    
    await asyncio.sleep(1)
    
    await update_transaction_status(
        tx_id=tx.id,
        status=TransactionStatus.PROCESSED.value,
        message=f"{tx.payment_type} transfer processed successfully",
        processed_at=datetime.now(timezone.utc)
    )
    
    print(f"Transaction {tx.id} processed successfully")


async def run_worker():
    print("Initializing worker...")
    await init_db()
    print("Worker ready. Checking queue every 30 seconds...")
    
    while True:
        try:
            transactions = await get_ready_transactions()
            
            if transactions:
                print(f"Found {len(transactions)} transaction(s) to process")
                for tx in transactions:
                    await process_transaction(tx)
            else:
                print("No transactions to process")
                
        except Exception as e:
            print(f"Error processing transactions: {e}")
        
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(run_worker())