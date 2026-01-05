"""
Tests for Authentication Manager
Includes property-based tests and unit tests

Feature: llm-tradebot-angelone
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from api.angelone.auth_manager import AuthManager, AuthenticationError, AuthTokens


# =============================================================================
# Mock SmartConnect for testing without SDK
# =============================================================================

class MockSmartConnect:
    """Mock SmartConnect class for testing"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self._should_fail = False
        self._fail_count = 0
        self._max_fails = 0
    
    def generateSession(self, client_code, password, totp):
        if self._should_fail:
            if self._fail_count < self._max_fails:
                self._fail_count += 1
                raise Exception("Connection failed")
        
        return {
            'status': True,
            'data': {
                'jwtToken': 'test_jwt_token_12345',
                'refreshToken': 'test_refresh_token_67890'
            }
        }
    
    def getfeedToken(self):
        return 'test_feed_token'
    
    def generateToken(self, refresh_token):
        return {
            'status': True,
            'data': {
                'jwtToken': 'new_jwt_token',
                'refreshToken': 'new_refresh_token'
            }
        }
    
    def terminateSession(self, client_code):
        return {'status': True}


class MockSmartConnectFailing:
    """Mock SmartConnect that always fails"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.call_count = 0
    
    def generateSession(self, client_code, password, totp):
        self.call_count += 1
        raise Exception("Connection failed")


# =============================================================================
# Property-Based Tests
# =============================================================================

class TestTOTPGenerationProperty:
    """
    Property 1: TOTP Generation Validity
    *For any* valid TOTP secret, the generated TOTP SHALL be a 6-digit numeric string
    
    **Validates: Requirements 1.2**
    """
    
    # Use valid base32 secrets with proper padding (multiple of 8 chars)
    @given(st.sampled_from([
        'JBSWY3DPEHPK3PXP',  # 16 chars - standard
        'GEZDGNBVGY3TQOJQ',  # 16 chars
        'MFRGGZDFMY4TQMZS',  # 16 chars
        'NBSWY3DPEHPK3PXP',  # 16 chars
        'KRSXG5CTMVRXEZLU',  # 16 chars
        'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP',  # 32 chars
    ]))
    @settings(max_examples=100)
    def test_totp_is_six_digit_numeric(self, secret):
        """
        Feature: llm-tradebot-angelone, Property 1: TOTP Generation Validity
        For any valid base32 secret, TOTP should be 6-digit numeric
        """
        auth = AuthManager(
            api_key="test_api_key",
            client_code="test_client",
            password="test_password",
            totp_secret=secret
        )
        
        totp = auth.generate_totp()
        
        # Property: TOTP must be exactly 6 characters
        assert len(totp) == 6, f"TOTP length should be 6, got {len(totp)}"
        
        # Property: TOTP must be all digits
        assert totp.isdigit(), f"TOTP should be numeric, got {totp}"


class TestCredentialValidationProperty:
    """
    Property 3: Credential Validation
    *For any* set of credentials with missing or empty required fields,
    the client SHALL raise a validation error before attempting connection.
    
    **Validates: Requirements 1.6**
    """
    
    @given(
        api_key=st.one_of(st.none(), st.just(""), st.just("  "), st.text(min_size=1)),
        client_code=st.one_of(st.none(), st.just(""), st.just("  "), st.text(min_size=1)),
        password=st.one_of(st.none(), st.just(""), st.just("  "), st.text(min_size=1)),
        totp_secret=st.one_of(st.none(), st.just(""), st.just("  "), st.text(min_size=1))
    )
    @settings(max_examples=100)
    def test_missing_credentials_raise_error(self, api_key, client_code, password, totp_secret):
        """
        Feature: llm-tradebot-angelone, Property 3: Credential Validation
        """
        def is_valid(val):
            return val is not None and isinstance(val, str) and val.strip() != ""
        
        all_valid = all([
            is_valid(api_key),
            is_valid(client_code),
            is_valid(password),
            is_valid(totp_secret)
        ])
        
        if all_valid:
            try:
                auth = AuthManager(
                    api_key=api_key,
                    client_code=client_code,
                    password=password,
                    totp_secret=totp_secret
                )
                assert auth is not None
            except AuthenticationError:
                pytest.fail("Should not raise error with valid credentials")
        else:
            with pytest.raises(AuthenticationError) as exc_info:
                AuthManager(
                    api_key=api_key,
                    client_code=client_code,
                    password=password,
                    totp_secret=totp_secret
                )
            
            assert exc_info.value.code == AuthManager.INVALID_CREDENTIALS


# =============================================================================
# Unit Tests
# =============================================================================

class TestAuthManagerUnit:
    """Unit tests for AuthManager"""
    
    def test_valid_credentials_initialization(self):
        """Test initialization with valid credentials"""
        auth = AuthManager(
            api_key="valid_api_key",
            client_code="ABC123",
            password="password123",
            totp_secret="JBSWY3DPEHPK3PXP"
        )
        
        assert auth.api_key == "valid_api_key"
        assert auth.client_code == "ABC123"
    
    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises error"""
        with pytest.raises(AuthenticationError) as exc_info:
            AuthManager(
                api_key="",
                client_code="ABC123",
                password="password123",
                totp_secret="JBSWY3DPEHPK3PXP"
            )
        
        assert "api_key" in exc_info.value.details["missing_fields"]
    
    def test_missing_multiple_credentials(self):
        """Test that multiple missing credentials are reported"""
        with pytest.raises(AuthenticationError) as exc_info:
            AuthManager(
                api_key="",
                client_code="",
                password="password123",
                totp_secret=""
            )
        
        missing = exc_info.value.details["missing_fields"]
        assert "api_key" in missing
        assert "client_code" in missing
        assert "totp_secret" in missing
    
    def test_totp_generation_format(self):
        """Test TOTP generation returns correct format"""
        auth = AuthManager(
            api_key="test_key",
            client_code="TEST123",
            password="test_pass",
            totp_secret="JBSWY3DPEHPK3PXP"
        )
        
        totp = auth.generate_totp()
        
        assert len(totp) == 6
        assert totp.isdigit()
    
    def test_session_invalid_before_login(self):
        """Test session is invalid before login"""
        auth = AuthManager(
            api_key="test_key",
            client_code="TEST123",
            password="test_pass",
            totp_secret="JBSWY3DPEHPK3PXP"
        )
        
        assert auth.is_session_valid() == False
        assert auth.tokens is None
    
    def test_login_success_with_mock(self):
        """Test successful login with mock SDK"""
        auth = AuthManager(
            api_key="test_key",
            client_code="TEST123",
            password="test_pass",
            totp_secret="JBSWY3DPEHPK3PXP"
        )
        
        tokens = auth.login(smart_api_class=MockSmartConnect)
        
        assert tokens.jwt_token == 'test_jwt_token_12345'
        assert tokens.refresh_token == 'test_refresh_token_67890'
        assert tokens.feed_token == 'test_feed_token'
        assert auth.is_session_valid() == True
    
    def test_login_retries_on_failure(self):
        """Test login retries on failure"""
        auth = AuthManager(
            api_key="test_key",
            client_code="TEST123",
            password="test_pass",
            totp_secret="JBSWY3DPEHPK3PXP"
        )
        
        # Override retry delays for faster test
        auth.RETRY_DELAYS = [0, 0, 0]
        
        with pytest.raises(AuthenticationError) as exc_info:
            auth.login(smart_api_class=MockSmartConnectFailing)
        
        assert exc_info.value.code == AuthManager.MAX_RETRIES_EXCEEDED
    
    def test_logout(self):
        """Test logout clears session"""
        auth = AuthManager(
            api_key="test_key",
            client_code="TEST123",
            password="test_pass",
            totp_secret="JBSWY3DPEHPK3PXP"
        )
        
        auth.login(smart_api_class=MockSmartConnect)
        assert auth.is_session_valid() == True
        
        auth.logout()
        assert auth.is_session_valid() == False
        assert auth.tokens is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
