"""
Enhanced rate limiter for Bedrock API calls to prevent quota exhaustion
Implements file-based locking with request distribution across time periods
Based on AWS troubleshooting guide for Bedrock throttling at low concurrency
"""

import time
import os
import fcntl
import logging
import random
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class BedrockRateLimiter:
    """
    Enhanced rate limiter that ensures serialized Bedrock API calls
    Uses file locking to coordinate across Lambda instances
    Distributes requests across time periods to prevent burst throttling
    """
    
    def __init__(self, min_interval: float = 2.0, max_jitter: float = 1.0):
        """
        Initialize enhanced rate limiter
        
        Args:
            min_interval: Minimum seconds between Bedrock API calls (increased to 2s)
            max_jitter: Maximum random jitter to add for request distribution
        """
        self.min_interval = min_interval
        self.max_jitter = max_jitter
        self.lock_file_path = '/tmp/bedrock_rate_limit.lock'
        self.last_call_file = '/tmp/bedrock_last_call.txt'
        self.call_count_file = '/tmp/bedrock_call_count.txt'
    
    @contextmanager
    def acquire_bedrock_call_lock(self):
        """
        Enhanced context manager that ensures serialized Bedrock API calls
        with request distribution across time periods
        
        Usage:
            with rate_limiter.acquire_bedrock_call_lock():
                # Make Bedrock API call here
                response = bedrock_client.invoke_model(...)
        """
        lock_file = None
        try:
            # Create lock file
            lock_file = open(self.lock_file_path, 'w')
            
            # Acquire exclusive lock (blocks until available)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            
            # Get current minute and call count for request distribution
            current_time = time.time()
            current_minute = int(current_time // 60)
            
            # Check time since last call and implement request distribution
            last_call_time = self._get_last_call_time()
            call_count_this_minute = self._get_call_count_for_minute(current_minute)
            
            if last_call_time is not None:
                time_since_last = current_time - last_call_time
                
                # Calculate dynamic interval based on calls this minute
                # Distribute requests across the 60-second period
                dynamic_interval = self.min_interval
                if call_count_this_minute > 0:
                    # Spread remaining calls across remaining time in minute
                    remaining_seconds = 60 - (current_time % 60)
                    if remaining_seconds > 0:
                        dynamic_interval = max(self.min_interval, remaining_seconds / (10 - call_count_this_minute))
                
                if time_since_last < dynamic_interval:
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0, self.max_jitter)
                    sleep_time = dynamic_interval - time_since_last + jitter
                    
                    logger.info(f"Rate limiting: sleeping {sleep_time:.2f}s (interval: {dynamic_interval:.2f}s, "
                              f"calls this minute: {call_count_this_minute}, jitter: {jitter:.2f}s)")
                    time.sleep(sleep_time)
            
            # Update counters
            self._update_last_call_time()
            self._increment_call_count(current_minute)
            
            yield
            
        finally:
            if lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                except:
                    pass
    
    def _get_last_call_time(self) -> float:
        """Get timestamp of last Bedrock API call"""
        try:
            if os.path.exists(self.last_call_file):
                with open(self.last_call_file, 'r') as f:
                    return float(f.read().strip())
        except:
            pass
        return None
    
    def _update_last_call_time(self):
        """Update timestamp of last Bedrock API call"""
        try:
            with open(self.last_call_file, 'w') as f:
                f.write(str(time.time()))
        except:
            pass
    
    def _get_call_count_for_minute(self, minute: int) -> int:
        """Get number of calls made in the specified minute"""
        try:
            if os.path.exists(self.call_count_file):
                with open(self.call_count_file, 'r') as f:
                    data = f.read().strip()
                    if data:
                        stored_minute, count = data.split(',')
                        if int(stored_minute) == minute:
                            return int(count)
        except:
            pass
        return 0
    
    def _increment_call_count(self, minute: int):
        """Increment call count for the specified minute"""
        try:
            current_count = self._get_call_count_for_minute(minute)
            with open(self.call_count_file, 'w') as f:
                f.write(f"{minute},{current_count + 1}")
        except:
            pass

# Global rate limiter instance with enhanced settings
bedrock_rate_limiter = BedrockRateLimiter(min_interval=2.0, max_jitter=1.0)  # 2 seconds + jitter