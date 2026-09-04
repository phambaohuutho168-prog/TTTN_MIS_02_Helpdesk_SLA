import asyncio

from app.database.session import AsyncSessionLocal
from app.services.escalation_service import process_sla_escalations


async def run() -> None:
    async with AsyncSessionLocal() as session:
        result = await process_sla_escalations(session)
    print(
        "SLA worker hoàn tất: "
        f"quét {result.scanned_runtimes} runtime, "
        f"tạo {result.created_events} event và "
        f"{result.created_notifications} notification."
    )


if __name__ == "__main__":
    asyncio.run(run())
