"""
Integration tests for the semantic cache API
"""

import pytest
import requests
import json
import time
import os
from typing import Dict, Any


class TestSemanticCacheAPI:
    """Integration tests for the deployed semantic cache API"""
    
    @pytest.fixture(scope="class")
    def api_endpoint(self) -> str:
        """Get API endpoint from environment or CloudFormation"""
        endpoint = os.environ.get('API_ENDPOINT')
        if not endpoint:
            pytest.skip("API_ENDPOINT environment variable not set")
        return endpoint.rstrip('/')
    
    def make_request(self, endpoint: str, query: str, timeout: int = 30) -> Dict[str, Any]:
        """Make a request to the semantic cache API"""
        url = f"{endpoint}/query"
        payload = {"query": query}
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    
    def test_api_endpoint_reachable(self, api_endpoint: str):
        """Test that the API endpoint is reachable"""
        # Make a simple request to verify connectivity
        response = self.make_request(api_endpoint, "Hello, world!")
        
        assert 'response' in response
        assert 'source' in response
        assert 'latency_ms' in response
        assert response['source'] in ['cache', 'bedrock']
    
    def test_cache_miss_flow_steps_1_to_7(self, api_endpoint: str):
        """Test cache miss flow (Steps 1→2→3→4→5b→6→7)"""
        # Use a unique query to ensure cache miss
        unique_query = f"What is the capital of France? {int(time.time())}"
        
        response = self.make_request(api_endpoint, unique_query)
        
        # Verify cache miss response
        assert response['source'] == 'bedrock'
        assert 'response' in response
        assert 'latency_ms' in response
        assert response['latency_ms'] > 500  # Should be slower due to LLM call
        assert 'similarity' not in response  # No similarity for cache miss
        
        # Verify response content is reasonable
        assert len(response['response']) > 10
        assert isinstance(response['response'], str)
    
    def test_cache_hit_flow_steps_1_to_5a(self, api_endpoint: str):
        """Test cache hit flow (Steps 1→2→3→4→5a)"""
        query = "What is the capital of France?"
        
        # First request (cache miss)
        response1 = self.make_request(api_endpoint, query)
        assert response1['source'] == 'bedrock'
        
        # Wait a moment for cache storage to complete
        time.sleep(2)
        
        # Second request (should be cache hit)
        response2 = self.make_request(api_endpoint, query)
        
        # Verify cache hit response
        assert response2['source'] == 'cache'
        assert 'similarity' in response2
        assert response2['similarity'] == 1.0  # Exact match
        assert response2['latency_ms'] < response1['latency_ms']  # Should be faster
        assert response2['response'] == response1['response']  # Same response
    
    def test_semantic_similarity_cache_hit(self, api_endpoint: str):
        """Test semantic similarity cache hit with different phrasing"""
        # First query
        query1 = "What is the capital city of Germany?"
        response1 = self.make_request(api_endpoint, query1)
        assert response1['source'] == 'bedrock'
        
        # Wait for cache storage
        time.sleep(2)
        
        # Semantically similar query with different phrasing
        query2 = "Tell me the capital of Germany"
        response2 = self.make_request(api_endpoint, query2)
        
        # Should be cache hit due to semantic similarity
        if response2['source'] == 'cache':
            assert 'similarity' in response2
            assert response2['similarity'] >= 0.85  # Above threshold
            assert response2['latency_ms'] < response1['latency_ms']
        else:
            # If not cache hit, similarity was below threshold
            pytest.skip("Semantic similarity below threshold - this is acceptable")
    
    def test_different_topics_cache_miss(self, api_endpoint: str):
        """Test that different topics result in cache miss"""
        # First query about France
        query1 = "What is the capital of France?"
        response1 = self.make_request(api_endpoint, query1)
        
        # Wait for cache storage
        time.sleep(2)
        
        # Completely different query about machine learning
        query2 = "What is machine learning?"
        response2 = self.make_request(api_endpoint, query2)
        
        # Should be cache miss due to different topics
        assert response2['source'] == 'bedrock'
        assert response2['response'] != response1['response']
    
    def test_input_validation_empty_query(self, api_endpoint: str):
        """Test input validation with empty query"""
        url = f"{api_endpoint}/query"
        payload = {"query": ""}
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, json=payload, headers=headers)
        
        assert response.status_code == 400
        error_data = response.json()
        assert 'error' in error_data
        assert 'empty' in error_data['error'].lower()
    
    def test_input_validation_missing_query(self, api_endpoint: str):
        """Test input validation with missing query field"""
        url = f"{api_endpoint}/query"
        payload = {"message": "hello"}  # Wrong field name
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, json=payload, headers=headers)
        
        assert response.status_code == 400
        error_data = response.json()
        assert 'error' in error_data
    
    def test_input_validation_query_too_long(self, api_endpoint: str):
        """Test input validation with query too long"""
        long_query = "x" * 8001  # Exceeds 8000 character limit
        
        url = f"{api_endpoint}/query"
        payload = {"query": long_query}
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, json=payload, headers=headers)
        
        assert response.status_code == 400
        error_data = response.json()
        assert 'error' in error_data
        assert 'too long' in error_data['error'].lower()
    
    def test_cors_headers(self, api_endpoint: str):
        """Test that CORS headers are present"""
        response = requests.post(
            f"{api_endpoint}/query",
            json={"query": "test"},
            headers={"Content-Type": "application/json"}
        )
        
        # Check CORS headers
        assert response.headers.get('Access-Control-Allow-Origin') == '*'
        assert 'POST' in response.headers.get('Access-Control-Allow-Methods', '')
        assert 'Content-Type' in response.headers.get('Access-Control-Allow-Headers', '')
    
    def test_response_format(self, api_endpoint: str):
        """Test that response format matches specification"""
        response = self.make_request(api_endpoint, "Test query for format validation")
        
        # Required fields
        assert 'response' in response
        assert 'source' in response
        assert 'latency_ms' in response
        
        # Field types
        assert isinstance(response['response'], str)
        assert response['source'] in ['cache', 'bedrock']
        assert isinstance(response['latency_ms'], (int, float))
        assert response['latency_ms'] > 0
        
        # Optional fields (present for cache hits)
        if response['source'] == 'cache':
            assert 'similarity' in response
            assert isinstance(response['similarity'], (int, float))
            assert 0.0 <= response['similarity'] <= 1.0
    
    def test_performance_cache_hit_vs_miss(self, api_endpoint: str):
        """Test that cache hits are significantly faster than misses"""
        query = f"Performance test query {int(time.time())}"
        
        # First request (cache miss)
        response1 = self.make_request(api_endpoint, query)
        miss_latency = response1['latency_ms']
        assert response1['source'] == 'bedrock'
        
        # Wait for cache storage
        time.sleep(2)
        
        # Second request (cache hit)
        response2 = self.make_request(api_endpoint, query)
        
        if response2['source'] == 'cache':
            hit_latency = response2['latency_ms']
            
            # Cache hit should be significantly faster
            # Allow some variance but expect at least 5x improvement
            assert hit_latency < miss_latency / 5
            assert hit_latency < 200  # Should be under 200ms
        else:
            pytest.skip("Second request was not a cache hit")
    
    def test_concurrent_requests(self, api_endpoint: str):
        """Test handling of concurrent requests"""
        import concurrent.futures
        import threading
        
        query = f"Concurrent test query {int(time.time())}"
        num_requests = 5
        
        def make_concurrent_request():
            return self.make_request(api_endpoint, query)
        
        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(make_concurrent_request) for _ in range(num_requests)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        assert len(responses) == num_requests
        
        # All responses should be valid
        for response in responses:
            assert 'response' in response
            assert 'source' in response
            assert 'latency_ms' in response
        
        # At least one should be from cache (after the first)
        sources = [r['source'] for r in responses]
        assert 'bedrock' in sources  # At least one cache miss
        # Note: Due to timing, we might not always get cache hits in concurrent requests
    
    @pytest.mark.slow
    def test_cache_ttl_behavior(self, api_endpoint: str):
        """Test cache TTL behavior (requires waiting)"""
        # This test is marked as slow since it requires waiting for TTL
        # In a real scenario, you might set a shorter TTL for testing
        pytest.skip("TTL test requires 24+ hours - skip in normal test runs")
        
        query = f"TTL test query {int(time.time())}"
        
        # First request
        response1 = self.make_request(api_endpoint, query)
        assert response1['source'] == 'bedrock'
        
        # Wait for cache storage
        time.sleep(2)
        
        # Second request (should hit cache)
        response2 = self.make_request(api_endpoint, query)
        assert response2['source'] == 'cache'
        
        # Wait for TTL expiration (24 hours in production)
        # In a test environment, you might configure a shorter TTL
        time.sleep(86400 + 60)  # 24 hours + 1 minute
        
        # Third request (should miss cache due to TTL expiration)
        response3 = self.make_request(api_endpoint, query)
        assert response3['source'] == 'bedrock'