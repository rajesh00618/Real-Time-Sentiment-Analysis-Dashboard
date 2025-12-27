"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from models.db_session import init_db, close_db
from api.routes import router, redis_subscriber
from services.alerting import AlertService
from models.db_session import AsyncSessionLocal
import redis.asyncio as redis
import os

# Initialize Redis connection
redis_client = None
alert_service = None
redis_subscriber_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    print("Lifespan startup beginning...")
    global redis_client, alert_service
    
    # Startup
    print("Initializing database...")
    try:
        await init_db()
    except Exception as e:
        print(f"Database initialization failed: {e}")
        raise
    
    print("Connecting to Redis...")
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_client = await redis.Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True
    )
    await redis_client.ping()
    print("Redis connected")
    
    # Initialize alert service
    alert_service = AlertService(AsyncSessionLocal, redis_client)
    
    # Start alert monitoring in background
    alert_task = asyncio.create_task(alert_service.run_monitoring_loop())
    
    # Start Redis subscriber for new post notifications
    try:
        global redis_subscriber_task
        redis_subscriber_task = asyncio.create_task(redis_subscriber(redis_client))
    except Exception as e:
        print(f"Failed to start Redis subscriber: {e}")
        redis_subscriber_task = None
    
    print("Lifespan startup complete")
    yield
    
    # Shutdown
    if alert_task:
        alert_task.cancel()
    if redis_subscriber_task:
        redis_subscriber_task.cancel()
    try:
        if alert_task:
            await alert_task
    except asyncio.CancelledError:
        pass
    try:
        if redis_subscriber_task:
            await redis_subscriber_task
    except asyncio.CancelledError:
        pass
    
    await redis_client.close()
    await close_db()
    print("Application shutdown complete")


app = FastAPI(
    title="Sentiment Analysis API",
    description="Real-time sentiment analysis platform API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Sentiment Analysis API", "status": "running"}

