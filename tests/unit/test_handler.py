"""
Unit tests for main handler (Steps 2-7)
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src/cache_orchestrator'))

from handler import lambda_handler, parse_request, create_response


class TestHandler:
    
    def test_parse_request_api_gateway_format(self):
        """Test parsing API Gateway format request"""
        event = {
            'body': json.dumps({'query': 'What is the capital of France?'})
        }
        
        result = parse_request(event)
        assert result == 'What is the capital of France?'
    
    def test_parse_request_direct_invocation_format(self):
        """Test parsing direct invocation format request"""
        event = {
            'query': 'What is the capital of France?'
        }
        
        result = parse_request(event)
        assert result == 'What is the capital of France?'
    
    def test_parse_request_empty_body(self):
        """Test parsing request with empty body"""
        event = {'body': ''}
        
        with pytest.raises(ValueError, match="Empty request body"):
            parse_request(event)
    
    def test_parse_request_invalid_json(self):
        """Test parsing request with invalid JSON"""
        event = {'body': 'invalid json'}
        
        with pytest.raises(ValueError, match="Invalid JSON in request body"):
            parse_request(event)
    
    def test_parse_request_missing_query(self):
        """Test parsing request with missing query field"""
        event = {'body': json.dumps({'message': 'hello'})}
        
        with pytest.raises(ValueError, match="Query cannot be empty"):
            parse_request(event)
    
    def test_parse_request_empty_query(self):
        """Test parsing request with empty query"""
        event = {'body': json.dumps({'query': ''})}
        
        with pytest.raises(ValueError, match="Query cannot be empty"):
            parse_request(event)
    
    def test_parse_request_query_too_long(self):
        """Test parsing request with query too long"""
        long_query = 'x' * 8001
        event = {'body': json.dumps({'query': long_query})}
        
        with pytest.raises(ValueError, match="Query too long"):
            parse_request(event)
    
    def test_parse_request_no_query_found(self):
        """Test parsing request with no query found"""
        event = {'other_field': 'value'}
        
        with pytest.raises(ValueError, match="No query found in request"):
            parse_request(event)
    
    def test_create_response(self):
        """Test creating API Gateway response"""
        body = {'message': 'success'}
        result = create_response(200, body)
        
        expected = {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps(body)
        }
        
        assert result == expected
    
    @patch('handler.init_clients')
    @patch('handler.parse_request')
    @patch('handler.embedding_client')
    @patch('handler.cache_client')
    @patch('handler.metrics_client')
    def test_lambda_handler_cache_hit(self, mock_metrics, mock_cache, mock_embedding, mock_parse, mock_init):
        """Test lambda handler with cache hit (Step 5a)"""
        # Setup mocks
        mock_parse.return_value = "What is the capital of France?"
        mock_embedding.generate_embedding.return_value = [0.1] * 1024
        mock_cache.search_cache.return_value = {
            'response': 'Paris is the capital of France.',
            'similarity': 0.95
        }
        
        # Mock context
        context = Mock()
        context.aws_request_id = 'test-request-123'
        
        # Test event
        event = {'body': json.dumps({'query': 'What is the capital of France?'})}
        
        result = lambda_handler(event, context)
        
        # Verify response
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['response'] == 'Paris is the capital of France.'
        assert body['source'] == 'cache'
        assert body['similarity'] == 0.95
        assert 'latency_ms' in body
        
        # Verify metrics were published
        mock_metrics.publish_metrics.assert_called_once()
        call_args = mock_metrics.publish_metrics.call_args
        assert call_args[1]['cache_hit'] is True
    
    @patch('handler.init_clients')
    @patch('handler.parse_request')
    @patch('handler.embedding_client')
    @patch('handler.cache_client')
    @patch('handler.llm_client')
    @patch('handler.metrics_client')
    def test_lambda_handler_cache_miss(self, mock_metrics, mock_llm, mock_cache, mock_embedding, mock_parse, mock_init):
        """Test lambda handler with cache miss (Steps 5b-6-7)"""
        # Setup mocks
        mock_parse.return_value = "What is machine learning?"
        mock_embedding.generate_embedding.return_value = [0.2] * 1024
        mock_cache.search_cache.return_value = None  # Cache miss
        mock_llm.invoke_llm.return_value = "Machine learning is a subset of AI."
        
        # Mock context
        context = Mock()
        context.aws_request_id = 'test-request-456'
        
        # Test event
        event = {'body': json.dumps({'query': 'What is machine learning?'})}
        
        result = lambda_handler(event, context)
        
        # Verify response
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['response'] == 'Machine learning is a subset of AI.'
        assert body['source'] == 'bedrock'
        assert 'latency_ms' in body
        assert 'similarity' not in body  # No similarity for cache miss
        
        # Verify LLM was called
        mock_llm.invoke_llm.assert_called_once_with("What is machine learning?")
        
        # Verify cache storage was attempted
        mock_cache.store_in_cache.assert_called_once()
        
        # Verify metrics were published
        mock_metrics.publish_metrics.assert_called_once()
        call_args = mock_metrics.publish_metrics.call_args
        assert call_args[1]['cache_hit'] is False
    
    @patch('handler.init_clients')
    @patch('handler.parse_request')
    @patch('handler.metrics_client')
    def test_lambda_handler_validation_error(self, mock_metrics, mock_parse, mock_init):
        """Test lambda handler with validation error"""
        # Setup mock to raise validation error
        mock_parse.side_effect = ValueError("Query cannot be empty")
        
        # Mock context
        context = Mock()
        context.aws_request_id = 'test-request-error'
        
        # Test event
        event = {'body': ''}
        
        result = lambda_handler(event, context)
        
        # Verify error response
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert body['error'] == 'Query cannot be empty'
        
        # Verify error metric was published
        mock_metrics.publish_error_metric.assert_called_once_with('ValidationError')
    
    @patch('handler.init_clients')
    @patch('handler.parse_request')
    @patch('handler.embedding_client')
    @patch('handler.metrics_client')
    def test_lambda_handler_server_error(self, mock_metrics, mock_embedding, mock_parse, mock_init):
        """Test lambda handler with server error"""
        # Setup mocks
        mock_parse.return_value = "test query"
        mock_embedding.generate_embedding.side_effect = Exception("Bedrock error")
        
        # Mock context
        context = Mock()
        context.aws_request_id = 'test-request-error'
        
        # Test event
        event = {'body': json.dumps({'query': 'test query'})}
        
        result = lambda_handler(event, context)
        
        # Verify error response
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert body['error'] == 'Internal server error'
        assert body['message'] == 'Bedrock error'
        
        # Verify error metric was published with correct type
        mock_metrics.publish_error_metric.assert_called_once_with('LLMError')
    
    @patch('handler.init_clients')
    @patch('handler.parse_request')
    @patch('handler.embedding_client')
    @patch('handler.metrics_client')
    def test_lambda_handler_embedding_error_classification(self, mock_metrics, mock_embedding, mock_parse, mock_init):
        """Test lambda handler error classification for embedding errors"""
        # Setup mocks
        mock_parse.return_value = "test query"
        mock_embedding.generate_embedding.side_effect = Exception("embedding generation failed")
        
        # Mock context
        context = Mock()
        context.aws_request_id = 'test-request-error'
        
        # Test event
        event = {'body': json.dumps({'query': 'test query'})}
        
        result = lambda_handler(event, context)
        
        # Verify error classification
        mock_metrics.publish_error_metric.assert_called_once_with('EmbeddingError')
    
    @patch('handler.init_clients')
    @patch('handler.parse_request')
    @patch('handler.embedding_client')
    @patch('handler.cache_client')
    @patch('handler.llm_client')
    @patch('handler.metrics_client')
    def test_lambda_handler_cache_storage_failure_non_critical(self, mock_metrics, mock_llm, mock_cache, mock_embedding, mock_parse, mock_init):
        """Test that cache storage failure doesn't fail the request"""
        # Setup mocks
        mock_parse.return_value = "test query"
        mock_embedding.generate_embedding.return_value = [0.1] * 1024
        mock_cache.search_cache.return_value = None  # Cache miss
        mock_llm.invoke_llm.return_value = "Test response"
        mock_cache.store_in_cache.side_effect = Exception("Cache storage failed")
        
        # Mock context
        context = Mock()
        context.aws_request_id = 'test-request'
        
        # Test event
        event = {'body': json.dumps({'query': 'test query'})}
        
        result = lambda_handler(event, context)
        
        # Verify request still succeeds despite cache storage failure
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['response'] == 'Test response'
        assert body['source'] == 'bedrock'
    
    @patch('handler.embedding_client', None)
    @patch('handler.cache_client', None)
    @patch('handler.llm_client', None)
    @patch('handler.metrics_client', None)
    def test_init_clients(self):
        """Test client initialization"""
        with patch('handler.EmbeddingClient') as mock_embedding_cls, \
             patch('handler.CacheClient') as mock_cache_cls, \
             patch('handler.LLMClient') as mock_llm_cls, \
             patch('handler.MetricsClient') as mock_metrics_cls:
            
            from handler import init_clients
            init_clients()
            
            # Verify all clients were initialized
            mock_embedding_cls.assert_called_once()
            mock_cache_cls.assert_called_once()
            mock_llm_cls.assert_called_once()
            mock_metrics_cls.assert_called_once()