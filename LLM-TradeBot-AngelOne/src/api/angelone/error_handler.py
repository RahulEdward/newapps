"""
Error Handler for AngelOne
Handles API errors, logging, retry logic, and rate limiting

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

import time
import functools
from typing import Callable, Any, Optional, Dict, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from loguru import logger


class ErrorCode(Enum):
    """AngelOne API error codes"""
    # Authentication errors
    AUTH_INVALID_CREDENTIALS = "AG8001"
    AUTH_SESSION_EXPIRED = "AG8002"
    AUTH_TOTP_INVALID = "AG8003"
    AUTH_RATE_LIMITED = "AG8004"
    
    # Order errors
    ORDER_INVALID_SYMBOL = "AG9001"
    ORDER_INSUFFICIENT_MARGIN = "AG9002"
    ORDER_INVALID_QUANTITY = "AG9003"
    ORDER_MARKET_CLOSED = "AG9004"
    ORDER_REJECTED = "AG9005"
    ORDER_NOT_FOUND = "AG9006"
    
    # Data errors
    DATA_NOT_AVAILABLE = "AG7001"
    DATA_INVALID_INTERVAL = "AG7002"
    DATA_RATE_LIMITED = "AG7003"
    
    # Network errors
    NETWORK_TIMEOUT = "AG6001"
    NETWORK_CONNECTION_ERROR = "AG6002"
    NETWORK_SERVER_ERROR = "AG6003"
    
    # General errors
    UNKNOWN_ERROR = "AG0000"
    CRITICAL_ERROR = "AG0001"


@dataclass
class AngelOneError(Exception):
    """Custom exception for AngelOne API errors"""
    code: ErrorCode
    message: str
    details: Optional[Dict] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        super().__init__(f"[{self.code.value}] {self.message}")
    
    def is_retryable(self) -> bool:
        """Check if error is retryable"""
        retryable_codes = [
            ErrorCode.NETWORK_TIMEOUT,
            ErrorCode.NETWORK_CONNECTION_ERROR,
            ErrorCode.NETWORK_SERVER_ERROR,
            ErrorCode.DATA_RATE_LIMITED,
            ErrorCode.AUTH_RATE_LIMITED,
        ]
        return self.code in retryable_codes
    
    def is_critical(self) -> bool:
        """Check if error is critical (should stop trading)"""
        critical_codes = [
            ErrorCode.CRITICAL_ERROR,
            ErrorCode.AUTH_INVALID_CREDENTIALS,
            ErrorCode.ORDER_INSUFFICIENT_MARGIN,
        ]
        return self.code in critical_codes


class RateLimiter:
    """
    Rate limiter for API calls
    
    Features:
    - Track API call counts
    - Enforce rate limits
    - Automatic cooldown
    """
    
    def __init__(
        self,
        max_calls: int = 10,
        time_window: int = 1,  # seconds
        cooldown: int = 60  # seconds
    ):
        """
        Initialize RateLimiter
        
        Args:
            max_calls: Maximum calls per time window
            time_window: Time window in seconds
            cooldown: Cooldown period when limit exceeded
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.cooldown = cooldown
        
        self._calls: List[float] = []
        self._cooldown_until: float = 0
    
    def can_proceed(self) -> bool:
        """Check if API call can proceed"""
        now = time.time()
        
        # Check cooldown
        if now < self._cooldown_until:
            return False
        
        # Clean old calls
        self._calls = [t for t in self._calls if now - t < self.time_window]
        
        return len(self._calls) < self.max_calls
    
    def record_call(self):
        """Record an API call"""
        self._calls.append(time.time())
    
    def trigger_cooldown(self):
        """Trigger cooldown period"""
        self._cooldown_until = time.time() + self.cooldown
        logger.warning(f"Rate limit exceeded, cooldown for {self.cooldown}s")
    
    def wait_if_needed(self) -> float:
        """Wait if rate limited, return wait time"""
        now = time.time()
        
        # Check cooldown
        if now < self._cooldown_until:
            wait_time = self._cooldown_until - now
            logger.info(f"Rate limited, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            return wait_time
        
        # Check rate limit
        if not self.can_proceed():
            # Wait for oldest call to expire
            if self._calls:
                wait_time = self.time_window - (now - self._calls[0])
                if wait_time > 0:
                    logger.debug(f"Rate limit, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                    return wait_time
        
        return 0


class ErrorHandler:
    """
    Centralized error handling for AngelOne API
    
    Features:
    - Parse API error responses
    - Log all errors with details
    - Retry logic with exponential backoff
    - Rate limiting
    - Critical error detection
    """
    
    # AngelOne API error message mapping
    ERROR_MAPPING = {
        'Invalid credentials': ErrorCode.AUTH_INVALID_CREDENTIALS,
        'Session expired': ErrorCode.AUTH_SESSION_EXPIRED,
        'Invalid TOTP': ErrorCode.AUTH_TOTP_INVALID,
        'Rate limit exceeded': ErrorCode.AUTH_RATE_LIMITED,
        'Invalid symbol': ErrorCode.ORDER_INVALID_SYMBOL,
        'Insufficient margin': ErrorCode.ORDER_INSUFFICIENT_MARGIN,
        'Invalid quantity': ErrorCode.ORDER_INVALID_QUANTITY,
        'Market closed': ErrorCode.ORDER_MARKET_CLOSED,
        'Order rejected': ErrorCode.ORDER_REJECTED,
        'Order not found': ErrorCode.ORDER_NOT_FOUND,
        'Data not available': ErrorCode.DATA_NOT_AVAILABLE,
        'Invalid interval': ErrorCode.DATA_INVALID_INTERVAL,
        'Too many requests': ErrorCode.DATA_RATE_LIMITED,
        'Connection timeout': ErrorCode.NETWORK_TIMEOUT,
        'Connection error': ErrorCode.NETWORK_CONNECTION_ERROR,
        'Server error': ErrorCode.NETWORK_SERVER_ERROR,
    }
    
    def __init__(
        self,
        rate_limiter: RateLimiter = None,
        on_critical_error: Callable[[AngelOneError], None] = None
    ):
        """
        Initialize ErrorHandler
        
        Args:
            rate_limiter: Optional rate limiter
            on_critical_error: Callback for critical errors
        """
        self.rate_limiter = rate_limiter or RateLimiter()
        self._on_critical_error = on_critical_error
        self._error_count = 0
        self._last_error: Optional[AngelOneError] = None
        
        logger.info("ErrorHandler initialized")
    
    def parse_error(self, response: Dict, context: str = "") -> AngelOneError:
        """
        Parse API response and create AngelOneError
        
        Args:
            response: API response dictionary
            context: Context string for logging
        
        Returns:
            AngelOneError object
        """
        message = response.get('message', 'Unknown error')
        error_code = response.get('errorcode', '')
        
        # Try to map error message to code
        code = ErrorCode.UNKNOWN_ERROR
        for pattern, error_code_enum in self.ERROR_MAPPING.items():
            if pattern.lower() in message.lower():
                code = error_code_enum
                break
        
        error = AngelOneError(
            code=code,
            message=message,
            details={
                'context': context,
                'response': response,
                'api_error_code': error_code
            }
        )
        
        self._log_error(error)
        self._error_count += 1
        self._last_error = error
        
        # Handle critical errors
        if error.is_critical() and self._on_critical_error:
            self._on_critical_error(error)
        
        return error
    
    def _log_error(self, error: AngelOneError):
        """Log error with appropriate level"""
        if error.is_critical():
            logger.error(f"CRITICAL: {error}")
        elif error.is_retryable():
            logger.warning(f"Retryable error: {error}")
        else:
            logger.error(f"API error: {error}")
        
        if error.details:
            logger.debug(f"Error details: {error.details}")
    
    def log_order(
        self,
        action: str,
        symbol: str,
        side: str,
        quantity: int,
        price: float = None,
        order_id: str = None,
        status: str = None
    ):
        """Log order placement/modification/cancellation"""
        msg = f"ORDER {action}: {side} {quantity} {symbol}"
        if price:
            msg += f" @ {price}"
        if order_id:
            msg += f" (ID: {order_id})"
        if status:
            msg += f" - {status}"
        
        logger.info(msg)
    
    def log_auth(self, action: str, client_code: str, success: bool):
        """Log authentication events"""
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"AUTH {action}: {client_code} - {status}")
    
    @property
    def error_count(self) -> int:
        """Get total error count"""
        return self._error_count
    
    @property
    def last_error(self) -> Optional[AngelOneError]:
        """Get last error"""
        return self._last_error
    
    def reset_error_count(self):
        """Reset error count"""
        self._error_count = 0


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator for retry with exponential backoff
    
    Args:
        max_retries: Maximum number of retries
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        retryable_exceptions: Tuple of exceptions to retry
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Check if it's an AngelOneError and retryable
                    if isinstance(e, AngelOneError) and not e.is_retryable():
                        raise
                    
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {delay:.1f}s: {str(e)}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}"
                        )
                        raise
            
            raise last_exception
        
        return wrapper
    return decorator


def rate_limited(rate_limiter: RateLimiter):
    """
    Decorator for rate limiting API calls
    
    Args:
        rate_limiter: RateLimiter instance
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            rate_limiter.wait_if_needed()
            rate_limiter.record_call()
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Check for rate limit error
                if 'rate limit' in str(e).lower() or 'too many' in str(e).lower():
                    rate_limiter.trigger_cooldown()
                raise
        
        return wrapper
    return decorator
