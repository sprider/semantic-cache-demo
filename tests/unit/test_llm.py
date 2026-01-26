"""
Unit tests for LLM module (Steps 5b, 6)
"""

import pytest
import json
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src/cache_orchestrator'))

from llm import LLMClient


class TestLLMClient:
    
    def setup_method(self):
        """Setup test fixtures"""
        self.client = LLMClient()
    
    @patch('llm.boto3.client')
    def test_init(self, mock_boto3_client):
        """Test LLMClient initialization"""
        client = LLMClient()
        
        assert client.model_id == 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
        assert client.max_retries == 3
        assert client.base_delay == 1.0
        assert client.max_tokens == 1024
        call_args = mock_boto3_client.call_args
        assert call_args[0][0] == 'bedrock-runtime'
        assert 'config' in call_args[1]
    
    @patch('llm.boto3.client')
    def test_invoke_llm_success(self, mock_boto3_client):
        """Test successful LLM invocation"""
        # Mock Bedrock response
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [
                {
                    'text': 'Paris is the capital of France.'
                }
            ]
        }).encode()
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.return_value = mock_response
        mock_boto3_client.return_value = mock_bedrock
        
        client = LLMClient()
        result = client.invoke_llm("What is the capital of France?")
        
        # Verify result
        assert result == 'Paris is the capital of France.'
        
        # Verify Bedrock call
        mock_bedrock.invoke_model.assert_called_once()
        call_args = mock_bedrock.invoke_model.call_args
        
        assert call_args[1]['modelId'] == 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
        assert call_args[1]['contentType'] == 'application/json'
        assert call_args[1]['accept'] == 'application/json'
        
        # Verify request body
        body = json.loads(call_args[1]['body'])
        assert body['anthropic_version'] == 'bedrock-2023-05-31'
        assert body['max_tokens'] == 1024
        assert body['messages'][0]['role'] == 'user'
        assert body['messages'][0]['content'] == 'What is the capital of France?'
        assert body['temperature'] == 0.1
    
    def test_invoke_llm_empty_query(self):
        """Test LLM invocation with empty query"""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            self.client.invoke_llm("")
        
        with pytest.raises(ValueError, match="Query cannot be empty"):
            self.client.invoke_llm("   ")
    
    @patch('llm.boto3.client')
    def test_invoke_llm_no_content(self, mock_boto3_client):
        """Test LLM invocation with no content in response"""
        # Mock Bedrock response with no content
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': []
        }).encode()
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.return_value = mock_response
        mock_boto3_client.return_value = mock_bedrock
        
        client = LLMClient()
        
        with pytest.raises(Exception, match="No content in LLM response"):
            client.invoke_llm("test")
    
    @patch('llm.bedrock_rate_limiter')
    @patch('llm.boto3.client')
    @patch('llm.random.uniform', return_value=0.0)
    @patch('llm.time.sleep')
    def test_invoke_llm_throttling_retry(self, mock_sleep, mock_random, mock_boto3_client, mock_rate_limiter):
        """Test LLM invocation with throttling and retry"""
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
            'content': [{'text': 'Success after retry'}]
        }).encode()
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = [throttling_error, mock_response]
        mock_boto3_client.return_value = mock_bedrock
        
        client = LLMClient()
        result = client.invoke_llm("test")
        
        # Verify retry logic
        assert result == 'Success after retry'
        assert mock_bedrock.invoke_model.call_count == 2
        # Sleep should be called at least once for retry (rate limiter may add more)
        assert mock_sleep.call_count >= 1
    
    @patch('llm.bedrock_rate_limiter')
    @patch('llm.boto3.client')
    @patch('llm.random.uniform', return_value=0.0)
    @patch('llm.time.sleep')
    def test_invoke_llm_throttling_max_retries(self, mock_sleep, mock_random, mock_boto3_client, mock_rate_limiter):
        """Test LLM invocation with max retries exceeded"""
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
        
        client = LLMClient()
        
        with pytest.raises(Exception, match="Bedrock throttling.*quota limits exceeded"):
            client.invoke_llm("test")
        
        # Verify all retries were attempted
        assert mock_bedrock.invoke_model.call_count == 3
        # Sleep should be called for retries (rate limiter may add more)
        assert mock_sleep.call_count >= 2  # At least 2 retry delays
    
    @patch('llm.boto3.client')
    def test_invoke_llm_access_denied(self, mock_boto3_client):
        """Test LLM invocation with access denied"""
        access_denied_error = ClientError(
            error_response={'Error': {'Code': 'AccessDeniedException'}},
            operation_name='InvokeModel'
        )
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = access_denied_error
        mock_boto3_client.return_value = mock_bedrock
        
        client = LLMClient()
        
        with pytest.raises(Exception, match="Access denied - enable Claude Haiku 4.5 in Bedrock Console"):
            client.invoke_llm("test")
    
    @patch('llm.boto3.client')
    def test_invoke_llm_validation_error(self, mock_boto3_client):
        """Test LLM invocation with validation error"""
        validation_error = ClientError(
            error_response={
                'Error': {
                    'Code': 'ValidationException',
                    'Message': 'Invalid request format'
                }
            },
            operation_name='InvokeModel'
        )
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = validation_error
        mock_boto3_client.return_value = mock_bedrock
        
        client = LLMClient()
        
        with pytest.raises(Exception, match="Invalid request: Invalid request format"):
            client.invoke_llm("test")
    
    @patch('llm.boto3.client')
    def test_invoke_llm_other_bedrock_error(self, mock_boto3_client):
        """Test LLM invocation with other Bedrock error"""
        other_error = ClientError(
            error_response={'Error': {'Code': 'ServiceUnavailableException'}},
            operation_name='InvokeModel'
        )
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = other_error
        mock_boto3_client.return_value = mock_bedrock
        
        client = LLMClient()
        
        with pytest.raises(Exception, match="Bedrock error: ServiceUnavailableException"):
            client.invoke_llm("test")
    
    @patch('llm.boto3.client')
    def test_invoke_llm_generic_exception(self, mock_boto3_client):
        """Test LLM invocation with generic exception"""
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = Exception("Network error")
        mock_boto3_client.return_value = mock_bedrock
        
        client = LLMClient()
        
        with pytest.raises(Exception, match="LLM invocation failed: Network error"):
            client.invoke_llm("test")
    
    @patch('llm.boto3.client')
    def test_invoke_llm_strips_whitespace(self, mock_boto3_client):
        """Test that LLM invocation strips whitespace from query"""
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Response'}]
        }).encode()
        
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.return_value = mock_response
        mock_boto3_client.return_value = mock_bedrock
        
        client = LLMClient()
        result = client.invoke_llm("  test query  ")
        
        # Verify whitespace was stripped in request
        call_args = mock_bedrock.invoke_model.call_args
        body = json.loads(call_args[1]['body'])
        assert body['messages'][0]['content'] == 'test query'