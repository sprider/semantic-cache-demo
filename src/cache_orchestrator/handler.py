"""
Main Lambda handler for Semantic Cache Demo
Orchestrates Steps 2-7: Route, Generate Embedding, Vector Search, Cache Hit/Miss, LLM Response, Store in Cache
"""

import base64
import json
import time
import logging
from typing import Dict, Any

from embedding import EmbeddingClient
from cache import CacheClient
from llm import LLMClient
from metrics import MetricsClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global clients (initialized on cold start)
embedding_client = None
cache_client = None
llm_client = None
metrics_client = None

def init_clients():
    """Initialize clients on cold start"""
    global embedding_client, cache_client, llm_client, metrics_client
    
    if not embedding_client:
        embedding_client = EmbeddingClient()
        logger.info("Initialized embedding client")
    
    if not cache_client:
        cache_client = CacheClient()
        logger.info("Initialized cache client")
    
    if not llm_client:
        llm_client = LLMClient()
        logger.info("Initialized LLM client")
    
    if not metrics_client:
        metrics_client = MetricsClient()
        logger.info("Initialized metrics client")

def parse_request(event: Dict[str, Any]) -> str:
    """
    Step 2: Parse request from API Gateway or direct invocation
    
    Args:
        event: Lambda event
        
    Returns:
        Query string
        
    Raises:
        ValueError: If query is missing or invalid
    """
    # Handle API Gateway format
    if 'body' in event:
        raw_body = event['body']
        if raw_body:
            if isinstance(raw_body, (dict, list)):
                raw_body = json.dumps(raw_body)
            
            # Handle base64 encoding
            if event.get('isBase64Encoded'):
                try:
                    body_bytes = base64.b64decode(raw_body)
                    body_str = body_bytes.decode('utf-8')
                except Exception:
                    raise ValueError("Invalid base64 request body")
            else:
                body_str = raw_body
                body_bytes = body_str.encode('utf-8')

            if len(body_bytes) > 10 * 1024:
                raise ValueError("Request body too large (max 10KB)")

            try:
                body = json.loads(body_str)
                query = body.get('query', '').strip()
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in request body")
        else:
            raise ValueError("Empty request body")
    
    # Handle direct invocation format
    elif 'query' in event:
        query = event['query'].strip()
    
    else:
        raise ValueError("No query found in request")
    
    # Validate query
    if not query:
        raise ValueError("Query cannot be empty")
    
    if len(query) > 8000:
        raise ValueError("Query too long (max 8000 characters)")
    
    return query

def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create API Gateway response format"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(body)
    }

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler - orchestrates Steps 2-7
    
    Args:
        event: API Gateway event or direct invocation
        context: Lambda context
        
    Returns:
        API Gateway response format
    """
    start_time = time.time()
    request_id = getattr(context, 'aws_request_id', 'unknown')
    
    try:
        # Initialize clients on cold start
        init_clients()
        
        # Step 2: Parse and validate request
        query = parse_request(event)
        logger.info(f"[{request_id}] Step 2: Processing query (length: {len(query)})")
        
        # Step 3: Generate embedding
        logger.info(f"[{request_id}] Step 3: Generating embedding...")
        embedding = embedding_client.generate_embedding(query)
        
        # Step 4: Search cache for similar embeddings
        logger.info(f"[{request_id}] Step 4: Searching cache...")
        cache_result = cache_client.search_cache(embedding, request_id)
        
        if cache_result:
            # Step 5a: Cache HIT - return cached response
            latency_ms = (time.time() - start_time) * 1000
            
            response_body = {
                'response': cache_result['response'],
                'source': 'cache',
                'latency_ms': round(latency_ms, 1),
                'similarity': round(cache_result['similarity'], 3)
            }
            
            # Publish metrics
            metrics_client.publish_metrics(cache_hit=True, latency_ms=latency_ms)
            
            logger.info(f"[{request_id}] Step 5a: Cache HIT - returning cached response (latency: {latency_ms:.1f}ms)")
            return create_response(200, response_body)
        
        else:
            # Step 5b-6: Cache MISS - invoke LLM
            logger.info(f"[{request_id}] Step 5b: Cache MISS - invoking LLM...")
            llm_response = llm_client.invoke_llm(query)
            
            # Step 7: Store in cache (best effort - don't fail if this fails)
            try:
                logger.info(f"[{request_id}] Step 7: Storing in cache...")
                cache_client.store_in_cache(query, embedding, llm_response, request_id)
            except Exception as e:
                logger.warning(f"[{request_id}] Step 7: Cache storage failed (non-critical): {str(e)}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            response_body = {
                'response': llm_response,
                'source': 'bedrock',
                'latency_ms': round(latency_ms, 1)
            }
            
            # Publish metrics
            metrics_client.publish_metrics(cache_hit=False, latency_ms=latency_ms)
            
            logger.info(f"[{request_id}] Step 5b-6-7: Cache MISS - returning LLM response (latency: {latency_ms:.1f}ms)")
            return create_response(200, response_body)
    
    except ValueError as e:
        # Client error (400)
        logger.warning(f"[{request_id}] Client error: {str(e)}")
        metrics_client.publish_error_metric('ValidationError')
        return create_response(400, {'error': str(e)})
    
    except Exception as e:
        # Server error (500)
        logger.error(f"[{request_id}] Server error: {str(e)}")
        
        # Determine error type for metrics
        error_type = 'UnknownError'
        if 'embedding' in str(e).lower():
            error_type = 'EmbeddingError'
        elif 'llm' in str(e).lower() or 'bedrock' in str(e).lower():
            error_type = 'LLMError'
        elif 'cache' in str(e).lower():
            error_type = 'CacheError'
        
        metrics_client.publish_error_metric(error_type)
        
        return create_response(500, {
            'error': 'Internal server error',
            'message': str(e)
        })
