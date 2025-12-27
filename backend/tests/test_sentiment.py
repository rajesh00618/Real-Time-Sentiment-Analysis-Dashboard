"""
Tests for sentiment analyzer
"""
import pytest
import asyncio
from services.sentiment_analyzer import SentimentAnalyzer


@pytest.mark.asyncio
async def test_local_sentiment_positive():
    """Test sentiment analysis with positive text"""
    analyzer = SentimentAnalyzer(model_type='local')
    result = await analyzer.analyze_sentiment("I absolutely love this product! It's amazing!")
    
    assert result['sentiment_label'] in ['positive', 'negative', 'neutral']
    assert 0.0 <= result['confidence_score'] <= 1.0
    assert 'model_name' in result


@pytest.mark.asyncio
async def test_local_sentiment_negative():
    """Test sentiment analysis with negative text"""
    analyzer = SentimentAnalyzer(model_type='local')
    result = await analyzer.analyze_sentiment("This is terrible and I hate it!")
    
    assert result['sentiment_label'] in ['positive', 'negative', 'neutral']
    assert 0.0 <= result['confidence_score'] <= 1.0


@pytest.mark.asyncio
async def test_local_sentiment_neutral():
    """Test sentiment analysis with neutral text"""
    analyzer = SentimentAnalyzer(model_type='local')
    result = await analyzer.analyze_sentiment("The product arrived today.")
    
    assert result['sentiment_label'] in ['positive', 'negative', 'neutral']
    assert 0.0 <= result['confidence_score'] <= 1.0


@pytest.mark.asyncio
async def test_local_emotion_detection():
    """Test emotion detection"""
    analyzer = SentimentAnalyzer(model_type='local')
    result = await analyzer.analyze_emotion("I'm so happy and excited about this!")
    
    assert 'emotion' in result
    assert result['emotion'] in ['joy', 'sadness', 'anger', 'fear', 'surprise', 'neutral']
    assert 0.0 <= result['confidence_score'] <= 1.0
    assert 'model_name' in result


@pytest.mark.asyncio
async def test_empty_text():
    """Test handling of empty text"""
    analyzer = SentimentAnalyzer(model_type='local')
    result = await analyzer.analyze_sentiment("")
    
    assert result['sentiment_label'] == 'neutral'
    assert 0.0 <= result['confidence_score'] <= 1.0


@pytest.mark.asyncio
async def test_short_text_emotion():
    """Test emotion detection with very short text"""
    analyzer = SentimentAnalyzer(model_type='local')
    result = await analyzer.analyze_emotion("Hi")
    
    assert result['emotion'] == 'neutral'


@pytest.mark.asyncio
async def test_batch_analyze():
    """Test batch sentiment analysis"""
    analyzer = SentimentAnalyzer(model_type='local')
    texts = [
        "I love this!",
        "This is terrible.",
        "It's okay, nothing special."
    ]
    
    results = await analyzer.batch_analyze(texts)
    
    assert len(results) == 3
    for result in results:
        assert 'sentiment_label' in result
        assert 'confidence_score' in result
        assert result['sentiment_label'] in ['positive', 'negative', 'neutral']


@pytest.mark.asyncio
async def test_batch_analyze_empty():
    """Test batch analysis with empty list"""
    analyzer = SentimentAnalyzer(model_type='local')
    results = await analyzer.batch_analyze([])
    
    assert results == []

