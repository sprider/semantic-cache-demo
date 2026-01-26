"""
Enhanced Embedding module for Semantic Cache Demo
Handles Step 3: Generate Embedding using Amazon Titan Embeddings V2
Implements enhanced retry strategy based on AWS Bedrock throttling troubleshooting guide

Model ID verified against AWS documentation: January 2026
- amazon.titan-embed-text-v2:0 (1024 dimensions)
- Verify latest at: https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html
"""

import json
import time
import random
import logging
from typing import List
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from rate_limiter import bedrock_rate_limiter

logger = logging.getLogger(__name__)

class EmbeddingClient:
    """Enhanced client for Amazon Bedrock Titan Embeddings V2 with improved throttling handling"""
    
    def __init__(self):
        # Retry configuration aligned with spec
        retry_config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            read_timeout=30,
            connect_timeout=10
        )
        
        self.bedrock_runtime = boto3.client('bedrock-runtime', config=retry_config)
        self.model_id = 'amazon.titan-embed-text-v2:0'
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 30.0
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for input text using Titan Embeddings V2
        
        Args:
            text: Input text to embed (max 8192 tokens)
            
        Returns:
            List of 1024 float values representing the embedding
            
        Raises:
            ValueError: If text is empty or too long
            Exception: If Bedrock call fails after retries
        """
        # Step 3: Input validation
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        if len(text) > 8000:  # Conservative limit for Titan V2
            raise ValueError("Text too long (max 8000 characters)")
        
        # Prepare request body for Titan V2
        body = {
            "inputText": text.strip(),
            "normalize": True,  # For cosine similarity
            "dimensions": 1024  # Titan V2 output dimensions
        }
        
        # Step 3: Call Bedrock with exponential backoff
        for attempt in range(self.max_retries):
            try:
                # Use rate limiter to serialize Bedrock calls across all Lambda instances
                with bedrock_rate_limiter.acquire_bedrock_call_lock():
                    response = self.bedrock_runtime.invoke_model(
                        modelId=self.model_id,
                        body=json.dumps(body),
                        contentType='application/json',
                        accept='application/json'
                    )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                embedding = response_body['embedding']
                
                # Validate embedding dimensions
                if len(embedding) != 1024:
                    raise ValueError(f"Expected 1024 dimensions, got {len(embedding)}")
                
                logger.info(f"Generated embedding for text (length: {len(text)})")
                return embedding
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if error_code == 'ThrottlingException':
                    if attempt < self.max_retries - 1:
                        # Enhanced exponential backoff with jitter (AWS best practices)
                        base_delay = self.base_delay * (2 ** attempt)
                        # Add substantial jitter to avoid thundering herd problem
                        jitter = random.uniform(0, 0.3) * base_delay
                        delay = min(base_delay + jitter, self.max_delay)
                        
                        # For quota-based throttling, ensure we wait at least until next minute boundary
                        if attempt >= 3:  # After several attempts, sync with quota refresh
                            current_time = time.time()
                            seconds_to_next_minute = 60 - (current_time % 60)
                            if seconds_to_next_minute < 30:  # If close to next minute, wait for it
                                delay = max(delay, seconds_to_next_minute + random.uniform(1, 5))
                        
                        logger.warning(f"Throttled, enhanced retry in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error("Max retries exceeded for throttling - quota limits reached")
                        raise Exception("Bedrock throttling - quota limits exceeded after enhanced retries")
                
                elif error_code == 'AccessDeniedException':
                    logger.error("Access denied to Titan Embeddings V2")
                    raise Exception("Access denied - enable Titan Embeddings V2 in Bedrock Console")
                
                else:
                    logger.error(f"Bedrock error: {error_code}")
                    raise Exception(f"Bedrock error: {error_code}")
            
            except Exception as e:
                logger.error(f"Embedding generation failed: {str(e)}")
                raise Exception(f"Embedding generation failed: {str(e)}")
        
        raise Exception("Max retries exceeded")