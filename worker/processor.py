"""
Database operations for worker
"""
from datetime import datetime
from typing import Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
import sys
import os

# Add parent directory to path to import models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.models.database import SocialMediaPost, SentimentAnalysis


async def save_post_and_analysis(
    db_session: AsyncSession,
    post_data: Dict,
    sentiment_result: Dict,
    emotion_result: Dict
) -> Tuple[int, int]:
    """
    Save post and analysis results to database
    
    Returns:
        tuple: (post_db_id, analysis_id) - database IDs of created records
    """
    try:
        # Parse created_at datetime and make it timezone-naive
        created_at = datetime.fromisoformat(post_data['created_at'].replace('Z', '+00:00'))
        created_at = created_at.replace(tzinfo=None)  # Make timezone-naive
        
        # Insert or update post (handle duplicates)
        post_insert = insert(SocialMediaPost).values(
            post_id=post_data['post_id'],
            source=post_data['source'],
            content=post_data['content'],
            author=post_data['author'],
            created_at=created_at,
            ingested_at=datetime.utcnow()
        )
        
        post_upsert = post_insert.on_conflict_do_update(
            index_elements=['post_id'],
            set_={
                'ingested_at': datetime.utcnow()
            }
        )
        
        await db_session.execute(post_upsert)
        await db_session.flush()
        
        # Get the post ID
        post_query = await db_session.execute(
            select(SocialMediaPost.id).where(SocialMediaPost.post_id == post_data['post_id'])
        )
        post_db_id = post_query.scalar()
        
        # Insert sentiment analysis
        analysis = SentimentAnalysis(
            post_id=post_data['post_id'],
            model_name=sentiment_result.get('model_name', 'unknown'),
            sentiment_label=sentiment_result.get('sentiment_label', 'neutral'),
            confidence_score=sentiment_result.get('confidence_score', 0.5),
            emotion=emotion_result.get('emotion')
        )
        
        db_session.add(analysis)
        await db_session.flush()
        analysis_id = analysis.id
        
        # Commit transaction
        await db_session.commit()
        
        return (post_db_id, analysis_id)
    
    except Exception as e:
        await db_session.rollback()
        raise e

