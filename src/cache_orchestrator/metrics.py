"""
Metrics module for Semantic Cache Demo
Handles Observability: CloudWatch metrics publishing
"""

import logging
from typing import Dict, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class MetricsClient:
    """Client for CloudWatch metrics publishing"""
    
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
        self.namespace = 'SemanticCache'
    
    def publish_metrics(self, cache_hit: bool, latency_ms: float) -> None:
        """
        Publish cache hit and latency metrics to CloudWatch
        
        Args:
            cache_hit: True if cache hit (Step 5a), False if cache miss (Step 5b)
            latency_ms: Total request latency in milliseconds
        """
        try:
            # Prepare metrics data
            metric_data = [
                {
                    'MetricName': 'CacheHit',
                    'Value': 1.0 if cache_hit else 0.0,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'Latency',
                    'Value': latency_ms,
                    'Unit': 'Milliseconds'
                }
            ]
            
            # Add cache-specific latency metrics
            if cache_hit:
                metric_data.append({
                    'MetricName': 'CacheHitLatency',
                    'Value': latency_ms,
                    'Unit': 'Milliseconds'
                })
            else:
                metric_data.append({
                    'MetricName': 'CacheMissLatency',
                    'Value': latency_ms,
                    'Unit': 'Milliseconds'
                })
            
            # Publish to CloudWatch
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
            
            logger.info(f"Published metrics: cache_hit={cache_hit}, latency={latency_ms:.1f}ms")
            
        except ClientError as e:
            # Metrics are non-critical - log error but don't fail
            logger.warning(f"Failed to publish metrics: {e.response['Error']['Code']}")
        except Exception as e:
            # Metrics are non-critical - log error but don't fail
            logger.warning(f"Failed to publish metrics: {str(e)}")
    
    def publish_error_metric(self, error_type: str) -> None:
        """
        Publish error metrics to CloudWatch with detailed categorization
        
        Args:
            error_type: Type of error (ValidationError, EmbeddingError, LLMError, CacheError, UnknownError)
        """
        try:
            metric_data = [
                {
                    'MetricName': 'Errors',
                    'Value': 1.0,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'ErrorType',
                            'Value': error_type
                        }
                    ]
                }
            ]
            
            # Add specific error category metrics for better monitoring
            if error_type == 'ValidationError':
                metric_data.append({
                    'MetricName': 'ClientErrors',
                    'Value': 1.0,
                    'Unit': 'Count'
                })
            elif error_type in ['EmbeddingError', 'LLMError']:
                metric_data.append({
                    'MetricName': 'BedrockErrors',
                    'Value': 1.0,
                    'Unit': 'Count'
                })
            elif error_type == 'CacheError':
                metric_data.append({
                    'MetricName': 'CacheErrors',
                    'Value': 1.0,
                    'Unit': 'Count'
                })
            else:
                metric_data.append({
                    'MetricName': 'SystemErrors',
                    'Value': 1.0,
                    'Unit': 'Count'
                })
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
            
            logger.info(f"Published error metrics: {error_type}")
            
        except Exception as e:
            # Metrics are non-critical - log error but don't fail
            logger.warning(f"Failed to publish error metric: {str(e)}")