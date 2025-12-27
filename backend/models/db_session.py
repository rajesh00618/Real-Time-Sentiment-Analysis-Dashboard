"""
Database session management
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import os
from .database import Base


def get_database_url() -> str:
    """Get database URL from environment"""
    database_url = os.getenv("DATABASE_URL", "")
    # Convert postgresql:// to postgresql+asyncpg:// for async
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


engine = create_async_engine(
    get_database_url(),
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database schema"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Verify connection
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        result.scalar()
    print("Database initialized successfully")


async def close_db():
    """Close database connections"""
    await engine.dispose()

