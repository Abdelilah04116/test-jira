import asyncio
from app.core.database import get_engine
from sqlalchemy import select, func
from app.models.database import AuditLog

async def count_logs():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(select(func.count(AuditLog.id)))
        count = result.scalar()
        print(f"Audit log entries: {count}")

if __name__ == "__main__":
    asyncio.run(count_logs())
