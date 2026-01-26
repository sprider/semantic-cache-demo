"""
Cache module for Semantic Cache Demo using Amazon S3 Vectors
Handles Steps 4, 5a, 7: Vector Search, Cache Hit, Store in Cache

S3 Vectors provides serverless vector storage with native similarity search.
"""

import os
import hashlib
import logging
from typing import List, Dict, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CacheClient:
    """Client for Amazon S3 Vectors with native vector search capabilities"""
    
    def __init__(self):
        self.vector_bucket_name = os.environ.get('VECTOR_BUCKET_NAME')
        self.index_name = os.environ.get('VECTOR_INDEX_NAME', 'semanticcache')
        self.similarity_threshold = float(os.environ.get('SIMILARITY_THRESHOLD', '0.85'))
        
        # Handle disabled cache case
        if not self.vector_bucket_name or self.vector_bucket_name == "disabled":
            logger.info("Cache is disabled - running in LLM-only mode")
            self.s3vectors_client = None
            return
        
        # Initialize S3 Vectors client
        try:
            self.s3vectors_client = boto3.client('s3vectors')
            logger.info(f"Initialized S3 Vectors client (bucket: {self.vector_bucket_name}, index: {self.index_name})")
        except Exception as e:
            logger.error(f"Failed to initialize S3 Vectors client: {str(e)}")
            self.s3vectors_client = None
    
    def search_cache(self, embedding: List[float], request_id: str = "unknown") -> Optional[Dict]:
        """
        Step 4 & 5a: Search for similar embeddings in cache using S3 Vectors QueryVectors API
        
        Args:
            embedding: Query embedding (1024 dimensions)
            request_id: Request ID for logging traceability
            
        Returns:
            Dict with response and similarity if hit, None if miss
        """
        # Handle disabled cache
        if self.s3vectors_client is None:
            logger.info(f"[{request_id}] Step 4: Cache disabled - returning cache miss")
            return None
            
        try:
            # Query S3 Vectors for most similar embedding (topK=1)
            response = self.s3vectors_client.query_vectors(
                vectorBucketName=self.vector_bucket_name,
                indexName=self.index_name,
                queryVector={"float32": embedding},
                topK=1,
                returnDistance=True,
                returnMetadata=True
            )
            
            vectors = response.get('vectors', [])
            if not vectors or len(vectors) == 0:
                logger.info(f"[{request_id}] Step 4: No cached entries found")
                return None
            
            # Get the best match (first result)
            best_match = vectors[0]
            
            # Extract metadata
            metadata = best_match.get('metadata', {})
            response_text = metadata.get('response', '')
            query_text = metadata.get('query', '')
            
            # Calculate similarity from distance
            # S3 Vectors returns cosine distance (lower = more similar)
            # For cosine distance: similarity = 1 - distance
            distance = best_match.get('distance', 1.0)
            similarity = 1.0 - distance
            
            if not response_text:
                logger.warning(f"[{request_id}] Incomplete search result - missing response")
                return None
            
            logger.info(f"[{request_id}] Step 4: Found similar query (similarity: {similarity:.3f})")
            
            # Step 5a: Check if similarity meets threshold
            if similarity >= self.similarity_threshold:
                logger.info(f"[{request_id}] Step 5a: Cache HIT (similarity: {similarity:.3f} >= {self.similarity_threshold})")
                return {
                    'response': response_text,
                    'similarity': similarity,
                    'cached_query': query_text
                }
            else:
                logger.info(f"[{request_id}] Step 4: Cache MISS (similarity: {similarity:.3f} < {self.similarity_threshold})")
                return None
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['NoSuchIndex', 'ResourceNotFoundException']:
                logger.info(f"[{request_id}] Step 4: Vector index not found - cache miss")
                return None
            else:
                logger.error(f"[{request_id}] Cache search error: {error_code} - {str(e)}")
                return None
        except Exception as e:
            logger.error(f"[{request_id}] Cache search error: {str(e)}")
            return None
    
    def store_in_cache(self, query: str, embedding: List[float], response: str, request_id: str = "unknown") -> None:
        """
        Step 7: Store query, embedding, and response in cache using S3 Vectors PutVectors API
        
        Args:
            query: Original query text
            embedding: Query embedding (1024 dimensions)
            response: LLM response to cache
            request_id: Request ID for logging traceability
        """
        # Handle disabled cache
        if self.s3vectors_client is None:
            logger.info(f"[{request_id}] Step 7: Cache disabled - skipping storage")
            return
            
        try:
            # Generate cache key from query hash
            query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()
            vector_key = f"cache_{query_hash}"
            
            # Store vector with metadata using S3 Vectors PutVectors API
            self.s3vectors_client.put_vectors(
                vectorBucketName=self.vector_bucket_name,
                indexName=self.index_name,
                vectors=[
                    {
                        "key": vector_key,
                        "data": {"float32": embedding},
                        "metadata": {
                            "query": query,
                            "response": response
                        }
                    }
                ]
            )
            
            logger.info(f"[{request_id}] Step 7: Stored in cache (key: {vector_key})")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.warning(f"[{request_id}] Cache storage error: {error_code} - {str(e)}")
            # Don't raise - storage is best effort
        except Exception as e:
            logger.error(f"[{request_id}] Cache storage error: {str(e)}")
            # Don't raise - storage is best effort
