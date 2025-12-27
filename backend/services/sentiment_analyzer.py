"""
Sentiment analysis service using Hugging Face and external LLM APIs
"""
import os
from typing import Dict, List, Optional
import httpx
import json
from transformers import pipeline
import torch


class SentimentAnalyzer:
    """Unified interface for sentiment analysis using multiple model backends"""
    
    def __init__(self, model_type: str = 'local', model_name: Optional[str] = None):
        """
        Initialize analyzer with specified backend
        
        Args:
            model_type: 'local' for Hugging Face or 'external' for LLM API
            model_name: Specific model to use (uses env var if None)
        """
        self.model_type = model_type
        self._pipelines_initialized = False
        
        if model_type == 'local':
            self.model_name = model_name or os.getenv(
                "HUGGINGFACE_MODEL",
                "distilbert-base-uncased-finetuned-sst-2-english"
            )
            self.emotion_model = os.getenv(
                "EMOTION_MODEL",
                "j-hartmann/emotion-english-distilroberta-base"
            )
            # Don't initialize pipelines here - do it lazily when needed
            self.sentiment_pipeline = None
            self.emotion_pipeline = None
        
        elif model_type == 'external':
            self.provider = os.getenv("EXTERNAL_LLM_PROVIDER", "groq").lower()
            self.api_key = os.getenv("EXTERNAL_LLM_API_KEY", "")
            self.model_name = model_name or os.getenv("EXTERNAL_LLM_MODEL", "llama-3.1-8b-instant")
            
            if self.provider == "groq":
                self.api_base = "https://api.groq.com/openai/v1"
            elif self.provider == "openai":
                self.api_base = "https://api.openai.com/v1"
            elif self.provider == "anthropic":
                self.api_base = "https://api.anthropic.com/v1"
            else:
                raise ValueError(f"Unsupported LLM provider: {self.provider}")
            
            self.client = httpx.AsyncClient(timeout=30.0)
        else:
            raise ValueError(f"Invalid model_type: {model_type}. Must be 'local' or 'external'")
    
    async def analyze_sentiment(self, text: str) -> Dict:
        """
        Analyze sentiment of input text
        
        Returns dict with:
        - sentiment_label: 'positive', 'negative', or 'neutral'
        - confidence_score: float between 0.0 and 1.0
        - model_name: str
        """
        if not text or len(text.strip()) == 0:
            return {
                "sentiment_label": "neutral",
                "confidence_score": 0.5,
                "model_name": self.model_name
            }
        
        if self.model_type == 'local':
            # Initialize pipeline lazily if not already done
            if not self._pipelines_initialized or self.sentiment_pipeline is None:
                try:
                    self.sentiment_pipeline = pipeline(
                        "sentiment-analysis",
                        model=self.model_name,
                        device=-1  # Use CPU
                    )
                    self._pipelines_initialized = True
                except Exception as e:
                    print(f"Error initializing sentiment pipeline: {e}")
                    raise RuntimeError(f"Failed to initialize local sentiment model: {e}")
            
            # Truncate text to model's max length (512 tokens)
            text_truncated = text[:512] if len(text) > 512 else text
            
            result = self.sentiment_pipeline(text_truncated)[0]
            label = result['label'].upper()
            score = float(result['score'])
            
            # Map labels to standard format
            if 'POSITIVE' in label or 'POS' in label:
                sentiment_label = "positive"
            elif 'NEGATIVE' in label or 'NEG' in label:
                sentiment_label = "negative"
            else:
                sentiment_label = "neutral"
            
            return {
                "sentiment_label": sentiment_label,
                "confidence_score": score,
                "model_name": self.model_name
            }
        
        else:  # external LLM
            prompt = f"""Analyze the sentiment of the following text and respond with ONLY a JSON object in this exact format:
{{"sentiment": "positive|negative|neutral", "confidence": 0.0-1.0}}

Text: {text}

JSON:"""
            
            try:
                if self.provider == "groq" or self.provider == "openai":
                    response = await self.client.post(
                        f"{self.api_base}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model_name,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.3,
                            "max_tokens": 100
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"].strip()
                
                elif self.provider == "anthropic":
                    response = await self.client.post(
                        f"{self.api_base}/messages",
                        headers={
                            "x-api-key": self.api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model_name,
                            "max_tokens": 100,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ]
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["content"][0]["text"].strip()
                
                # Parse JSON from response
                # Extract JSON if wrapped in code blocks or markdown
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                result = json.loads(content)
                sentiment = result.get("sentiment", "neutral").lower()
                confidence = float(result.get("confidence", 0.5))
                
                # Normalize sentiment label
                if sentiment in ["pos", "positive"]:
                    sentiment_label = "positive"
                elif sentiment in ["neg", "negative"]:
                    sentiment_label = "negative"
                else:
                    sentiment_label = "neutral"
                
                # Clamp confidence to 0.0-1.0
                confidence = max(0.0, min(1.0, confidence))
                
                return {
                    "sentiment_label": sentiment_label,
                    "confidence_score": confidence,
                    "model_name": self.model_name
                }
            
            except Exception as e:
                print(f"Error calling external LLM: {e}")
                # Fallback to neutral
                return {
                    "sentiment_label": "neutral",
                    "confidence_score": 0.5,
                    "model_name": self.model_name
                }
    
    async def analyze_emotion(self, text: str) -> Dict:
        """
        Detect primary emotion in text
        
        Returns dict with:
        - emotion: 'joy', 'sadness', 'anger', 'fear', 'surprise', or 'neutral'
        - confidence_score: float between 0.0 and 1.0
        - model_name: str
        """
        if not text or len(text.strip()) < 10:
            return {
                "emotion": "neutral",
                "confidence_score": 0.5,
                "model_name": self.model_name
            }
        
        if self.model_type == 'local':
            # Initialize pipeline lazily if not already done
            if not self._pipelines_initialized or self.emotion_pipeline is None:
                try:
                    self.emotion_pipeline = pipeline(
                        "text-classification",
                        model=self.emotion_model,
                        device=-1  # Use CPU
                    )
                    if self.sentiment_pipeline is None:
                        # Also initialize sentiment pipeline if not done
                        self.sentiment_pipeline = pipeline(
                            "sentiment-analysis",
                            model=self.model_name,
                            device=-1  # Use CPU
                        )
                    self._pipelines_initialized = True
                except Exception as e:
                    print(f"Error initializing emotion pipeline: {e}")
                    raise RuntimeError(f"Failed to initialize local emotion model: {e}")
            
            text_truncated = text[:512] if len(text) > 512 else text
            
            result = self.emotion_pipeline(text_truncated)[0]
            emotion_label = result['label'].lower()
            confidence = float(result['score'])
            
            # Map to standard emotions
            emotion_map = {
                'joy': 'joy',
                'happiness': 'joy',
                'sadness': 'sadness',
                'sad': 'sadness',
                'anger': 'anger',
                'angry': 'anger',
                'fear': 'fear',
                'afraid': 'fear',
                'surprise': 'surprise',
                'surprised': 'surprise',
                'neutral': 'neutral',
                'disgust': 'anger'  # Map disgust to anger
            }
            
            emotion = emotion_map.get(emotion_label, 'neutral')
            
            return {
                "emotion": emotion,
                "confidence_score": confidence,
                "model_name": self.model_name
            }
        
        else:  # external LLM
            prompt = f"""Detect the primary emotion in the following text and respond with ONLY a JSON object in this exact format:
{{"emotion": "joy|sadness|anger|fear|surprise|neutral", "confidence": 0.0-1.0}}

Text: {text}

JSON:"""
            
            try:
                if self.provider == "groq" or self.provider == "openai":
                    response = await self.client.post(
                        f"{self.api_base}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model_name,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.3,
                            "max_tokens": 100
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"].strip()
                
                elif self.provider == "anthropic":
                    response = await self.client.post(
                        f"{self.api_base}/messages",
                        headers={
                            "x-api-key": self.api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model_name,
                            "max_tokens": 100,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ]
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["content"][0]["text"].strip()
                
                # Parse JSON
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                result = json.loads(content)
                emotion = result.get("emotion", "neutral").lower()
                confidence = float(result.get("confidence", 0.5))
                
                # Normalize emotion
                valid_emotions = ["joy", "sadness", "anger", "fear", "surprise", "neutral"]
                if emotion not in valid_emotions:
                    emotion = "neutral"
                
                confidence = max(0.0, min(1.0, confidence))
                
                return {
                    "emotion": emotion,
                    "confidence_score": confidence,
                    "model_name": self.model_name
                }
            
            except Exception as e:
                print(f"Error calling external LLM for emotion: {e}")
                return {
                    "emotion": "neutral",
                    "confidence_score": 0.5,
                    "model_name": self.model_name
                }
    
    async def batch_analyze(self, texts: List[str]) -> List[Dict]:
        """
        Analyze multiple texts efficiently
        """
        if not texts:
            return []
        
        if self.model_type == 'local':
            # Batch processing for local models
            results = []
            for text in texts:
                try:
                    result = await self.analyze_sentiment(text)
                    results.append(result)
                except Exception as e:
                    print(f"Error analyzing text: {e}")
                    results.append({
                        "sentiment_label": "neutral",
                        "confidence_score": 0.5,
                        "model_name": self.model_name
                    })
            return results
        
        else:
            # Concurrent API calls for external LLMs
            import asyncio
            tasks = [self.analyze_sentiment(text) for text in texts]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            formatted_results = []
            for result in results:
                if isinstance(result, Exception):
                    print(f"Error in batch analyze: {result}")
                    formatted_results.append({
                        "sentiment_label": "neutral",
                        "confidence_score": 0.5,
                        "model_name": self.model_name
                    })
                else:
                    formatted_results.append(result)
            
            return formatted_results
    
    async def close(self):
        """Clean up resources"""
        if self.model_type == 'external' and hasattr(self, 'client'):
            await self.client.aclose()

