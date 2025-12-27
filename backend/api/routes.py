"""
API routes for sentiment analysis platform
"""
from fastapi import APIRouter, Query, Depends, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func, select, and_, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from models.db_session import get_db, AsyncSessionLocal
from models.database import SocialMediaPost, SentimentAnalysis, SentimentAlert
from services.aggregator import AggregatorService
from services.websocket_manager import ConnectionManager
import redis.asyncio as redis
import os
import json
import asyncio

router = APIRouter()

# Redis client for caching
redis_cache = None


async def get_redis():
    """Get Redis client"""
    global redis_cache
    if redis_cache is None:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_cache = await redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
    return redis_cache


# WebSocket connection manager
connection_manager = ConnectionManager()


@router.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint
    """
    status = "healthy"
    services = {}
    
    # Check database
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        services["database"] = "connected"
    except Exception as e:
        services["database"] = "disconnected"
        status = "unhealthy"
    
    # Check Redis
    try:
        redis_client = await get_redis()
        await redis_client.ping()
        services["redis"] = "connected"
    except Exception as e:
        services["redis"] = "disconnected"
        status = "unhealthy"
    
    # Get stats
    stats = {}
    try:
        total_posts_result = await db.execute(
            select(func.count(SocialMediaPost.id))
        )
        stats["total_posts"] = total_posts_result.scalar() or 0
        
        total_analyses_result = await db.execute(
            select(func.count(SentimentAnalysis.id))
        )
        stats["total_analyses"] = total_analyses_result.scalar() or 0
        
        # Posts from last hour
        one_hour_ago = datetime.utcnow().replace(tzinfo=None) - timedelta(hours=1)
        recent_posts_result = await db.execute(
            select(func.count(SocialMediaPost.id))
            .where(SocialMediaPost.ingested_at >= one_hour_ago)
        )
        stats["recent_posts_1h"] = recent_posts_result.scalar() or 0
    except Exception:
        stats = {
            "total_posts": 0,
            "total_analyses": 0,
            "recent_posts_1h": 0
        }
    
    status_code = 200 if status == "healthy" else 503
    
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": services,
        "stats": stats
    }


@router.get("/api/posts")
async def get_posts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve posts with filtering and pagination
    """
    # Parse dates as timezone-naive UTC
    if start_date:
        start_date = datetime.fromisoformat(start_date.replace('Z', ''))
    if end_date:
        end_date = datetime.fromisoformat(end_date.replace('Z', ''))
    
    # Build query
    query = select(
        SocialMediaPost,
        SentimentAnalysis
    ).outerjoin(
        SentimentAnalysis,
        and_(
            SocialMediaPost.post_id == SentimentAnalysis.post_id,
            SentimentAnalysis.id == select(func.max(SentimentAnalysis.id))
            .where(SentimentAnalysis.post_id == SocialMediaPost.post_id)
            .correlate(SocialMediaPost)
            .scalar_subquery()
        )
    )
    
    # Apply filters
    conditions = []
    if source:
        conditions.append(SocialMediaPost.source == source)
    if start_date:
        conditions.append(SocialMediaPost.created_at >= start_date)
    if end_date:
        conditions.append(SocialMediaPost.created_at <= end_date)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Order by created_at DESC
    query = query.order_by(desc(SocialMediaPost.created_at))
    
    # Get total count
    count_query = select(func.count()).select_from(SocialMediaPost)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    query = query.offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    rows = result.all()
    
    # Format response
    posts = []
    for post, analysis in rows:
        post_data = {
            "post_id": post.post_id,
            "source": post.source,
            "content": post.content,
            "author": post.author,
            "created_at": post.created_at.isoformat() + "Z",
        }
        
        if analysis:
            # Apply sentiment filter if specified
            if sentiment and analysis.sentiment_label != sentiment:
                continue
            
            post_data["sentiment"] = {
                "label": analysis.sentiment_label,
                "confidence": analysis.confidence_score,
                "emotion": analysis.emotion,
                "model_name": analysis.model_name
            }
        elif sentiment:  # If sentiment filter specified but no analysis, skip
            continue
        else:
            post_data["sentiment"] = None
        
        posts.append(post_data)
    
    return {
        "posts": posts,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "source": source,
            "sentiment": sentiment,
            "start_date": start_date.isoformat() + "Z" if start_date else None,
            "end_date": end_date.isoformat() + "Z" if end_date else None
        }
    }


@router.get("/api/sentiment/aggregate")
async def get_sentiment_aggregate(
    period: str = Query(..., regex="^(minute|hour|day)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sentiment counts aggregated by time period
    """
    # Parse dates as timezone-naive UTC
    if start_date:
        start_date = datetime.fromisoformat(start_date.replace('Z', ''))
    if end_date:
        end_date = datetime.fromisoformat(end_date.replace('Z', ''))
    
    # Default time range: last 24 hours
    if not end_date:
        end_date = datetime.utcnow().replace(tzinfo=None)
    if not start_date:
        start_date = end_date - timedelta(hours=24)
    
    # Determine time truncation function based on period
    if period == "minute":
        trunc_func = func.date_trunc('minute', SentimentAnalysis.analyzed_at)
    elif period == "hour":
        trunc_func = func.date_trunc('hour', SentimentAnalysis.analyzed_at)
    else:  # day
        trunc_func = func.date_trunc('day', SentimentAnalysis.analyzed_at)
    
    # Build query
    query = select(
        trunc_func.label("timestamp"),
        SentimentAnalysis.sentiment_label,
        func.count(SentimentAnalysis.id).label("count"),
        func.avg(SentimentAnalysis.confidence_score).label("avg_confidence")
    ).join(
        SocialMediaPost,
        SentimentAnalysis.post_id == SocialMediaPost.post_id
    ).where(
        and_(
            SentimentAnalysis.analyzed_at >= start_date,
            SentimentAnalysis.analyzed_at <= end_date
        )
    ).group_by(
        trunc_func,
        SentimentAnalysis.sentiment_label
    ).order_by(
        trunc_func
    )
    
    if source:
        query = query.where(SocialMediaPost.source == source)
    
    # Execute query
    result = await db.execute(query)
    rows = result.all()
    
    # Organize data by timestamp
    data_by_time = {}
    for row in rows:
        timestamp_str = row.timestamp.isoformat() + "Z"
        if timestamp_str not in data_by_time:
            data_by_time[timestamp_str] = {
                "timestamp": timestamp_str,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "total_count": 0,
                "confidence_sum": 0.0,
                "confidence_count": 0
            }
        
        label = row.sentiment_label
        count = row.count or 0
        avg_conf = row.avg_confidence or 0.0
        
        if label == "positive":
            data_by_time[timestamp_str]["positive_count"] = count
        elif label == "negative":
            data_by_time[timestamp_str]["negative_count"] = count
        elif label == "neutral":
            data_by_time[timestamp_str]["neutral_count"] = count
        
        data_by_time[timestamp_str]["total_count"] += count
        data_by_time[timestamp_str]["confidence_sum"] += avg_conf * count
        data_by_time[timestamp_str]["confidence_count"] += count
    
    # Calculate percentages and format response
    data = []
    positive_total = 0
    negative_total = 0
    neutral_total = 0
    
    for timestamp_str, metrics in sorted(data_by_time.items()):
        total = metrics["total_count"]
        if total > 0:
            avg_confidence = metrics["confidence_sum"] / metrics["confidence_count"] if metrics["confidence_count"] > 0 else 0.0
        else:
            avg_confidence = 0.0
        
        positive_count = metrics["positive_count"]
        negative_count = metrics["negative_count"]
        neutral_count = metrics["neutral_count"]
        
        positive_total += positive_count
        negative_total += negative_count
        neutral_total += neutral_count
        
        data.append({
            "timestamp": timestamp_str,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "total_count": total,
            "positive_percentage": (positive_count / total * 100) if total > 0 else 0.0,
            "negative_percentage": (negative_count / total * 100) if total > 0 else 0.0,
            "neutral_percentage": (neutral_count / total * 100) if total > 0 else 0.0,
            "average_confidence": round(avg_confidence, 4)
        })
    
    return {
        "period": period,
        "start_date": start_date.isoformat() + "Z",
        "end_date": end_date.isoformat() + "Z",
        "data": data,
        "summary": {
            "total_posts": positive_total + negative_total + neutral_total,
            "positive_total": positive_total,
            "negative_total": negative_total,
            "neutral_total": neutral_total
        }
    }


@router.get("/api/sentiment/distribution")
async def get_sentiment_distribution(
    hours: int = Query(24, ge=1, le=168),
    source: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current sentiment distribution for dashboard
    """
    # Check cache
    redis_client = await get_redis()
    cache_key = f"sentiment_distribution:{hours}:{source or 'all'}"
    cached = await redis_client.get(cache_key)
    
    if cached:
        cached_data = json.loads(cached)
        cached_data["cached"] = True
        return cached_data
    
    # Calculate time threshold
    threshold = datetime.utcnow().replace(tzinfo=None) - timedelta(hours=hours)
    
    # Build query
    query = select(
        SentimentAnalysis.sentiment_label,
        func.count(SentimentAnalysis.id).label("count")
    ).join(
        SocialMediaPost,
        SentimentAnalysis.post_id == SocialMediaPost.post_id
    ).where(
        SentimentAnalysis.analyzed_at >= threshold
    ).group_by(
        SentimentAnalysis.sentiment_label
    )
    
    if source:
        query = query.where(SocialMediaPost.source == source)
    
    # Execute query
    result = await db.execute(query)
    rows = result.all()
    
    # Count sentiments
    distribution = {"positive": 0, "negative": 0, "neutral": 0}
    for row in rows:
        label = row.sentiment_label
        count = row.count or 0
        if label in distribution:
            distribution[label] = count
    
    total = sum(distribution.values())
    
    # Calculate percentages
    percentages = {
        "positive": (distribution["positive"] / total * 100) if total > 0 else 0.0,
        "negative": (distribution["negative"] / total * 100) if total > 0 else 0.0,
        "neutral": (distribution["neutral"] / total * 100) if total > 0 else 0.0
    }
    
    # Get top emotions
    emotion_query = select(
        SentimentAnalysis.emotion,
        func.count(SentimentAnalysis.id).label("count")
    ).join(
        SocialMediaPost,
        SentimentAnalysis.post_id == SocialMediaPost.post_id
    ).where(
        and_(
            SentimentAnalysis.analyzed_at >= threshold,
            SentimentAnalysis.emotion.isnot(None)
        )
    ).group_by(
        SentimentAnalysis.emotion
    ).order_by(
        desc(func.count(SentimentAnalysis.id))
    ).limit(5)
    
    if source:
        emotion_query = emotion_query.where(SocialMediaPost.source == source)
    
    emotion_result = await db.execute(emotion_query)
    emotion_rows = emotion_result.all()
    
    top_emotions = {}
    for row in emotion_rows:
        if row.emotion:
            top_emotions[row.emotion] = row.count or 0
    
    response = {
        "timeframe_hours": hours,
        "source": source,
        "distribution": distribution,
        "total": total,
        "percentages": percentages,
        "top_emotions": top_emotions,
        "cached": False,
        "cached_at": datetime.utcnow().isoformat() + "Z"
    }
    
    # Cache for 60 seconds
    await redis_client.setex(cache_key, 60, json.dumps(response, default=str))
    
    return response


async def redis_subscriber(redis_client):
    """Subscribe to Redis pub/sub for new post notifications"""
    print("Starting Redis subscriber...")
    while True:
        try:
            print("Creating Redis client...")
            # Use the passed redis_client instead of creating new one
            print("Redis client ready")
            pubsub = redis_client.pubsub()
            print("PubSub created")
            await pubsub.subscribe("new_post_notifications")
            print("Subscribed to new_post_notifications channel")
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    print(f"Received Redis message: {message['data'][:100]}...")
                    try:
                        post_data = json.loads(message['data'])
                        await connection_manager.broadcast({
                            "type": "new_post",
                            "data": {
                                "post_id": post_data.get("post_id"),
                                "content": (post_data.get("content", "")[:100] + "...") if len(post_data.get("content", "")) > 100 else post_data.get("content", ""),
                                "source": post_data.get("source"),
                                "sentiment_label": post_data.get("sentiment_label", "neutral"),
                                "confidence_score": post_data.get("confidence_score", 0.0),
                                "emotion": post_data.get("emotion"),
                                "timestamp": post_data.get("timestamp", datetime.utcnow().isoformat() + "Z")
                            }
                        })
                        print("Broadcasted new post to WebSocket clients")
                    except Exception as e:
                        print(f"Error processing Redis notification: {e}")
        except Exception as e:
            print(f"Redis subscriber error: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(5)  # Wait before retrying


@router.websocket("/ws/sentiment")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time sentiment updates
    """
    await connection_manager.connect(websocket)
    try:
        # Send connection confirmation
        await connection_manager.send_personal_message({
            "type": "connected",
            "message": "Connected to sentiment stream",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, websocket)
        
        # Keep connection alive and send periodic updates
        while True:
            await asyncio.sleep(30)  # Send metrics every 30 seconds
            
            # Calculate metrics
            async with AsyncSessionLocal() as db:
                try:
                    now = datetime.utcnow().replace(tzinfo=None)
                    
                    # Last minute
                    one_min_ago = now - timedelta(minutes=1)
                    one_min_result = await db.execute(
                        select(
                            SentimentAnalysis.sentiment_label,
                            func.count(SentimentAnalysis.id).label("count")
                        ).where(
                            SentimentAnalysis.analyzed_at >= one_min_ago
                        ).group_by(SentimentAnalysis.sentiment_label)
                    )
                    last_minute = {"positive": 0, "negative": 0, "neutral": 0, "total": 0}
                    for row in one_min_result.all():
                        label = row.sentiment_label
                        count = row.count or 0
                        last_minute[label] = count
                        last_minute["total"] += count
                    
                    # Last hour
                    one_hour_ago = now - timedelta(hours=1)
                    one_hour_result = await db.execute(
                        select(
                            SentimentAnalysis.sentiment_label,
                            func.count(SentimentAnalysis.id).label("count")
                        ).where(
                            SentimentAnalysis.analyzed_at >= one_hour_ago
                        ).group_by(SentimentAnalysis.sentiment_label)
                    )
                    last_hour = {"positive": 0, "negative": 0, "neutral": 0, "total": 0}
                    for row in one_hour_result.all():
                        label = row.sentiment_label
                        count = row.count or 0
                        last_hour[label] = count
                        last_hour["total"] += count
                    
                    # Last 24 hours
                    one_day_ago = now - timedelta(hours=24)
                    one_day_result = await db.execute(
                        select(
                            SentimentAnalysis.sentiment_label,
                            func.count(SentimentAnalysis.id).label("count")
                        ).where(
                            SentimentAnalysis.analyzed_at >= one_day_ago
                        ).group_by(SentimentAnalysis.sentiment_label)
                    )
                    last_24_hours = {"positive": 0, "negative": 0, "neutral": 0, "total": 0}
                    for row in one_day_result.all():
                        label = row.sentiment_label
                        count = row.count or 0
                        last_24_hours[label] = count
                        last_24_hours["total"] += count
                    
                    # Send metrics update
                    await connection_manager.broadcast({
                        "type": "metrics_update",
                        "data": {
                            "last_minute": last_minute,
                            "last_hour": last_hour,
                            "last_24_hours": last_24_hours
                        },
                        "timestamp": now.isoformat() + "Z"
                    })
                except Exception as e:
                    print(f"Error calculating metrics: {e}")
    
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)



