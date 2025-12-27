# System Architecture Documentation

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│                         Port: 3000                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Dashboard   │  │   Charts     │  │  Live Feed   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│         │                  │                  │                 │
│         └──────────────────┼──────────────────┘                 │
│                            │                                    │
│                    HTTP/WebSocket                               │
└────────────────────────────┼────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│                    Backend API (FastAPI)                        │
│                         Port: 8000                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ REST Routes  │  │  WebSocket   │  │  Alerting    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│         │                  │                  │                 │
│         └──────────────────┼──────────────────┘                 │
│                            │                                    │
│              Database Connection    Redis Connection            │
└────────────────────────────┼────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐    ┌──────────────┐    ┌──────────────┐
│  PostgreSQL   │    │    Redis     │    │   Ingester   │
│   Database    │    │   Streams    │    │   Service    │
│               │    │              │    │              │
│ - Posts       │    │ - Streams    │    │ - Generate   │
│ - Analysis    │    │ - Consumer   │    │   Posts      │
│ - Alerts      │    │   Groups     │    │ - Publish    │
└───────────────┘    └──────────────┘    └──────────────┘
        ▲                    │
        │                    │
        │                    │
        │                    ▼
        │            ┌──────────────┐
        │            │    Worker    │
        │            │   Service    │
        │            │              │
        │            │ - Consume    │
        │            │ - Analyze    │
        │            │ - Store      │
        │            └──────────────┘
        │                    │
        └────────────────────┘
           Database Write
```

## Component Descriptions

### 1. PostgreSQL Database Service

**Purpose**: Persistent storage for all post data and analysis results.

**Data Model**:
- `social_media_posts`: Raw social media posts with metadata
- `sentiment_analysis`: Sentiment and emotion analysis results
- `sentiment_alerts`: Triggered alert records

**Key Features**:
- Automatic schema initialization on startup
- Foreign key relationships for data integrity
- Indexes on frequently queried columns for performance
- Supports time-based queries for aggregation

### 2. Redis Service

**Purpose**: Message queue using Redis Streams for decoupled communication between services.

**Key Features**:
- Redis Streams for reliable message delivery
- Consumer groups for distributed processing
- Message acknowledgment (XACK) for at-least-once delivery
- Persistence with AOF (Append-Only File)

### 3. Ingester Service

**Purpose**: Generates and publishes simulated social media posts to Redis Stream.

**Responsibilities**:
- Generate realistic posts with varied sentiment (40% positive, 30% neutral, 30% negative)
- Publish posts at configurable rate (posts per minute)
- Handle Redis connection failures gracefully
- Maintain consistent post format

**Key Implementation Details**:
- Uses XADD command to publish to Redis Stream
- Implements rate limiting to maintain target posts/minute
- Logs all publishing activity

### 4. Worker Service

**Purpose**: Consumes posts from Redis Stream, performs sentiment analysis, and stores results.

**Responsibilities**:
- Consume messages from Redis Stream using consumer groups
- Perform sentiment analysis using Hugging Face models
- Detect emotions in posts
- Save results to database
- Acknowledge messages after successful processing

**Key Implementation Details**:
- Uses XREADGROUP for coordinated message consumption
- Supports both local (Hugging Face) and external (LLM API) models
- Processes messages concurrently for throughput
- Only acknowledges messages after successful database save
- Implements error handling and retry logic

### 5. Backend API Service

**Purpose**: Provides REST API endpoints and WebSocket for real-time communication.

**REST Endpoints**:
- `GET /api/health`: System health check
- `GET /api/posts`: Retrieve posts with pagination and filtering
- `GET /api/sentiment/distribution`: Current sentiment distribution
- `GET /api/sentiment/aggregate`: Time-series aggregated data

**WebSocket Endpoint**:
- `ws://localhost:8000/ws/sentiment`: Real-time sentiment updates

**Key Features**:
- FastAPI for async performance
- Redis caching for frequently requested data
- WebSocket broadcasting to multiple clients
- Alert monitoring background task

### 6. Frontend Dashboard Service

**Purpose**: Web application for visualizing sentiment data in real-time.

**Components**:
- Dashboard: Main layout and state management
- DistributionChart: Pie chart showing sentiment distribution
- SentimentChart: Line chart showing sentiment trends over time
- LiveFeed: Real-time scrolling feed of posts
- MetricsCards: Summary statistics cards

**Key Features**:
- React 18 with hooks for state management
- Recharts for data visualization
- WebSocket client for real-time updates
- Responsive design with Tailwind CSS

## Data Flow

### Step-by-Step Data Flow: Ingestion → Processing → Storage → Serving

1. **Ingestion**: Ingester service generates simulated social media posts and publishes them to Redis Streams using XADD command
2. **Processing**: Worker service consumes messages from Redis Stream using XREADGROUP, performs sentiment analysis using Hugging Face models, and detects emotions
3. **Storage**: Worker saves the post data and analysis results to PostgreSQL database tables (social_media_posts, sentiment_analysis)
4. **Serving**: Backend API queries the database for aggregated data and serves it via REST endpoints to the Frontend, while also broadcasting real-time updates via WebSocket

## Technology Justification

### FastAPI (Backend Framework)
- **Why**: High-performance async framework, automatic OpenAPI documentation, type safety
- **Alternatives Considered**: Flask (slower), Express.js (different language), Spring Boot (heavier)

### PostgreSQL (Database)
- **Why**: ACID compliance, strong consistency, excellent performance for time-series queries
- **Alternatives Considered**: MySQL (similar but PostgreSQL better for JSON), MongoDB (we need relational data)

### Redis Streams (Message Queue)
- **Why**: Required for consumer groups, message persistence, at-least-once delivery guarantees
- **Alternatives Considered**: RabbitMQ (more complex), Kafka (overkill for this scale)

### Hugging Face Transformers (AI Models)
- **Why**: Easy-to-use library, pre-trained models, local execution (no API costs)
- **Alternatives Considered**: TensorFlow/PyTorch directly (more complex), cloud-only APIs (cost)

### React + Vite (Frontend)
- **Why**: Modern React with fast build times, excellent ecosystem, component reusability
- **Alternatives Considered**: Vue (similar), Angular (heavier), Svelte (smaller ecosystem)

### Docker Compose (Orchestration)
- **Why**: Simple multi-container orchestration, development and production consistency
- **Alternatives Considered**: Kubernetes (overkill), Docker Swarm (less features)

## Database Schema

### social_media_posts
- `id`: Primary key (auto-increment)
- `post_id`: Unique identifier (indexed)
- `source`: Platform name (indexed)
- `content`: Post text
- `author`: Username
- `created_at`: Post creation time (indexed)
- `ingested_at`: Ingestion timestamp

### sentiment_analysis
- `id`: Primary key (auto-increment)
- `post_id`: Foreign key to social_media_posts.post_id
- `model_name`: AI model used
- `sentiment_label`: positive/negative/neutral
- `confidence_score`: 0.0-1.0
- `emotion`: Detected emotion (nullable)
- `analyzed_at`: Analysis timestamp (indexed)

### sentiment_alerts
- `id`: Primary key (auto-increment)
- `alert_type`: Alert category
- `threshold_value`: Threshold that was exceeded
- `actual_value`: Actual value that triggered alert
- `window_start`: Time window start
- `window_end`: Time window end
- `post_count`: Number of posts in window
- `triggered_at`: Alert timestamp (indexed)
- `details`: JSON with additional context

## API Design

### REST API Patterns
- RESTful resource naming
- Query parameters for filtering and pagination
- Consistent JSON response format
- HTTP status codes for error handling

### WebSocket Protocol
- JSON message format
- Message type field for routing
- Timestamp on all messages
- Connection confirmation on connect

## Scalability Considerations

### Horizontal Scaling
- **Workers**: Multiple worker instances can consume from same consumer group
- **Backend API**: Stateless API can be scaled behind load balancer
- **Database**: Read replicas for read-heavy workloads
- **Redis**: Redis Cluster for high throughput

### Performance Optimizations
- Database indexes on frequently queried columns
- Redis caching for distribution endpoint
- Batch processing in worker
- Async operations throughout

### Resource Limits
- Current setup handles ~2 messages/second per worker
- Can scale workers horizontally for higher throughput
- Database connection pooling limits concurrent connections
- Redis memory limits message queue size

## Security Considerations

### Current Implementation
- No authentication/authorization (development/demo)
- Internal-only database and Redis (not exposed to host)
- Environment variables for sensitive configuration
- Input validation on API endpoints

### Production Recommendations
- Add authentication (JWT tokens)
- Rate limiting on API endpoints
- HTTPS for API and WebSocket
- Database connection encryption
- API key rotation for external LLMs
- CORS restrictions
- Input sanitization
- SQL injection protection (using ORM)

