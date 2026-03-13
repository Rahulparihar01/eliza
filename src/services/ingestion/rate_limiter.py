"""
Rate Limiter for API Calls

Token bucket algorithm with thread-safe implementation.
Prevents exceeding API rate limits for external connectors.
"""
import time
from collections import deque
from threading import Lock
from typing import Optional

from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class RateLimiter:
    """
    Token bucket rate limiter for API calls.
    
    Thread-safe implementation that blocks requests when rate limit is exceeded.
    Automatically removes old requests outside the time window.
    
    Usage:
        limiter = RateLimiter(max_requests=60, time_window=60)
        limiter.acquire()  # Blocks if rate limit exceeded
        # Make API call here
    
    Example:
        # PDL API: 60 requests per minute
        pdl_limiter = RateLimiter(max_requests=60, time_window=60)
        
        for person_id in person_ids:
            pdl_limiter.acquire()  # Waits if needed
            response = api.get_person(person_id)
    """
    
    def __init__(self, max_requests: int, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds (default: 60 = 1 minute)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()  # Timestamps of requests
        self.lock = Lock()
        
        logger.info(
            "rate_limiter_initialized",
            max_requests=max_requests,
            time_window=time_window,
            requests_per_second=max_requests / time_window
        )
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make a request.
        
        Blocks until rate limit allows the request or timeout occurs.
        Automatically cleans up old request timestamps.
        
        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)
            
        Returns:
            True if acquired, False if timeout occurred
            
        Raises:
            No exceptions - blocks gracefully
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                now = time.time()
                
                # Remove requests outside time window (sliding window)
                while self.requests and self.requests[0] < now - self.time_window:
                    self.requests.popleft()
                
                # Check if we can make request
                if len(self.requests) < self.max_requests:
                    self.requests.append(now)
                    return True
                
                # Calculate how long to sleep
                oldest_request = self.requests[0]
                sleep_time = self.time_window - (now - oldest_request)
                
                # Check timeout
                if timeout and (time.time() - start_time) >= timeout:
                    logger.warning(
                        "rate_limiter_timeout",
                        timeout=timeout,
                        elapsed=time.time() - start_time
                    )
                    return False
                
                logger.debug(
                    "rate_limit_hit",
                    sleep_time=round(sleep_time, 2),
                    requests_in_window=len(self.requests),
                    utilization_percent=round((len(self.requests) / self.max_requests) * 100, 1)
                )
            
            # Sleep outside lock to allow other threads
            if sleep_time > 0:
                # Sleep in small increments for responsiveness
                time.sleep(min(sleep_time, 1.0))
            else:
                # Shouldn't happen, but safety check
                time.sleep(0.1)
    
    def try_acquire(self) -> bool:
        """
        Non-blocking attempt to acquire permission.
        
        Returns immediately without waiting.
        
        Returns:
            True if acquired, False if rate limit exceeded
        """
        with self.lock:
            now = time.time()
            
            # Remove old requests
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()
            
            # Check if we can make request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            
            return False
    
    def get_remaining_requests(self) -> int:
        """
        Get the number of remaining requests in the current time window.
        
        Returns:
            Number of requests that can be made without blocking
        """
        usage = self.get_current_usage()
        return usage["available_capacity"]
    
    def get_time_until_reset(self) -> float:
        """
        Get the time until the rate limit resets (oldest request expires).
        
        Returns:
            Time in seconds until capacity opens up
        """
        usage = self.get_current_usage()
        return usage["time_until_next_slot"]
    
    def get_current_usage(self) -> dict:
        """
        Get current rate limit usage statistics.
        
        Returns:
            Dict with usage metrics:
            {
                "requests_in_window": int,
                "max_requests": int,
                "utilization_percent": float,
                "available_capacity": int,
                "time_until_next_slot": float
            }
        """
        with self.lock:
            now = time.time()
            
            # Remove old requests
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()
            
            current_count = len(self.requests)
            available = self.max_requests - current_count
            utilization = (current_count / self.max_requests) * 100 if self.max_requests > 0 else 0
            
            # Calculate time until next slot opens
            time_until_next = 0.0
            if current_count >= self.max_requests and self.requests:
                oldest = self.requests[0]
                time_until_next = max(0, self.time_window - (now - oldest))
            
            return {
                "requests_in_window": current_count,
                "max_requests": self.max_requests,
                "utilization_percent": round(utilization, 1),
                "available_capacity": available,
                "time_until_next_slot": round(time_until_next, 2)
            }
    
    def reset(self):
        """
        Reset the rate limiter (clear all request history).
        
        Useful for testing or manual intervention.
        """
        with self.lock:
            self.requests.clear()
            logger.info("rate_limiter_reset", max_requests=self.max_requests)
    
    def __repr__(self):
        """String representation for debugging."""
        usage = self.get_current_usage()
        return (
            f"RateLimiter("
            f"max={self.max_requests}/{self.time_window}s, "
            f"current={usage['requests_in_window']}, "
            f"available={usage['available_capacity']})"
        )


class AdaptiveRateLimiter(RateLimiter):
    """
    Adaptive rate limiter that adjusts based on API responses.
    
    Automatically backs off when receiving rate limit errors (429).
    Gradually recovers to normal rate after successful requests.
    
    Usage:
        limiter = AdaptiveRateLimiter(max_requests=60, time_window=60)
        
        limiter.acquire()
        try:
            response = api.call()
            limiter.record_success()
        except RateLimitError:
            limiter.record_rate_limit_error()
            raise
    """
    
    def __init__(
        self,
        max_requests: int,
        time_window: int = 60,
        backoff_factor: float = 0.5,
        recovery_factor: float = 1.1,
        min_rate_percent: float = 10.0
    ):
        """
        Initialize adaptive rate limiter.
        
        Args:
            max_requests: Maximum requests under normal conditions
            time_window: Time window in seconds
            backoff_factor: Multiply rate by this on error (e.g., 0.5 = half rate)
            recovery_factor: Multiply rate by this on success (e.g., 1.1 = 10% increase)
            min_rate_percent: Minimum rate as % of max (safety floor)
        """
        super().__init__(max_requests, time_window)
        
        self.base_max_requests = max_requests
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.min_requests = max(1, int(max_requests * min_rate_percent / 100))
        
        self.consecutive_successes = 0
        self.consecutive_errors = 0
        
        logger.info(
            "adaptive_rate_limiter_initialized",
            base_max_requests=max_requests,
            backoff_factor=backoff_factor,
            recovery_factor=recovery_factor
        )
    
    def record_rate_limit_error(self):
        """
        Record that we hit the API's rate limit.
        
        Reduces our max_requests to avoid future 429 errors.
        """
        with self.lock:
            self.consecutive_errors += 1
            self.consecutive_successes = 0
            
            # Reduce rate
            new_max = max(
                self.min_requests,
                int(self.max_requests * self.backoff_factor)
            )
            
            if new_max != self.max_requests:
                logger.warning(
                    "rate_limiter_backing_off",
                    old_max=self.max_requests,
                    new_max=new_max,
                    consecutive_errors=self.consecutive_errors
                )
                self.max_requests = new_max
    
    def record_success(self):
        """
        Record a successful API call.
        
        After sustained success, gradually increases rate back toward base max.
        """
        with self.lock:
            self.consecutive_successes += 1
            self.consecutive_errors = 0
            
            # After 10 successful calls, try increasing rate
            if self.consecutive_successes >= 10 and self.max_requests < self.base_max_requests:
                new_max = min(
                    self.base_max_requests,
                    int(self.max_requests * self.recovery_factor)
                )
                
                if new_max != self.max_requests:
                    logger.info(
                        "rate_limiter_recovering",
                        old_max=self.max_requests,
                        new_max=new_max,
                        consecutive_successes=self.consecutive_successes
                    )
                    self.max_requests = new_max
                    self.consecutive_successes = 0

