"""
Pytest configuration and fixtures
"""
import pytest
import asyncio
import os
from httpx import AsyncClient
from main import app
from models.db_session import init_db, close_db


# Set test environment variables
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    """Setup test database"""
    await init_db()
    yield
    await close_db()


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac

