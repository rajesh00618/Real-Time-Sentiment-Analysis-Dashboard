"""
Data aggregation service
"""
from typing import Dict, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from models.database import SentimentAnalysis, SocialMediaPost


class AggregatorService:
    """Service for aggregating sentiment data"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def get_sentiment_distribution(
        self,
        hours: int = 24,
        source: str = None
    ) -> Dict:
        """
        Get sentiment distribution for a time period
        """
        threshold = datetime.utcnow() - timedelta(hours=hours)
        
        query = select(
            SentimentAnalysis.sentiment_label,
            func.count(SentimentAnalysis.id).label("count")
        ).where(
            SentimentAnalysis.analyzed_at >= threshold
        ).group_by(
            SentimentAnalysis.sentiment_label
        )
        
        result = await self.db.execute(query)
        rows = result.all()
        
        distribution = {"positive": 0, "negative": 0, "neutral": 0}
        for row in rows:
            label = row.sentiment_label
            count = row.count or 0
            if label in distribution:
                distribution[label] = count
        
        return distribution
    
    async def get_time_series(
        self,
        period: str,
        start_date: datetime,
        end_date: datetime,
        source: str = None
    ) -> List[Dict]:
        """
        Get time series aggregated sentiment data
        """
        # Determine truncation function
        if period == "minute":
            trunc_func = func.date_trunc('minute', SentimentAnalysis.analyzed_at)
        elif period == "hour":
            trunc_func = func.date_trunc('hour', SentimentAnalysis.analyzed_at)
        else:  # day
            trunc_func = func.date_trunc('day', SentimentAnalysis.analyzed_at)
        
        query = select(
            trunc_func.label("timestamp"),
            SentimentAnalysis.sentiment_label,
            func.count(SentimentAnalysis.id).label("count")
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
        
        result = await self.db.execute(query)
        rows = result.all()
        
        # Organize by timestamp
        data_by_time = {}
        for row in rows:
            timestamp_str = row.timestamp.isoformat() + "Z"
            if timestamp_str not in data_by_time:
                data_by_time[timestamp_str] = {
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0
                }
            label = row.sentiment_label
            count = row.count or 0
            if label in data_by_time[timestamp_str]:
                data_by_time[timestamp_str][label] = count
        
        # Format as list
        return [
            {
                "timestamp": ts,
                **counts
            }
            for ts, counts in sorted(data_by_time.items())
        ]

