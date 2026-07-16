from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, text
from typing import AsyncGenerator
from app.core.config import settings

# create async engine
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# create async session maker
async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Columns to ensure exist: (table_name, column_name, column_definition)
_MIGRATIONS = [
    ("chatmessage", "feedback_rating",  "TEXT DEFAULT NULL"),
    ("chatmessage", "feedback_comment", "TEXT DEFAULT NULL"),
    ("server", "tags", "TEXT DEFAULT ''"),
]

async def _run_schema_migrations(conn) -> None:
    """Add new columns to existing tables without breaking existing data."""
    for table, column, definition in _MIGRATIONS:
        # PRAGMA table_info returns rows: (cid, name, type, notnull, dflt_value, pk)
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing_columns = {row[1] for row in result.fetchall()}
        if column not in existing_columns:
            await conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            ))

# create async db and tables
async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await _run_schema_migrations(conn)

# create async session dependency
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

