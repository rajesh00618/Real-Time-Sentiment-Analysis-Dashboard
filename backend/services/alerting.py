"""
Alert service for sentiment monitoring
"""
import os
from typing import Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select, func, and_
from models.database import SentimentAnalysis, SentimentAlert, SocialMediaPost
import asyncio


class AlertService:
    """Service for monitoring sentiment and triggering alerts"""
    
    def __init__(self, db_session_maker: async_sessionmaker, redis_client=None):
        self.db_session_maker = db_session_maker
        self.redis_client = redis_client
        self.threshold = float(os.getenv("ALERT_NEGATIVE_RATIO_THRESHOLD", "2.0"))
        self.window_minutes = int(os.getenv("ALERT_WINDOW_MINUTES", "5"))
        self.min_posts = int(os.getenv("ALERT_MIN_POSTS", "10"))
    
    async def check_thresholds(self) -> Optional[Dict]:
        """
        Check if current sentiment metrics exceed alert thresholds
        """
        async with self.db_session_maker() as db:
            # Calculate time window
            now = datetime.utcnow()
            window_start = now - timedelta(minutes=self.window_minutes)
            
            # Count sentiments in window
            query = select(
                SentimentAnalysis.sentiment_label,
                func.count(SentimentAnalysis.id).label("count")
            ).join(
                SocialMediaPost,
                SentimentAnalysis.post_id == SocialMediaPost.post_id
            ).where(
                SentimentAnalysis.analyzed_at >= window_start
            ).group_by(
                SentimentAnalysis.sentiment_label
            )
            
            result = await db.execute(query)
            rows = result.all()
            
            positive_count = 0
            negative_count = 0
            neutral_count = 0
            
            for row in rows:
                label = row.sentiment_label
                count = row.count or 0
                if label == "positive":
                    positive_count = count
                elif label == "negative":
                    negative_count = count
                elif label == "neutral":
                    neutral_count = count
            
            total_count = positive_count + negative_count + neutral_count
            
            # Check if we have enough posts
            if total_count < self.min_posts:
                return None
            
            # Calculate ratio (avoid division by zero)
            if positive_count == 0:
                if negative_count > 0:
                    ratio = float('inf')  # Infinite ratio if no positive posts
                else:
                    ratio = 0.0
            else:
                ratio = negative_count / positive_count
            
            # Check if threshold exceeded
            if ratio > self.threshold:
                return {
                    "alert_triggered": True,
                    "alert_type": "high_negative_ratio",
                    "threshold": self.threshold,
                    "actual_ratio": ratio,
                    "window_minutes": self.window_minutes,
                    "metrics": {
                        "positive_count": positive_count,
                        "negative_count": negative_count,
                        "neutral_count": neutral_count,
                        "total_count": total_count
                    },
                    "timestamp": now.isoformat() + "Z"
                }
        
        return None
    
    async def save_alert(self, alert_data: Dict) -> int:
        """
        Save alert to database
        """
        async with self.db_session_maker() as db:
            alert = SentimentAlert(
                alert_type=alert_data["alert_type"],
                threshold_value=alert_data["threshold"],
                actual_value=alert_data["actual_ratio"],
                window_start=datetime.utcnow() - timedelta(minutes=alert_data["window_minutes"]),
                window_end=datetime.utcnow(),
                post_count=alert_data["metrics"]["total_count"],
                details=alert_data
            )
            db.add(alert)
            await db.commit()
            await db.refresh(alert)
            return alert.id
    
    async def run_monitoring_loop(self, check_interval_seconds: int = 60):
        """
        Continuously monitor and trigger alerts
        """
        while True:
            try:
                await asyncio.sleep(check_interval_seconds)
                alert_data = await self.check_thresholds()
                
                if alert_data:
                    alert_id = await self.save_alert(alert_data)
                    print(f"Alert triggered! Alert ID: {alert_id}, Ratio: {alert_data['actual_ratio']:.2f}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying

