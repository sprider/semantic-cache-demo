"""
Unit tests for embedding module (Step 3)
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src/cache_orchestrator'))

from embedding import EmbeddingClient


class TestEmbeddingClient:
    
    def setup_method(self):
        """Setup test fixtures"""
        self.client = EmbeddingClient()
    
    @patch('embedding.boto3.client')
    def test_init(self, mock_boto3_client):
        """Test EmbeddingClient initialization"""
        client = EmbeddingClient()
        
        assert client.model_id == 'amazon.titan-embed-text-v2:0'
        assert client.max_retries == 3
        assert client.base_delay == 1.0
        call_args = mock_boto3_client.call_args
        assert call_args[0][0] == 'bedrock-runtime'
        assert 'config' in call_args[1]
    
    @patch('embedding.boto3.client')
    def test_generate_embedding_success(self, mock_boto3_client):
        """Test successful embedding generation"""
        # Mock Bedrock response
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'embedding': [0.1] * 1024  # 1024-dimensional embedding
        }).encode()
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.return_value = mock_response
        mock_boto3_client.return_value = mock_bedrock
        
        client = EmbeddingClient()
        result = client.generate_embedding("What is the capital of France?")
        
        # Verify result
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)
        
        # Verify Bedrock call
        mock_bedrock.invoke_model.assert_called_once()
        call_args = mock_bedrock.invoke_model.call_args
        
        assert call_args[1]['modelId'] == 'amazon.titan-embed-text-v2:0'
        assert call_args[1]['contentType'] == 'application/json'
        assert call_args[1]['accept'] == 'application/json'
        
        # Verify request body
        body = json.loads(call_args[1]['body'])
        assert body['inputText'] == "What is the capital of France?"
        assert body['normalize'] is True
        assert body['dimensions'] == 1024
    
    def test_generate_embedding_empty_text(self):
        """Test embedding generation with empty text"""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            self.client.generate_embedding("")
        
        with pytest.raises(ValueError, match="Text cannot be empty"):
            self.client.generate_embedding("   ")
    
    def test_generate_embedding_text_too_long(self):
        """Test embedding generation with text too long"""
        long_text = "x" * 8001
        
        with pytest.raises(ValueError, match="Text too long"):
            self.client.generate_embedding(long_text)
    
    @patch('embedding.boto3.client')
    def test_generate_embedding_wrong_dimensions(self, mock_boto3_client):
        """Test embedding generation with wrong dimensions"""
        # Mock Bedrock response with wrong dimensions
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'embedding': [0.1] * 512  # Wrong dimensions
        }).encode()
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.return_value = mock_response
        mock_boto3_client.return_value = mock_bedrock
        
        client = EmbeddingClient()
        
        with pytest.raises(Exception, match="Embedding generation failed: Expected 1024 dimensions, got 512"):
            client.generate_embedding("test")
    
    @patch('embedding.bedrock_rate_limiter')
    @patch('embedding.boto3.client')
    @patch('embedding.random.uniform', return_value=0.0)
    @patch('embedding.time.sleep')
    def test_generate_embedding_throttling_retry(self, mock_sleep, mock_random, mock_boto3_client, mock_rate_limiter):
        """Test embedding generation with throttling and retry"""
        # Mock rate limiter context manager
        mock_rate_limiter.acquire_bedrock_call_lock.return_value.__enter__ = Mock()
        mock_rate_limiter.acquire_bedrock_call_lock.return_value.__exit__ = Mock(return_value=None)
        
        # Mock throttling error then success
        throttling_error = ClientError(
            error_response={'Error': {'Code': 'ThrottlingException'}},
            operation_name='InvokeModel'
        )
        
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'embedding': [0.1] * 1024
        }).encode()
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = [throttling_error, mock_response]
        mock_boto3_client.return_value = mock_bedrock
        
        client = EmbeddingClient()
        result = client.generate_embedding("test")
        
        # Verify retry logic
        assert len(result) == 1024
        assert mock_bedrock.invoke_model.call_count == 2
        # Sleep should be called at least once for retry (rate limiter may add more)
        assert mock_sleep.call_count >= 1
    
    @patch('embedding.bedrock_rate_limiter')
    @patch('embedding.boto3.client')
    @patch('embedding.random.uniform', return_value=0.0)
    @patch('embedding.time.sleep')
    def test_generate_embedding_throttling_max_retries(self, mock_sleep, mock_random, mock_boto3_client, mock_rate_limiter):
        """Test embedding generation with max retries exceeded"""
        # Mock rate limiter context manager
        mock_rate_limiter.acquire_bedrock_call_lock.return_value.__enter__ = Mock()
        mock_rate_limiter.acquire_bedrock_call_lock.return_value.__exit__ = Mock(return_value=None)
        
        # Mock throttling error for all retries
        throttling_error = ClientError(
            error_response={'Error': {'Code': 'ThrottlingException'}},
            operation_name='InvokeModel'
        )
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = throttling_error
        mock_boto3_client.return_value = mock_bedrock
        
        client = EmbeddingClient()
        
        with pytest.raises(Exception, match="Bedrock throttling.*quota limits exceeded"):
            client.generate_embedding("test")
        
        # Verify all retries were attempted
        assert mock_bedrock.invoke_model.call_count == 3
        # Sleep should be called for retries (rate limiter may add more)
        assert mock_sleep.call_count >= 2  # At least 2 retry delays
    
    @patch('embedding.boto3.client')
    def test_generate_embedding_access_denied(self, mock_boto3_client):
        """Test embedding generation with access denied"""
        access_denied_error = ClientError(
            error_response={'Error': {'Code': 'AccessDeniedException'}},
            operation_name='InvokeModel'
        )
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = access_denied_error
        mock_boto3_client.return_value = mock_bedrock
        
        client = EmbeddingClient()
        
        with pytest.raises(Exception, match="Access denied - enable Titan Embeddings V2 in Bedrock Console"):
            client.generate_embedding("test")
    
    @patch('embedding.boto3.client')
    def test_generate_embedding_other_bedrock_error(self, mock_boto3_client):
        """Test embedding generation with other Bedrock error"""
        other_error = ClientError(
            error_response={'Error': {'Code': 'ValidationException'}},
            operation_name='InvokeModel'
        )
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = other_error
        mock_boto3_client.return_value = mock_bedrock
        
        client = EmbeddingClient()
        
        with pytest.raises(Exception, match="Bedrock error: ValidationException"):
            client.generate_embedding("test")
    
    @patch('embedding.boto3.client')
    def test_generate_embedding_generic_exception(self, mock_boto3_client):
        """Test embedding generation with generic exception"""
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = Exception("Network error")
        mock_boto3_client.return_value = mock_bedrock
        
        client = EmbeddingClient()
        
        with pytest.raises(Exception, match="Embedding generation failed: Network error"):
            client.generate_embedding("test")