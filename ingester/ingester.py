"""
Data ingester service - publishes social media posts to Redis Stream
"""
import asyncio
import os
import random
import time
from datetime import datetime, timezone
from typing import Dict
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()


class DataIngester:
    """
    Publishes simulated social media posts to Redis Stream
    """
    
    def __init__(self, redis_client: redis.Redis, stream_name: str, posts_per_minute: int = 60):
        """
        Initialize the ingester
        
        Args:
            redis_client: Redis connection instance
            stream_name: Name of the Redis stream to publish to
            posts_per_minute: Rate of post generation (default: 60)
        """
        self.redis_client = redis_client
        self.stream_name = stream_name
        self.posts_per_minute = posts_per_minute
        self.interval_seconds = 60.0 / posts_per_minute
        
        # Post templates for realistic content
        self.positive_templates = [
            "I absolutely love {product}! Best purchase I've made this year.",
            "This {product} exceeded my expectations! Highly recommended.",
            "Amazing experience with {product}. Can't believe how good it is!",
            "{product} is fantastic! Worth every penny.",
            "So happy I got {product}. It's absolutely amazing!",
            "Incredible quality from {product}. Very impressed!",
            "{product} has changed my life for the better!",
            "This {product} is outstanding! 5 stars!",
            "I'm obsessed with {product}! It's perfect!",
            "{product} is the best thing I've ever bought!"
        ]
        
        self.negative_templates = [
            "Very disappointed with {product}. Not worth the money.",
            "Terrible experience with {product}. Would not recommend.",
            "{product} broke after just one week. So frustrating!",
            "Waste of money on {product}. Poor quality and customer service.",
            "I hate {product}. Complete waste of time and money.",
            "Regret buying {product}. It doesn't work as advertised.",
            "{product} is awful. Don't buy it!",
            "Extremely disappointed in {product}. Quality is terrible.",
            "{product} failed to meet expectations. Very unsatisfied.",
            "Would never buy {product} again. Worst purchase ever."
        ]
        
        self.neutral_templates = [
            "Just tried {product} for the first time. We'll see how it goes.",
            "Received {product} today. Starting to use it now.",
            "Using {product} for the first time today.",
            "Got my {product} in the mail. Looks interesting.",
            "Trying out {product} to see if it fits my needs.",
            "Unboxed {product} earlier. Setting it up now.",
            "Ordered {product} last week. It arrived today.",
            "Reviewing {product} for a project I'm working on.",
            "Checking out {product} based on a friend's recommendation.",
            "New {product} arrived. Time to test it out."
        ]
        
        self.products = [
            "iPhone 16", "Tesla Model 3", "ChatGPT", "Netflix", "Amazon Prime",
            "Spotify", "YouTube Premium", "PlayStation 5", "Xbox Series X",
            "AirPods Pro", "MacBook Pro", "iPad", "Samsung Galaxy S24",
            "Google Pixel 8", "Windows 11", "Discord", "Slack", "Zoom",
            "Notion", "Figma", "Adobe Creative Cloud", "Microsoft 365"
        ]
        
        self.sources = ["reddit", "twitter", "facebook", "instagram", "linkedin"]
        
        self.post_counter = 0
    
    def generate_post(self) -> Dict:
        """
        Generate a single realistic post with varied sentiment
        
        Returns dict with keys: post_id, source, content, author, created_at
        """
        # Determine sentiment distribution: 40% positive, 30% neutral, 30% negative
        rand = random.random()
        if rand < 0.4:
            template_list = self.positive_templates
        elif rand < 0.7:
            template_list = self.neutral_templates
        else:
            template_list = self.negative_templates
        
        # Select random template and product
        template = random.choice(template_list)
        product = random.choice(self.products)
        content = template.format(product=product)
        
        # Ensure content length is between 50-500 characters
        if len(content) < 50:
            content += " " + " ".join(random.choices(["Great!", "Nice!", "Cool!", "Interesting!"], k=10))
        elif len(content) > 500:
            content = content[:497] + "..."
        
        # Generate post data
        self.post_counter += 1
        post_id = f"post_{int(time.time() * 1000)}_{self.post_counter}"
        source = random.choice(self.sources)
        author = f"user_{random.randint(1000, 9999)}_{random.choice(['2023', '2024', '2025'])}"
        
        # Random created_at within last 7 days
        from datetime import timedelta
        days_ago = random.uniform(0, 7)
        created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        created_at_iso = created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return {
            'post_id': post_id,
            'source': source,
            'content': content,
            'author': author,
            'created_at': created_at_iso
        }
    
    async def publish_post(self, post_data: Dict) -> bool:
        """
        Publish a single post to Redis Stream
        
        Args:
            post_data: Dictionary from generate_post()
        
        Returns:
            bool: True if published successfully, False otherwise
        """
        try:
            # Convert post_data to Redis Stream format
            # Redis Streams require field-value pairs
            message_data = {
                'post_id': post_data['post_id'],
                'source': post_data['source'],
                'content': post_data['content'],
                'author': post_data['author'],
                'created_at': post_data['created_at']
            }
            
            # Use XADD to add message to stream
            message_id = await self.redis_client.xadd(
                self.stream_name,
                message_data
            )
            
            print(f"Published post {post_data['post_id']} to stream (ID: {message_id})")
            return True
        
        except Exception as e:
            print(f"Error publishing post to Redis: {e}")
            return False
    
    async def start(self, duration_seconds: int = None):
        """
        Start continuous post generation and publishing
        
        Args:
            duration_seconds: How long to run (None = run indefinitely)
        """
        start_time = time.time()
        post_count = 0
        
        print(f"Starting ingester: {self.posts_per_minute} posts/minute")
        
        try:
            while True:
                # Check duration limit
                if duration_seconds and (time.time() - start_time) >= duration_seconds:
                    print(f"Ingester stopping after {duration_seconds} seconds")
                    break
                
                # Generate and publish post
                post_data = self.generate_post()
                success = await self.publish_post(post_data)
                
                if success:
                    post_count += 1
                
                # Sleep to maintain rate
                await asyncio.sleep(self.interval_seconds)
        
        except KeyboardInterrupt:
            print("\nIngester interrupted by user")
        finally:
            print(f"Ingester stopped. Published {post_count} posts.")


async def main():
    """Main entry point"""
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    stream_name = os.getenv("REDIS_STREAM_NAME", "social_posts_stream")
    posts_per_minute = int(os.getenv("POSTS_PER_MINUTE", "60"))
    
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
    
    # Create and start ingester
    ingester = DataIngester(redis_client, stream_name, posts_per_minute)
    await ingester.start()  # Run indefinitely
    
    # Close Redis connection
    await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())

