"""
Unit tests for cache module (Steps 4, 5a, 7)
Tests Amazon S3 Vectors implementation for semantic caching
"""

import pytest
import hashlib
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src/cache_orchestrator'))

from cache import CacheClient


class TestCacheClient:
    
    def setup_method(self):
        """Setup test fixtures"""
        with patch.dict(os.environ, {
            'VECTOR_BUCKET_NAME': 'test-vector-bucket',
            'VECTOR_INDEX_NAME': 'semantic_cache',
            'SIMILARITY_THRESHOLD': '0.85'
        }):
            with patch('cache.boto3.client') as mock_boto:
                self.mock_s3vectors = Mock()
                mock_boto.return_value = self.mock_s3vectors
                self.client = CacheClient()
    
    @patch.dict(os.environ, {
        'VECTOR_BUCKET_NAME': 'test-vector-bucket',
        'VECTOR_INDEX_NAME': 'semantic_cache',
        'SIMILARITY_THRESHOLD': '0.85'
    })
    @patch('cache.boto3.client')
    def test_init(self, mock_boto):
        """Test CacheClient initialization"""
        mock_s3vectors = Mock()
        mock_boto.return_value = mock_s3vectors
        
        client = CacheClient()
        
        assert client.vector_bucket_name == 'test-vector-bucket'
        assert client.index_name == 'semantic_cache'
        assert client.similarity_threshold == 0.85
        assert client.s3vectors_client is not None
        
        # Verify S3 Vectors client initialization
        mock_boto.assert_called_once_with('s3vectors')
    
    @patch.dict(os.environ, {
        'VECTOR_BUCKET_NAME': 'disabled',
        'VECTOR_INDEX_NAME': 'semantic_cache',
        'SIMILARITY_THRESHOLD': '0.85'
    })
    def test_init_disabled_cache(self):
        """Test CacheClient initialization with disabled cache"""
        client = CacheClient()
        
        assert client.vector_bucket_name == 'disabled'
        assert client.s3vectors_client is None
    
    @patch.dict(os.environ, {
        'VECTOR_INDEX_NAME': 'semantic_cache',
        'SIMILARITY_THRESHOLD': '0.85'
    }, clear=True)
    def test_init_missing_bucket_name(self):
        """Test CacheClient initialization with missing bucket name"""
        # Clear VECTOR_BUCKET_NAME to test missing case
        if 'VECTOR_BUCKET_NAME' in os.environ:
            del os.environ['VECTOR_BUCKET_NAME']
        
        client = CacheClient()
        
        assert client.vector_bucket_name is None
        assert client.s3vectors_client is None
    
    @patch.dict(os.environ, {
        'VECTOR_BUCKET_NAME': 'test-vector-bucket',
        'VECTOR_INDEX_NAME': 'semantic_cache',
        'SIMILARITY_THRESHOLD': '0.85'
    })
    @patch('cache.boto3.client')
    def test_init_boto_client_error(self, mock_boto):
        """Test CacheClient initialization when boto3 client fails"""
        mock_boto.side_effect = Exception("Failed to create client")
        
        client = CacheClient()
        
        assert client.vector_bucket_name == 'test-vector-bucket'
        assert client.s3vectors_client is None
    
    def test_search_cache_no_results(self):
        """Test cache search with no results"""
        # Mock empty search results
        self.client.s3vectors_client.query_vectors.return_value = {'vectors': []}
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        assert result is None
        
        # Verify query_vectors was called with correct parameters
        self.client.s3vectors_client.query_vectors.assert_called_once_with(
            vectorBucketName='test-vector-bucket',
            indexName='semantic_cache',
            queryVector={'float32': [0.1] * 1024},
            topK=1,
            returnDistance=True,
            returnMetadata=True
        )
    
    def test_search_cache_hit(self):
        """Test cache search with hit above threshold"""
        # Mock search results with high similarity (low distance)
        # similarity = 1 - distance, so distance 0.1 = similarity 0.9
        mock_response = {
            'vectors': [
                {
                    'key': 'cache_abc123',
                    'distance': 0.1,  # Low distance = high similarity (0.9)
                    'metadata': {
                        'response': 'Paris is the capital of France.',
                        'query': 'What is the capital of France?'
                    }
                }
            ]
        }
        self.client.s3vectors_client.query_vectors.return_value = mock_response
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        # Verify cache hit
        assert result is not None
        assert result['response'] == 'Paris is the capital of France.'
        assert result['similarity'] == 0.9  # 1.0 - 0.1
        assert result['cached_query'] == 'What is the capital of France?'
    
    def test_search_cache_miss_low_similarity(self):
        """Test cache search with miss due to low similarity"""
        # Mock search results with low similarity (high distance)
        # similarity = 1 - distance, so distance 0.5 = similarity 0.5
        mock_response = {
            'vectors': [
                {
                    'key': 'cache_abc123',
                    'distance': 0.5,  # High distance = low similarity (0.5)
                    'metadata': {
                        'response': 'Paris is the capital of France.',
                        'query': 'What is the capital of France?'
                    }
                }
            ]
        }
        self.client.s3vectors_client.query_vectors.return_value = mock_response
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        # Verify cache miss (similarity 0.5 < threshold 0.85)
        assert result is None
    
    def test_search_cache_missing_response_metadata(self):
        """Test cache search with incomplete metadata"""
        mock_response = {
            'vectors': [
                {
                    'key': 'cache_abc123',
                    'distance': 0.1,
                    'metadata': {
                        'query': 'What is the capital of France?'
                        # Missing 'response' field
                    }
                }
            ]
        }
        self.client.s3vectors_client.query_vectors.return_value = mock_response
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        # Should return None due to missing response
        assert result is None
    
    def test_search_cache_no_such_index_error(self):
        """Test cache search with NoSuchIndex error"""
        error_response = {'Error': {'Code': 'NoSuchIndex', 'Message': 'Index not found'}}
        self.client.s3vectors_client.query_vectors.side_effect = ClientError(error_response, 'QueryVectors')
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        # Should return None (graceful degradation)
        assert result is None
    
    def test_search_cache_resource_not_found_error(self):
        """Test cache search with ResourceNotFoundException error"""
        error_response = {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Resource not found'}}
        self.client.s3vectors_client.query_vectors.side_effect = ClientError(error_response, 'QueryVectors')
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        # Should return None (graceful degradation)
        assert result is None
    
    def test_search_cache_client_error(self):
        """Test cache search with generic ClientError"""
        error_response = {'Error': {'Code': 'InternalServerError', 'Message': 'Server error'}}
        self.client.s3vectors_client.query_vectors.side_effect = ClientError(error_response, 'QueryVectors')
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        # Should return None on error (graceful degradation)
        assert result is None
    
    def test_search_cache_generic_exception(self):
        """Test cache search with generic exception"""
        self.client.s3vectors_client.query_vectors.side_effect = Exception("Generic search error")
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        # Should return None on exception (graceful degradation)
        assert result is None
    
    def test_store_in_cache_success(self):
        """Test successful cache storage"""
        query = "What is the capital of France?"
        embedding = [0.1] * 1024
        response = "Paris is the capital of France."
        
        self.client.store_in_cache(query, embedding, response, "test-request")
        
        # Verify put_vectors was called with correct parameters
        expected_key = f"cache_{hashlib.md5(query.encode('utf-8')).hexdigest()}"
        
        self.client.s3vectors_client.put_vectors.assert_called_once_with(
            vectorBucketName='test-vector-bucket',
            indexName='semantic_cache',
            vectors=[
                {
                    'key': expected_key,
                    'data': {'float32': embedding},
                    'metadata': {
                        'query': query,
                        'response': response
                    }
                }
            ]
        )
    
    def test_store_in_cache_client_error(self):
        """Test cache storage with ClientError"""
        error_response = {'Error': {'Code': 'ValidationException', 'Message': 'Invalid input'}}
        self.client.s3vectors_client.put_vectors.side_effect = ClientError(error_response, 'PutVectors')
        
        # Should not raise exception (best effort storage)
        self.client.store_in_cache("test", [0.1] * 1024, "response", "test-request")
        
        # Verify put_vectors was attempted
        self.client.s3vectors_client.put_vectors.assert_called_once()
    
    def test_store_in_cache_generic_exception(self):
        """Test cache storage with generic exception"""
        self.client.s3vectors_client.put_vectors.side_effect = Exception("Generic storage error")
        
        # Should not raise exception (best effort)
        self.client.store_in_cache("test query", [0.1] * 1024, "test response", "test-request")
    
    def test_search_cache_disabled_client(self):
        """Test search_cache with disabled cache client"""
        # Create client with disabled cache
        with patch.dict(os.environ, {'VECTOR_BUCKET_NAME': 'disabled'}):
            client = CacheClient()
        
        result = client.search_cache([0.1] * 1024, "test-request")
        assert result is None
    
    def test_store_in_cache_disabled_client(self):
        """Test store_in_cache with disabled cache client"""
        # Create client with disabled cache
        with patch.dict(os.environ, {'VECTOR_BUCKET_NAME': 'disabled'}):
            client = CacheClient()
        
        # Should not raise exception
        client.store_in_cache("test query", [0.1] * 1024, "test response", "test-request")
    
    def test_search_cache_empty_vectors_response(self):
        """Test cache search when response has empty vectors key"""
        mock_response = {'vectors': None}
        self.client.s3vectors_client.query_vectors.return_value = mock_response
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        assert result is None
    
    def test_search_cache_exact_threshold_match(self):
        """Test cache search with exact threshold match"""
        # similarity = 1 - distance, threshold is 0.85
        # So distance 0.15 = similarity 0.85 (exactly at threshold)
        mock_response = {
            'vectors': [
                {
                    'key': 'cache_abc123',
                    'distance': 0.15,  # Exactly at threshold
                    'metadata': {
                        'response': 'Test response',
                        'query': 'Test query'
                    }
                }
            ]
        }
        self.client.s3vectors_client.query_vectors.return_value = mock_response
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        # Should be a hit (similarity >= threshold)
        assert result is not None
        assert result['similarity'] == 0.85
    
    def test_search_cache_just_below_threshold(self):
        """Test cache search with similarity just below threshold"""
        # distance 0.16 = similarity 0.84 (just below 0.85)
        mock_response = {
            'vectors': [
                {
                    'key': 'cache_abc123',
                    'distance': 0.16,
                    'metadata': {
                        'response': 'Test response',
                        'query': 'Test query'
                    }
                }
            ]
        }
        self.client.s3vectors_client.query_vectors.return_value = mock_response
        
        result = self.client.search_cache([0.1] * 1024, "test-request")
        
        # Should be a miss (similarity < threshold)
        assert result is None
    
    @patch.dict(os.environ, {
        'VECTOR_BUCKET_NAME': 'test-bucket',
        'SIMILARITY_THRESHOLD': '0.90'
    })
    @patch('cache.boto3.client')
    def test_custom_similarity_threshold(self, mock_boto):
        """Test cache client with custom similarity threshold"""
        mock_boto.return_value = Mock()
        client = CacheClient()
        
        assert client.similarity_threshold == 0.90
    
    @patch.dict(os.environ, {
        'VECTOR_BUCKET_NAME': 'test-bucket',
        'VECTOR_INDEX_NAME': 'custom_index'
    })
    @patch('cache.boto3.client')
    def test_custom_index_name(self, mock_boto):
        """Test cache client with custom index name"""
        mock_boto.return_value = Mock()
        client = CacheClient()
        
        assert client.index_name == 'custom_index'
    
    def test_store_different_queries_get_different_keys(self):
        """Test that different queries get different cache keys"""
        query1 = "What is the capital of France?"
        query2 = "What is the capital of Germany?"
        embedding = [0.1] * 1024
        
        self.client.store_in_cache(query1, embedding, "Paris", "req-1")
        self.client.store_in_cache(query2, embedding, "Berlin", "req-2")
        
        # Get the keys from the put_vectors calls
        calls = self.client.s3vectors_client.put_vectors.call_args_list
        key1 = calls[0][1]['vectors'][0]['key']
        key2 = calls[1][1]['vectors'][0]['key']
        
        # Keys should be different for different queries
        assert key1 != key2
        
        # Keys should be deterministic
        expected_key1 = f"cache_{hashlib.md5(query1.encode('utf-8')).hexdigest()}"
        expected_key2 = f"cache_{hashlib.md5(query2.encode('utf-8')).hexdigest()}"
        assert key1 == expected_key1
        assert key2 == expected_key2
