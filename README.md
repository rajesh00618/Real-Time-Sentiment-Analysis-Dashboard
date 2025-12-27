# Real-Time Sentiment Analysis Platform

A production-grade, real-time sentiment analysis platform that processes social media posts, analyzes sentiment and emotions using AI models, and provides live visualization through a web dashboard.

## Features

- **Real-time Data Ingestion**: Simulated social media posts published to Redis Streams at configurable rates
- **Dual Sentiment Analysis**: Supports both local Hugging Face models and external LLM APIs (Groq, OpenAI, Anthropic)
- **Emotion Detection**: Identifies emotions (joy, anger, sadness, fear, surprise, neutral) in posts
- **Live Dashboard**: React-based web dashboard with real-time updates via WebSocket
- **REST API**: Comprehensive API endpoints for data retrieval and analytics
- **Alert System**: Monitors sentiment trends and triggers alerts when thresholds are exceeded
- **Scalable Architecture**: Microservices architecture with 6 containerized services

## Architecture Overview

The system consists of 6 containerized services:

1. **PostgreSQL Database**: Stores posts and analysis results
2. **Redis**: Message queue using Redis Streams
3. **Ingester**: Publishes posts to Redis Stream
4. **Worker**: Consumes posts, performs sentiment analysis, stores results
5. **Backend API**: FastAPI service providing REST endpoints and WebSocket
6. **Frontend**: React dashboard with charts and live feed

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

## Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- 4GB RAM minimum
- Ports 3000 and 8000 available on your system
- API keys (optional but recommended):
  - Groq API key: https://console.groq.com/
  - OpenAI API key: https://platform.openai.com/api-keys
  - Anthropic API key: https://console.anthropic.com/

## Quick Start

```bash
# Clone repository
git clone <https://github.com/rajesh00618/setiment-platform>
cd sentiment-platform

# Copy environment template
cp .env.example .env

# Edit .env file with your API keys
nano .env

# Start all services
docker-compose up -d

# Wait for services to be healthy (30-60 seconds)
docker-compose ps

# Access dashboard
# Open http://localhost:3000 in browser

# Stop services
docker-compose down
```

## Configuration

All configuration is done through environment variables in the `.env` file. Key variables:

### Database Configuration
- `POSTGRES_USER`: Database user (default: sentiment_user)
- `POSTGRES_PASSWORD`: Database password (required)
- `POSTGRES_DB`: Database name (default: sentiment_db)

### Redis Configuration
- `REDIS_STREAM_NAME`: Name of Redis stream (default: social_posts_stream)
- `REDIS_CONSUMER_GROUP`: Consumer group name (default: sentiment_workers)

### AI Model Configuration
- `HUGGINGFACE_MODEL`: Local sentiment model (default: distilbert-base-uncased-finetuned-sst-2-english)
- `EMOTION_MODEL`: Local emotion model (default: j-hartmann/emotion-english-distilroberta-base)
- `EXTERNAL_LLM_PROVIDER`: External LLM provider (groq, openai, or anthropic)
- `EXTERNAL_LLM_API_KEY`: API key for external LLM
- `EXTERNAL_LLM_MODEL`: Model name for external LLM

### Ingester Configuration
- `POSTS_PER_MINUTE`: Rate of post generation (default: 60)

### Alert Configuration
- `ALERT_NEGATIVE_RATIO_THRESHOLD`: Alert when negative/positive ratio exceeds this (default: 2.0)
- `ALERT_WINDOW_MINUTES`: Time window for alert calculation (default: 5)
- `ALERT_MIN_POSTS`: Minimum posts required to trigger alert (default: 10)

See `.env.example` for all available configuration options.

## API Documentation

### REST Endpoints

#### Health Check
```
GET /api/health
```
Returns system health status and statistics.

#### Get Posts
```
GET /api/posts?limit=50&offset=0&source=reddit&sentiment=positive
```
Retrieve posts with pagination and filtering.

Query Parameters:
- `limit`: Max posts to return (1-100, default: 50)
- `offset`: Number of posts to skip (pagination)
- `source`: Filter by platform (reddit, twitter, etc.)
- `sentiment`: Filter by sentiment (positive, negative, neutral)
- `start_date`: Filter posts created after this datetime
- `end_date`: Filter posts created before this datetime

#### Sentiment Distribution
```
GET /api/sentiment/distribution?hours=24&source=reddit
```
Get current sentiment distribution for dashboard.

Query Parameters:
- `hours`: Look back period in hours (1-168, default: 24)
- `source`: Filter by platform

#### Sentiment Aggregate
```
GET /api/sentiment/aggregate?period=hour&start_date=2025-01-15T00:00:00Z&end_date=2025-01-15T23:59:59Z
```
Get sentiment counts aggregated by time period.

Query Parameters:
- `period`: Aggregation granularity (minute, hour, day) [REQUIRED]
- `start_date`: Start of time range
- `end_date`: End of time range
- `source`: Filter by platform

### WebSocket

Connect to `ws://localhost:8000/ws/sentiment` for real-time updates.

Message types:
- `connected`: Connection confirmation
- `new_post`: New post with sentiment analysis
- `metrics_update`: Periodic metrics update (every 30 seconds)

## Testing

Run tests with coverage:

```bash
docker-compose exec backend pytest --cov=backend --cov-report=term
```

Expected coverage: ≥70%

## Troubleshooting

### Services won't start
- Check Docker and Docker Compose versions
- Ensure ports 3000 and 8000 are available
- Check logs: `docker-compose logs`

### Database connection errors
- Verify PostgreSQL is healthy: `docker-compose ps postgres`
- Check database credentials in `.env`
- Ensure database has initialized (wait 30-60 seconds after first start)

### Redis connection errors
- Verify Redis is healthy: `docker-compose ps redis`
- Check Redis host and port in `.env`

### Frontend not loading
- Check backend API is running: `curl http://localhost:8000/api/health`
- Verify WebSocket connection in browser console
- Check frontend logs: `docker-compose logs frontend`

### No posts appearing
- Check ingester logs: `docker-compose logs ingester`
- Verify worker is processing: `docker-compose logs worker`
- Check Redis stream: `docker-compose exec redis redis-cli XINFO STREAM social_posts_stream`

### Sentiment analysis errors
- Verify Hugging Face models are downloading (first run may take time)
- Check external LLM API key if using external provider
- Check worker logs: `docker-compose logs worker`

## Project Structure

```
sentiment-platform/
├── docker-compose.yml          # Orchestrates all 6 services
├── .env.example               # Environment template
├── README.md                  # This file
├── ARCHITECTURE.md            # System design documentation
│
├── backend/                   # Backend API service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py               # FastAPI application
│   ├── api/
│   │   └── routes.py         # REST endpoints and WebSocket
│   ├── models/
│   │   ├── database.py       # SQLAlchemy models
│   │   └── db_session.py     # Database session management
│   ├── services/
│   │   ├── sentiment_analyzer.py  # Sentiment analysis service
│   │   ├── aggregator.py          # Data aggregation
│   │   ├── alerting.py            # Alert service
│   │   └── websocket_manager.py   # WebSocket connection manager
│   └── tests/                # Test files
│
├── worker/                    # Worker service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── worker.py             # Main worker loop
│   └── processor.py          # Message processing
│
├── ingester/                  # Ingester service
│   ├── Dockerfile
│   ├── requirements.txt
│   └── ingester.py           # Stream publisher
│
└── frontend/                  # Frontend dashboard
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── components/        # React components
        └── services/
            └── api.js         # API client
```

## License

This project is part of a capstone assignment. See LICENSE file for details.

