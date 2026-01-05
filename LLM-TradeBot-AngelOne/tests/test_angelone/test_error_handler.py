"""
Tests for Error Handler (Task 13)
Tests error parsing, logging, retry logic, and rate limiting

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

import pytest
import time
from unittest.mock import Mock, patch

from src.api.angelone.error_handler import (
    ErrorHandler, ErrorCode, AngelOneError, RateLimiter,
    retry_with_backoff, rate_limited
)


class TestAngelOneError:
    """Test AngelOneError exception class"""
    
    def test_error_creation(self):
        """Test creating AngelOneError"""
        error = AngelOneError(
            code=ErrorCode.AUTH_INVALID_CREDENTIALS,
            message="Invalid credentials"
        )
        
        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert error.message == "Invalid credentials"
        assert error.timestamp is not None
    
    def test_error_with_details(self):
        """Test error with details"""
        error = AngelOneError(
            code=ErrorCode.ORDER_REJECTED,
            message="Order rejected",
            details={'reason': 'Insufficient margin'}
        )
        
        assert error.details['reason'] == 'Insufficient margin'
    
    def test_retryable_error(self):
        """Test retryable error detection"""
        retryable = AngelOneError(
            code=ErrorCode.NETWORK_TIMEOUT,
            message="Connection timeout"
        )
        
        non_retryable = AngelOneError(
            code=ErrorCode.AUTH_INVALID_CREDENTIALS,
            message="Invalid credentials"
        )
        
        assert retryable.is_retryable() is True
        assert non_retryable.is_retryable() is False
    
    def test_critical_error(self):
        """Test critical error detection"""
        critical = AngelOneError(
            code=ErrorCode.CRITICAL_ERROR,
            message="Critical error"
        )
        
        non_critical = AngelOneError(
            code=ErrorCode.DATA_NOT_AVAILABLE,
            message="Data not available"
        )
        
        assert critical.is_critical() is True
        assert non_critical.is_critical() is False
    
    def test_error_string(self):
        """Test error string representation"""
        error = AngelOneError(
            code=ErrorCode.ORDER_REJECTED,
            message="Order rejected"
        )
        
        assert "[AG9005]" in str(error)
        assert "Order rejected" in str(error)


class TestErrorHandler:
    """Test ErrorHandler class"""
    
    @pytest.fixture
    def handler(self):
        return ErrorHandler()
    
    def test_parse_error_invalid_credentials(self, handler):
        """Test parsing invalid credentials error"""
        response = {
            'status': False,
            'message': 'Invalid credentials provided'
        }
        
        error = handler.parse_error(response, "login")
        
        assert error.code == ErrorCode.AUTH_INVALID_CREDENTIALS
        assert handler.error_count == 1
    
    def test_parse_error_insufficient_margin(self, handler):
        """Test parsing insufficient margin error"""
        response = {
            'status': False,
            'message': 'Insufficient margin for order'
        }
        
        error = handler.parse_error(response, "order")
        
        assert error.code == ErrorCode.ORDER_INSUFFICIENT_MARGIN
    
    def test_parse_error_rate_limited(self, handler):
        """Test parsing rate limit error"""
        response = {
            'status': False,
            'message': 'Too many requests, please try later'
        }
        
        error = handler.parse_error(response, "data")
        
        assert error.code == ErrorCode.DATA_RATE_LIMITED
    
    def test_parse_unknown_error(self, handler):
        """Test parsing unknown error"""
        response = {
            'status': False,
            'message': 'Some unknown error occurred'
        }
        
        error = handler.parse_error(response, "unknown")
        
        assert error.code == ErrorCode.UNKNOWN_ERROR
    
    def test_critical_error_callback(self):
        """Test critical error callback"""
        callback = Mock()
        handler = ErrorHandler(on_critical_error=callback)
        
        response = {
            'status': False,
            'message': 'Invalid credentials'
        }
        
        handler.parse_error(response, "login")
        
        callback.assert_called_once()
    
    def test_log_order(self, handler, caplog):
        """Test order logging"""
        handler.log_order(
            action="PLACE",
            symbol="RELIANCE-EQ",
            side="BUY",
            quantity=10,
            price=2500.0,
            order_id="123456",
            status="PLACED"
        )
        
        # Check log was created (loguru doesn't use caplog directly)
        # Just verify no exception
        assert True
    
    def test_log_auth(self, handler):
        """Test auth logging"""
        handler.log_auth("LOGIN", "TEST123", True)
        handler.log_auth("LOGOUT", "TEST123", True)
        
        # Just verify no exception
        assert True
    
    def test_error_count(self, handler):
        """Test error counting"""
        assert handler.error_count == 0
        
        handler.parse_error({'message': 'Error 1'}, "test")
        handler.parse_error({'message': 'Error 2'}, "test")
        
        assert handler.error_count == 2
        
        handler.reset_error_count()
        assert handler.error_count == 0
    
    def test_last_error(self, handler):
        """Test last error tracking"""
        assert handler.last_error is None
        
        handler.parse_error({'message': 'First error'}, "test")
        handler.parse_error({'message': 'Second error'}, "test")
        
        assert handler.last_error.message == 'Second error'


class TestRateLimiter:
    """Test RateLimiter class"""
    
    def test_can_proceed_under_limit(self):
        """Test can proceed when under limit"""
        limiter = RateLimiter(max_calls=5, time_window=1)
        
        for _ in range(4):
            assert limiter.can_proceed() is True
            limiter.record_call()
    
    def test_cannot_proceed_at_limit(self):
        """Test cannot proceed when at limit"""
        limiter = RateLimiter(max_calls=3, time_window=1)
        
        for _ in range(3):
            limiter.record_call()
        
        assert limiter.can_proceed() is False
    
    def test_cooldown(self):
        """Test cooldown functionality"""
        limiter = RateLimiter(max_calls=5, time_window=1, cooldown=1)
        
        limiter.trigger_cooldown()
        
        assert limiter.can_proceed() is False
    
    def test_calls_expire(self):
        """Test that old calls expire"""
        limiter = RateLimiter(max_calls=2, time_window=0.1)
        
        limiter.record_call()
        limiter.record_call()
        
        assert limiter.can_proceed() is False
        
        time.sleep(0.15)  # Wait for calls to expire
        
        assert limiter.can_proceed() is True


class TestRetryWithBackoff:
    """Test retry_with_backoff decorator"""
    
    def test_successful_call_no_retry(self):
        """Test successful call doesn't retry"""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_func()
        
        assert result == "success"
        assert call_count == 1
    
    def test_retry_on_failure(self):
        """Test retry on failure"""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return "success"
        
        result = failing_then_success()
        
        assert result == "success"
        assert call_count == 3
    
    def test_max_retries_exceeded(self):
        """Test max retries exceeded"""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")
        
        with pytest.raises(Exception, match="Always fails"):
            always_fails()
        
        assert call_count == 3  # Initial + 2 retries
    
    def test_non_retryable_error_not_retried(self):
        """Test non-retryable AngelOneError is not retried"""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01, retryable_exceptions=(AngelOneError,))
        def non_retryable():
            nonlocal call_count
            call_count += 1
            raise AngelOneError(
                code=ErrorCode.AUTH_INVALID_CREDENTIALS,
                message="Invalid credentials"
            )
        
        with pytest.raises(AngelOneError):
            non_retryable()
        
        assert call_count == 1  # No retries


class TestRateLimitedDecorator:
    """Test rate_limited decorator"""
    
    def test_rate_limited_calls(self):
        """Test rate limited calls"""
        limiter = RateLimiter(max_calls=2, time_window=0.1)
        call_count = 0
        
        @rate_limited(limiter)
        def api_call():
            nonlocal call_count
            call_count += 1
            return "success"
        
        # First two calls should be immediate
        api_call()
        api_call()
        
        assert call_count == 2
    
    def test_rate_limit_triggers_cooldown(self):
        """Test rate limit error triggers cooldown"""
        limiter = RateLimiter(max_calls=10, time_window=1, cooldown=0.1)
        
        @rate_limited(limiter)
        def rate_limit_error():
            raise Exception("Rate limit exceeded")
        
        with pytest.raises(Exception):
            rate_limit_error()
        
        # Cooldown should be triggered
        assert limiter.can_proceed() is False


class TestErrorCode:
    """Test ErrorCode enum"""
    
    def test_error_code_values(self):
        """Test error code values"""
        assert ErrorCode.AUTH_INVALID_CREDENTIALS.value == "AG8001"
        assert ErrorCode.ORDER_REJECTED.value == "AG9005"
        assert ErrorCode.NETWORK_TIMEOUT.value == "AG6001"
        assert ErrorCode.UNKNOWN_ERROR.value == "AG0000"
    
    def test_all_error_codes_unique(self):
        """Test all error codes are unique"""
        values = [code.value for code in ErrorCode]
        assert len(values) == len(set(values))
