"""
Integration tests for end-to-end flow
"""
import pytest
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from models.db_session import AsyncSessionLocal
from models.database import SocialMediaPost, SentimentAnalysis


@pytest.mark.asyncio
async def test_end_to_end_flow():
    """
    Test complete flow from post creation to retrieval
    """
    # This is a simplified integration test
    # In a real scenario, you would test:
    # 1. Ingester publishes to Redis
    # 2. Worker consumes and processes
    # 3. Database contains the record
    # 4. API can retrieve it
    
    # For now, test database operations directly
    async with AsyncSessionLocal() as session:
        # Create a test post
        test_post = SocialMediaPost(
            post_id=f"test_post_{int(datetime.utcnow().timestamp())}",
            source="test",
            content="This is a test post with positive sentiment!",
            author="test_user",
            created_at=datetime.utcnow(),
            ingested_at=datetime.utcnow()
        )
        
        session.add(test_post)
        await session.flush()
        
        # Create sentiment analysis
        analysis = SentimentAnalysis(
            post_id=test_post.post_id,
            model_name="test_model",
            sentiment_label="positive",
            confidence_score=0.95,
            emotion="joy",
            analyzed_at=datetime.utcnow()
        )
        
        session.add(analysis)
        await session.commit()
        
        # Verify it was saved
        from sqlalchemy import select
        result = await session.execute(
            select(SocialMediaPost).where(SocialMediaPost.post_id == test_post.post_id)
        )
        saved_post = result.scalar_one()
        
        assert saved_post.post_id == test_post.post_id
        assert saved_post.source == "test"
        
        # Verify analysis was saved
        analysis_result = await session.execute(
            select(SentimentAnalysis).where(SentimentAnalysis.post_id == test_post.post_id)
        )
        saved_analysis = analysis_result.scalar_one()
        
        assert saved_analysis.sentiment_label == "positive"
        assert saved_analysis.confidence_score == 0.95
        
        # Cleanup
        await session.delete(saved_analysis)
        await session.delete(saved_post)
        await session.commit()

