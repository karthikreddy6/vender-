from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import settings

# Create async database engine
# If using SQLite for testing or fallback, we check. But the spec says: PostgreSQL/asyncpg.
engine = create_async_engine(settings.DATABASE_URL, echo=settings.SQL_ECHO)

# Session factory for async sessions
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Declarative base class for models
Base = declarative_base()

# FastAPI DB Dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
