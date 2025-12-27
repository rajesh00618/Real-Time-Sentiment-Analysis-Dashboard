"""
Worker service - consumes posts from Redis Stream and processes sentiment analysis
"""
print("Worker module loading...")
import asyncio
import os
import sys
from typing import Dict, Optional
import redis.asyncio as redis
from dotenv import load_dotenv
from datetime import datetime

# Add parent directory to path to import backend services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.models.db_session import AsyncSessionLocal
from backend.services.sentiment_analyzer import SentimentAnalyzer
from worker.processor import save_post_and_analysis

load_dotenv()


class SentimentWorker:
    """
    Consumes posts from Redis Stream and processes them through sentiment analysis
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        db_session_maker,
        stream_name: str,
        consumer_group: str,
        consumer_name: str = "worker-1"
    ):
        """
        Initialize worker with necessary dependencies
        """
        self.redis_client = redis_client
        self.db_session_maker = db_session_maker
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        
        # Initialize sentiment analyzers
        # Try local first, but don't fail if it can't download models
        print("About to initialize analyzers...")
        try:
            self.local_analyzer = SentimentAnalyzer(model_type='local')
            print("Initialized local sentiment analyzer")
        except Exception as e:
            print(f"Failed to initialize local analyzer: {e}")
            self.local_analyzer = None
        
        # Initialize external analyzer if API key is provided
        external_api_key = os.getenv("EXTERNAL_LLM_API_KEY", "")
        if external_api_key:
            try:
                self.external_analyzer = SentimentAnalyzer(model_type='external')
                print("Initialized external sentiment analyzer")
            except Exception as e:
                print(f"Failed to initialize external analyzer: {e}")
                self.external_analyzer = None
        else:
            self.external_analyzer = None
            print("No external LLM API key provided, using local analyzer only")
        
        self.stats = {
            "processed": 0,
            "errors": 0,
            "start_time": None
        }
    
    async def ensure_consumer_group(self):
        """Create consumer group if it doesn't exist"""
        try:
            await self.redis_client.xgroup_create(
                name=self.stream_name,
                groupname=self.consumer_group,
                id="0",
                mkstream=True
            )
            print(f"Created consumer group: {self.consumer_group}")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"Consumer group {self.consumer_group} already exists")
            else:
                raise
    
    async def process_message(self, message_id: str, message_data: Dict) -> bool:
        """
        Process a single message from the stream
        
        Returns:
            bool: True if processed successfully, False otherwise
        """
        try:
            print(f"Processing message {message_id}")
            # Extract post data
            post_data = {
                'post_id': message_data.get('post_id'),
                'source': message_data.get('source'),
                'content': message_data.get('content'),
                'author': message_data.get('author'),
                'created_at': message_data.get('created_at')
            }
            
            # Validate message data
            if not all(post_data.values()):
                print(f"Invalid message data: {message_data}")
                # Acknowledge invalid message to avoid infinite retries
                await self.redis_client.xack(
                    self.stream_name,
                    self.consumer_group,
                    message_id
                )
                return False
            
            print(f"Analyzing sentiment for post {post_data['post_id']}")
            # Run sentiment analysis (try local first, fallback to external)
            sentiment_result = None
            emotion_result = None
            
            if self.local_analyzer:
                try:
                    sentiment_result = await self.local_analyzer.analyze_sentiment(post_data['content'])
                    emotion_result = await self.local_analyzer.analyze_emotion(post_data['content'])
                except Exception as e:
                    print(f"Error in local analyzer: {e}")
                    # Fall through to try external analyzer
            
            # If local failed or not available, try external
            if not sentiment_result and self.external_analyzer:
                try:
                    sentiment_result = await self.external_analyzer.analyze_sentiment(post_data['content'])
                    emotion_result = await self.external_analyzer.analyze_emotion(post_data['content'])
                except Exception as e2:
                    print(f"Error in external analyzer: {e2}")
                    return False
            
            if not sentiment_result:
                print("No analyzer available to process sentiment")
                return False
            
            print(f"Saving to database: sentiment={sentiment_result.get('sentiment_label')}")
            # Save to database
            async with self.db_session_maker() as db_session:
                try:
                    post_db_id, analysis_id = await save_post_and_analysis(
                        db_session,
                        post_data,
                        sentiment_result,
                        emotion_result
                    )
                except Exception as e:
                    print(f"Error saving to database: {e}")
                    # Don't acknowledge message if database save failed
                    return False
            
            print(f"Publishing notification for post {post_data['post_id']}")
            # Publish notification to Redis pub/sub for WebSocket broadcasting
            try:
                import json
                notification_data = {
                    "post_id": post_data['post_id'],
                    "content": post_data['content'],
                    "source": post_data['source'],
                    "sentiment_label": sentiment_result.get('sentiment_label', 'neutral'),
                    "confidence_score": sentiment_result.get('confidence_score', 0.0),
                    "emotion": emotion_result.get('emotion'),
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                await self.redis_client.publish(
                    "new_post_notifications",
                    json.dumps(notification_data)
                )
            except Exception as e:
                print(f"Error publishing notification: {e}")
                # Don't fail processing if notification fails
            
            # Acknowledge message in Redis (only after successful processing)
            await self.redis_client.xack(
                self.stream_name,
                self.consumer_group,
                message_id
            )
            
            self.stats["processed"] += 1
            if self.stats["processed"] % 10 == 0:
                print(f"Processed {self.stats['processed']} messages")
            
            return True
        
        except Exception as e:
            print(f"Error processing message {message_id}: {e}")
            self.stats["errors"] += 1
            # Don't acknowledge on error - message will be retried
            return False
    
    async def run(self, batch_size: int = 10, block_ms: int = 5000):
        """
        Main worker loop - continuously consume and process messages
        """
        # Ensure consumer group exists
        await self.ensure_consumer_group()
        
        self.stats["start_time"] = asyncio.get_event_loop().time()
        print(f"Worker {self.consumer_name} started. Consuming from stream: {self.stream_name}")
        
        try:
            while True:
                try:
                    # Read messages from stream using consumer group
                    messages = await self.redis_client.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.consumer_name,
                        streams={self.stream_name: '>'},
                        count=batch_size,
                        block=block_ms
                    )
                    
                    if messages:
                        # Process messages concurrently
                        tasks = []
                        for stream_name, stream_messages in messages:
                            for message_id, message_data in stream_messages:
                                tasks.append(self.process_message(message_id, message_data))
                        
                        if tasks:
                            results = await asyncio.gather(*tasks, return_exceptions=True)
                            # Log any exceptions
                            for result in results:
                                if isinstance(result, Exception):
                                    print(f"Task error: {result}")
                    
                    # Brief pause to avoid tight loop
                    await asyncio.sleep(0.1)
                
                except redis.ConnectionError as e:
                    print(f"Redis connection error: {e}. Retrying in 5 seconds...")
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"Error in worker loop: {e}")
                    await asyncio.sleep(1)
        
        except KeyboardInterrupt:
            print("\nWorker interrupted by user")
        finally:
            # Cleanup
            if self.local_analyzer:
                if hasattr(self.local_analyzer, 'close'):
                    await self.local_analyzer.close()
            if self.external_analyzer:
                if hasattr(self.external_analyzer, 'close'):
                    await self.external_analyzer.close()
            
            elapsed = asyncio.get_event_loop().time() - self.stats["start_time"]
            rate = self.stats["processed"] / elapsed if elapsed > 0 else 0
            print(f"Worker stopped. Processed: {self.stats['processed']}, Errors: {self.stats['errors']}, Rate: {rate:.2f} msg/s")


async def main():
    """Main entry point"""
    print("Worker starting...")
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    stream_name = os.getenv("REDIS_STREAM_NAME", "social_posts_stream")
    consumer_group = os.getenv("REDIS_CONSUMER_GROUP", "sentiment_workers")
    
    # Connect to Redis
    print(f"Connecting to Redis at {redis_host}:{redis_port}...")
    redis_client = await redis.Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True
    )
    
    # Test connection
    await redis_client.ping()
    print("Connected to Redis")
    
    # Create and start worker
    worker = SentimentWorker(
        redis_client,
        AsyncSessionLocal,
        stream_name,
        consumer_group,
        consumer_name="worker-1"
    )
    
    await worker.run()
    
    # Close Redis connection
    await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())

