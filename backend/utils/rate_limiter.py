"""
Trading Maven - Rate Limiter Utility
Controls API request frequency to respect broker rate limits
"""
import time
import asyncio
import threading
import logging
from functools import wraps
from typing import List, Callable, Any

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Synchronous rate limiter for thread-based operations
    Ensures we don't exceed broker's rate limits (e.g., 10 symbols per second)
    """
    
    def __init__(self, max_calls: int = 10, period: float = 1.0):
        """
        Initialize rate limiter
        
        Args:
            max_calls: Maximum number of calls allowed in the period
            period: Time period in seconds (default: 1 second)
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = []
        self.lock = threading.Lock()
    
    def __call__(self, func):
        """Decorator to rate limit function calls"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.wait_if_needed()
            return func(*args, **kwargs)
        return wrapper
    
    def wait_if_needed(self):
        """Wait if rate limit is reached"""
        with self.lock:
            now = time.time()
            # Clean up old calls
            self.calls = [t for t in self.calls if t > now - self.period]
            
            # Check if we've reached the limit
            if len(self.calls) >= self.max_calls:
                sleep_time = self.calls[0] + self.period - now
                if sleep_time > 0:
                    logger.info(f"Rate limit reached. Waiting {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                    # Clean up again after waiting
                    now = time.time()
                    self.calls = [t for t in self.calls if t > now - self.period]
            
            # Add current call time
            self.calls.append(now)


class AsyncRateLimiter:
    """
    Async rate limiter for asyncio-based operations
    """
    
    def __init__(self, calls_per_second: int = 3):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call_time = 0
        self._lock = asyncio.Lock()
    
    async def wait(self):
        """Wait if necessary to respect rate limit"""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_call_time
            
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.3f}s")
                await asyncio.sleep(wait_time)
            
            self.last_call_time = time.time()
    
    def __call__(self, func):
        """Decorator for async functions"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await self.wait()
            return await func(*args, **kwargs)
        return wrapper


def batch_process(
    items: List[Any],
    batch_size: int,
    process_func: Callable,
    delay_between_batches: float = 1.0,
    *args, **kwargs
) -> List[Any]:
    """
    Process items in batches to respect rate limits (synchronous)
    
    Args:
        items: List of items to process
        batch_size: Number of items per batch
        process_func: Function to process each batch
        delay_between_batches: Seconds to wait between batches
        *args, **kwargs: Additional arguments for process_func
    
    Returns:
        Combined results from all batches
    """
    results = []
    total_batches = (len(items) + batch_size - 1) // batch_size
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} items)")
        
        batch_results = process_func(batch, *args, **kwargs)
        if batch_results:
            results.extend(batch_results)
        
        # Wait between batches (except for last batch)
        if i + batch_size < len(items):
            logger.debug(f"Waiting {delay_between_batches}s before next batch")
            time.sleep(delay_between_batches)
    
    return results


async def async_batch_process(
    items: List[Any],
    batch_size: int,
    process_func: Callable,
    delay_between_batches: float = 1.0,
    *args, **kwargs
) -> List[Any]:
    """
    Process items in batches to respect rate limits (async)
    
    Args:
        items: List of items to process
        batch_size: Number of items per batch
        process_func: Async function to process each batch
        delay_between_batches: Seconds to wait between batches
    
    Returns:
        Combined results from all batches
    """
    results = []
    total_batches = (len(items) + batch_size - 1) // batch_size
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} items)")
        
        batch_results = await process_func(batch, *args, **kwargs)
        if batch_results:
            results.extend(batch_results)
        
        # Wait between batches (except for last batch)
        if i + batch_size < len(items):
            await asyncio.sleep(delay_between_batches)
    
    return results


# Pre-configured rate limiters for different use cases

# Angel One API: 10 requests per second
angel_one_limiter = RateLimiter(max_calls=10, period=1.0)

# General broker API limiter
broker_rate_limiter = RateLimiter(max_calls=10, period=1.0)

# Async rate limiter for FastAPI endpoints
async_rate_limiter = AsyncRateLimiter(calls_per_second=3)
