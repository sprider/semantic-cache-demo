"""
Unit tests for metrics module (Observability)
"""

import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src/cache_orchestrator'))

from metrics import MetricsClient


class TestMetricsClient:
    
    def setup_method(self):
        """Setup test fixtures"""
        self.client = MetricsClient()
    
    @patch('metrics.boto3.client')
    def test_init(self, mock_boto3_client):
        """Test MetricsClient initialization"""
        client = MetricsClient()
        
        assert client.namespace == 'SemanticCache'
        mock_boto3_client.assert_called_once_with('cloudwatch')
    
    @patch('metrics.boto3.client')
    def test_publish_metrics_cache_hit(self, mock_boto3_client):
        """Test publishing metrics for cache hit"""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        client = MetricsClient()
        client.publish_metrics(cache_hit=True, latency_ms=50.5)
        
        # Verify CloudWatch call
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        assert call_args[1]['Namespace'] == 'SemanticCache'
        
        metric_data = call_args[1]['MetricData']
        assert len(metric_data) == 3  # CacheHit, Latency, CacheHitLatency
        
        # Check CacheHit metric
        cache_hit_metric = next(m for m in metric_data if m['MetricName'] == 'CacheHit')
        assert cache_hit_metric['Value'] == 1.0
        assert cache_hit_metric['Unit'] == 'Count'
        
        # Check Latency metric
        latency_metric = next(m for m in metric_data if m['MetricName'] == 'Latency')
        assert latency_metric['Value'] == 50.5
        assert latency_metric['Unit'] == 'Milliseconds'
        
        # Check CacheHitLatency metric
        hit_latency_metric = next(m for m in metric_data if m['MetricName'] == 'CacheHitLatency')
        assert hit_latency_metric['Value'] == 50.5
        assert hit_latency_metric['Unit'] == 'Milliseconds'
    
    @patch('metrics.boto3.client')
    def test_publish_metrics_cache_miss(self, mock_boto3_client):
        """Test publishing metrics for cache miss"""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        client = MetricsClient()
        client.publish_metrics(cache_hit=False, latency_ms=1200.7)
        
        # Verify CloudWatch call
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData']
        assert len(metric_data) == 3  # CacheHit, Latency, CacheMissLatency
        
        # Check CacheHit metric
        cache_hit_metric = next(m for m in metric_data if m['MetricName'] == 'CacheHit')
        assert cache_hit_metric['Value'] == 0.0
        assert cache_hit_metric['Unit'] == 'Count'
        
        # Check CacheMissLatency metric
        miss_latency_metric = next(m for m in metric_data if m['MetricName'] == 'CacheMissLatency')
        assert miss_latency_metric['Value'] == 1200.7
        assert miss_latency_metric['Unit'] == 'Milliseconds'
    
    @patch('metrics.boto3.client')
    def test_publish_metrics_client_error(self, mock_boto3_client):
        """Test publishing metrics with CloudWatch client error"""
        mock_cloudwatch = Mock()
        mock_cloudwatch.put_metric_data.side_effect = ClientError(
            error_response={'Error': {'Code': 'AccessDenied'}},
            operation_name='PutMetricData'
        )
        mock_boto3_client.return_value = mock_cloudwatch
        
        client = MetricsClient()
        
        # Should not raise exception (metrics are non-critical)
        client.publish_metrics(cache_hit=True, latency_ms=100.0)
        
        # Verify CloudWatch was called despite error
        mock_cloudwatch.put_metric_data.assert_called_once()
    
    @patch('metrics.boto3.client')
    def test_publish_metrics_generic_exception(self, mock_boto3_client):
        """Test publishing metrics with generic exception"""
        mock_cloudwatch = Mock()
        mock_cloudwatch.put_metric_data.side_effect = Exception("Network error")
        mock_boto3_client.return_value = mock_cloudwatch
        
        client = MetricsClient()
        
        # Should not raise exception (metrics are non-critical)
        client.publish_metrics(cache_hit=True, latency_ms=100.0)
        
        # Verify CloudWatch was called despite error
        mock_cloudwatch.put_metric_data.assert_called_once()
    
    @patch('metrics.boto3.client')
    def test_publish_error_metric_validation_error(self, mock_boto3_client):
        """Test publishing validation error metric"""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        client = MetricsClient()
        client.publish_error_metric('ValidationError')
        
        # Verify CloudWatch call
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        metric_data = call_args[1]['MetricData']
        assert len(metric_data) == 2  # Errors, ClientErrors
        
        # Check Errors metric with dimension
        errors_metric = next(m for m in metric_data if m['MetricName'] == 'Errors')
        assert errors_metric['Value'] == 1.0
        assert errors_metric['Unit'] == 'Count'
        assert errors_metric['Dimensions'][0]['Name'] == 'ErrorType'
        assert errors_metric['Dimensions'][0]['Value'] == 'ValidationError'
        
        # Check ClientErrors metric
        client_errors_metric = next(m for m in metric_data if m['MetricName'] == 'ClientErrors')
        assert client_errors_metric['Value'] == 1.0
        assert client_errors_metric['Unit'] == 'Count'
    
    @patch('metrics.boto3.client')
    def test_publish_error_metric_embedding_error(self, mock_boto3_client):
        """Test publishing embedding error metric"""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        client = MetricsClient()
        client.publish_error_metric('EmbeddingError')
        
        # Verify CloudWatch call
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData']
        
        # Check BedrockErrors metric
        bedrock_errors_metric = next(m for m in metric_data if m['MetricName'] == 'BedrockErrors')
        assert bedrock_errors_metric['Value'] == 1.0
    
    @patch('metrics.boto3.client')
    def test_publish_error_metric_llm_error(self, mock_boto3_client):
        """Test publishing LLM error metric"""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        client = MetricsClient()
        client.publish_error_metric('LLMError')
        
        # Verify CloudWatch call
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData']
        
        # Check BedrockErrors metric
        bedrock_errors_metric = next(m for m in metric_data if m['MetricName'] == 'BedrockErrors')
        assert bedrock_errors_metric['Value'] == 1.0
    
    @patch('metrics.boto3.client')
    def test_publish_error_metric_cache_error(self, mock_boto3_client):
        """Test publishing cache error metric"""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        client = MetricsClient()
        client.publish_error_metric('CacheError')
        
        # Verify CloudWatch call
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData']
        
        # Check CacheErrors metric
        cache_errors_metric = next(m for m in metric_data if m['MetricName'] == 'CacheErrors')
        assert cache_errors_metric['Value'] == 1.0
    
    @patch('metrics.boto3.client')
    def test_publish_error_metric_unknown_error(self, mock_boto3_client):
        """Test publishing unknown error metric"""
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        client = MetricsClient()
        client.publish_error_metric('UnknownError')
        
        # Verify CloudWatch call
        call_args = mock_cloudwatch.put_metric_data.call_args
        metric_data = call_args[1]['MetricData']
        
        # Check SystemErrors metric
        system_errors_metric = next(m for m in metric_data if m['MetricName'] == 'SystemErrors')
        assert system_errors_metric['Value'] == 1.0
    
    @patch('metrics.boto3.client')
    def test_publish_error_metric_exception_handling(self, mock_boto3_client):
        """Test error metric publishing with exception"""
        mock_cloudwatch = Mock()
        mock_cloudwatch.put_metric_data.side_effect = Exception("CloudWatch error")
        mock_boto3_client.return_value = mock_cloudwatch
        
        client = MetricsClient()
        
        # Should not raise exception (metrics are non-critical)
        client.publish_error_metric('TestError')
        
        # Verify CloudWatch was called despite error
        mock_cloudwatch.put_metric_data.assert_called_once()