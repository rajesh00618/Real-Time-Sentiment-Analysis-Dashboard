"""
Tests for API endpoints
"""
import pytest
from main import app
from models.db_session import init_db, close_db, AsyncSessionLocal
import asyncio


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test health check endpoint"""
    response = await client.get("/api/health")
    assert response.status_code in [200, 503]  # 503 if services not available
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "services" in data
    assert "stats" in data


@pytest.mark.asyncio
async def test_posts_endpoint_basic(client):
    """Test posts endpoint basic retrieval"""
    response = await client.get("/api/posts?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "posts" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["posts"], list)


@pytest.mark.asyncio
async def test_posts_endpoint_pagination(client):
    """Test posts endpoint pagination"""
    response1 = await client.get("/api/posts?limit=5&offset=0")
    response2 = await client.get("/api/posts?limit=5&offset=5")
    
    assert response1.status_code == 200
    assert response2.status_code == 200
    
    data1 = response1.json()
    data2 = response2.json()
    
    assert len(data1["posts"]) <= 5
    assert len(data2["posts"]) <= 5
    assert data1["offset"] == 0
    assert data2["offset"] == 5


@pytest.mark.asyncio
async def test_sentiment_distribution_endpoint(client):
    """Test sentiment distribution endpoint"""
    response = await client.get("/api/sentiment/distribution?hours=24")
    assert response.status_code == 200
    data = response.json()
    assert "distribution" in data
    assert "total" in data
    assert "percentages" in data
    assert "timeframe_hours" in data
    assert data["timeframe_hours"] == 24


@pytest.mark.asyncio
async def test_sentiment_aggregate_endpoint(client):
    """Test sentiment aggregate endpoint"""
    response = await client.get("/api/sentiment/aggregate?period=hour")
    assert response.status_code == 200
    data = response.json()
    assert "period" in data
    assert "data" in data
    assert "summary" in data
    assert data["period"] == "hour"
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_sentiment_aggregate_invalid_period(client):
    """Test aggregate endpoint with invalid period"""
    response = await client.get("/api/sentiment/aggregate?period=invalid")
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test root endpoint"""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "status" in data

