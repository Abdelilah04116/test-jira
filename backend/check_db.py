import asyncio
from app.core.database import get_engine
from sqlalchemy import inspect

async def check_tables():
    engine = get_engine()
    def get_tables(conn):
        inspector = inspect(conn)
        return inspector.get_table_names()
    
    async with engine.connect() as conn:
        tables = await conn.run_sync(get_tables)
        print(f"Tables found: {tables}")

if __name__ == "__main__":
    asyncio.run(check_tables())
