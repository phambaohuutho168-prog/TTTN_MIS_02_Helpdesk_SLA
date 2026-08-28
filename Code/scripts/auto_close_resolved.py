import asyncio

from app.database.session import AsyncSessionLocal
from app.services.workflow_service import auto_close_expired_tickets


async def run() -> None:
    async with AsyncSessionLocal() as session:
        count = await auto_close_expired_tickets(session)
    print(f"Auto-close hoàn tất: {count} ticket được đóng.")


if __name__ == "__main__":
    asyncio.run(run())
