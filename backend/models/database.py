"""
Database models and schema definitions
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class SocialMediaPost(Base):
    """Model for social media posts"""
    __tablename__ = "social_media_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(255), unique=True, nullable=False, index=True)
    source = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    author = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, index=True)
    ingested_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationship to sentiment analysis
    sentiment_analyses = relationship("SentimentAnalysis", back_populates="post", cascade="all, delete-orphan")


class SentimentAnalysis(Base):
    """Model for sentiment analysis results"""
    __tablename__ = "sentiment_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(255), ForeignKey("social_media_posts.post_id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String(100), nullable=False)
    sentiment_label = Column(String(20), nullable=False)  # positive, negative, neutral
    confidence_score = Column(Float, nullable=False)
    emotion = Column(String(50), nullable=True)
    analyzed_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    # Relationship to post
    post = relationship("SocialMediaPost", back_populates="sentiment_analyses")

    __table_args__ = (
        Index('idx_post_id_model', 'post_id', 'model_name'),
    )


class SentimentAlert(Base):
    """Model for sentiment alerts"""
    __tablename__ = "sentiment_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(50), nullable=False)
    threshold_value = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=False)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    post_count = Column(Integer, nullable=False)
    triggered_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    details = Column(JSON, nullable=True)

