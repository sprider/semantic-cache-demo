"""
Enhanced LLM module for Semantic Cache Demo
Handles Steps 5b, 6: Cache Miss, LLM Response using Claude Haiku 4.5
Implements enhanced retry strategy based on AWS Bedrock throttling troubleshooting guide

Model ID verified against AWS documentation: January 2026
- us.anthropic.claude-haiku-4-5-20251001-v1:0 (Claude Haiku 4.5 inference profile)
- Verify latest at: https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html
"""

import json
import time
import random
import logging
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from rate_limiter import bedrock_rate_limiter

logger = logging.getLogger(__name__)

class LLMClient:
    """Enhanced client for Amazon Bedrock Claude Haiku 4.5 with improved throttling handling"""
    
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
        # Use inference profile ID (required for Claude Haiku 4.5)
        self.model_id = 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 30.0
        self.max_tokens = 1024
    
    def invoke_llm(self, query: str) -> str:
        """
        Steps 5b, 6: Invoke Claude Haiku 4.5 for cache miss
        
        Args:
            query: User query to answer
            
        Returns:
            LLM response text
            
        Raises:
            ValueError: If query is empty
            Exception: If Bedrock call fails after retries
        """
        # Step 5b: Input validation
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        # Prepare request body for Claude Haiku 4.5
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": query.strip()
                }
            ],
            "temperature": 0.1  # Low temperature for consistent responses
        }
        
        # Step 5b-6: Call Bedrock with exponential backoff and rate limiting
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
                
                # Extract text from Claude response
                if 'content' in response_body and len(response_body['content']) > 0:
                    response_text = response_body['content'][0]['text']
                    logger.info(f"Step 6: Generated LLM response (length: {len(response_text)})")
                    return response_text
                else:
                    raise Exception("No content in LLM response")
                
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
                    logger.error("Access denied to Claude Haiku 4.5")
                    raise Exception("Access denied - enable Claude Haiku 4.5 in Bedrock Console")
                
                elif error_code == 'ValidationException':
                    logger.error(f"Validation error: {e.response['Error']['Message']}")
                    raise Exception(f"Invalid request: {e.response['Error']['Message']}")
                
                else:
                    logger.error(f"Bedrock error: {error_code}")
                    raise Exception(f"Bedrock error: {error_code}")
            
            except Exception as e:
                logger.error(f"LLM invocation failed: {str(e)}")
                raise Exception(f"LLM invocation failed: {str(e)}")
        
        raise Exception("Max retries exceeded")