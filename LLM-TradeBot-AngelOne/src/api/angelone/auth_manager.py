"""
Authentication Manager for AngelOne SmartAPI
Handles TOTP generation, login, session management, and token refresh

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
import pyotp
from loguru import logger


@dataclass
class AuthTokens:
    """Container for authentication tokens"""
    jwt_token: str
    refresh_token: str
    feed_token: str
    expires_at: datetime


class AuthenticationError(Exception):
    """Custom exception for authentication failures"""
    def __init__(self, code: str, message: str, details: Dict[str, Any] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"{code}: {message}")


class AuthManager:
    """
    Handles AngelOne authentication with TOTP
    
    Features:
    - TOTP generation using pyotp
    - Login with credentials
    - Session refresh
    - Token validation
    - Retry with exponential backoff
    """
    
    # Error codes
    AUTH_FAILED = "AUTH_001"
    INVALID_TOTP = "AUTH_002"
    SESSION_EXPIRED = "AUTH_003"
    INVALID_CREDENTIALS = "AUTH_004"
    MAX_RETRIES_EXCEEDED = "AUTH_005"
    
    # Configuration
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds
    TOKEN_EXPIRY_BUFFER = 300  # 5 minutes buffer before expiry
    
    def __init__(
        self,
        api_key: str,
        client_code: str,
        password: str,
        totp_secret: str
    ):
        """
        Initialize AuthManager with credentials
        
        Args:
            api_key: AngelOne API key
            client_code: Trading account client code
            password: Account password
            totp_secret: TOTP secret for 2FA
        """
        self._validate_credentials(api_key, client_code, password, totp_secret)
        
        self.api_key = api_key
        self.client_code = client_code
        self.password = password
        self.totp_secret = totp_secret
        
        self._tokens: Optional[AuthTokens] = None
        self._smart_api = None
        
        logger.info(f"AuthManager initialized for client: {client_code}")
    
    def _validate_credentials(
        self,
        api_key: str,
        client_code: str,
        password: str,
        totp_secret: str
    ) -> None:
        """
        Validate all credentials before attempting connection
        
        Raises:
            AuthenticationError: If any credential is missing or invalid
        """
        missing = []
        
        if not api_key or not api_key.strip():
            missing.append("api_key")
        if not client_code or not client_code.strip():
            missing.append("client_code")
        if not password or not password.strip():
            missing.append("password")
        if not totp_secret or not totp_secret.strip():
            missing.append("totp_secret")
        
        if missing:
            raise AuthenticationError(
                code=self.INVALID_CREDENTIALS,
                message=f"Missing required credentials: {', '.join(missing)}",
                details={"missing_fields": missing}
            )
    
    def generate_totp(self) -> str:
        """
        Generate time-based OTP using pyotp
        
        Returns:
            6-digit TOTP string
            
        Note:
            TOTP changes every 30 seconds
        """
        totp = pyotp.TOTP(self.totp_secret)
        otp = totp.now()
        logger.debug(f"Generated TOTP: {otp[:2]}****")
        return otp
    
    def login(self, smart_api_class=None) -> AuthTokens:
        """
        Login to AngelOne with retry logic
        
        Args:
            smart_api_class: Optional SmartConnect class for dependency injection (testing)
        
        Returns:
            AuthTokens containing JWT, refresh, and feed tokens
            
        Raises:
            AuthenticationError: If login fails after max retries
        """
        # Import SmartConnect only if not injected (for testing)
        if smart_api_class is None:
            try:
                from SmartApi import SmartConnect
                smart_api_class = SmartConnect
            except ImportError:
                # For testing without SDK installed
                raise AuthenticationError(
                    code=self.AUTH_FAILED,
                    message="SmartApi SDK not installed. Install with: pip install smartapi-python",
                    details={}
                )
        
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"Login attempt {attempt + 1}/{self.MAX_RETRIES}")
                
                # Initialize SmartConnect
                self._smart_api = smart_api_class(api_key=self.api_key)
                
                # Generate fresh TOTP for each attempt
                totp = self.generate_totp()
                
                # Attempt login
                data = self._smart_api.generateSession(
                    self.client_code,
                    self.password,
                    totp
                )
                
                if data.get('status') and data.get('data'):
                    session_data = data['data']
                    
                    # Store tokens
                    feed_token = ''
                    if hasattr(self._smart_api, 'getfeedToken'):
                        feed_token = self._smart_api.getfeedToken() or ''
                    
                    self._tokens = AuthTokens(
                        jwt_token=session_data.get('jwtToken', ''),
                        refresh_token=session_data.get('refreshToken', ''),
                        feed_token=feed_token,
                        expires_at=datetime.now() + timedelta(hours=24)
                    )
                    
                    logger.info("Login successful")
                    if self._tokens.jwt_token:
                        logger.debug(f"JWT Token: {self._tokens.jwt_token[:20]}...")
                    
                    return self._tokens
                else:
                    error_msg = data.get('message', 'Unknown error')
                    raise AuthenticationError(
                        code=self.AUTH_FAILED,
                        message=f"Login failed: {error_msg}",
                        details={"response": data}
                    )
                    
            except AuthenticationError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"Login attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAYS[attempt]
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
        
        # All retries exhausted
        raise AuthenticationError(
            code=self.MAX_RETRIES_EXCEEDED,
            message=f"Login failed after {self.MAX_RETRIES} attempts",
            details={"last_error": str(last_error)}
        )
    
    def refresh_session(self) -> AuthTokens:
        """
        Refresh expired JWT token
        
        Returns:
            New AuthTokens with refreshed JWT
            
        Raises:
            AuthenticationError: If refresh fails
        """
        if not self._smart_api or not self._tokens:
            logger.warning("No active session, performing fresh login")
            return self.login()
        
        try:
            logger.info("Refreshing session...")
            
            data = self._smart_api.generateToken(self._tokens.refresh_token)
            
            if data.get('status') and data.get('data'):
                session_data = data['data']
                
                self._tokens = AuthTokens(
                    jwt_token=session_data.get('jwtToken', ''),
                    refresh_token=session_data.get('refreshToken', self._tokens.refresh_token),
                    feed_token=self._tokens.feed_token,
                    expires_at=datetime.now() + timedelta(hours=24)
                )
                
                logger.info("Session refreshed successfully")
                return self._tokens
            else:
                # Refresh failed, try fresh login
                logger.warning("Token refresh failed, attempting fresh login")
                return self.login()
                
        except Exception as e:
            logger.error(f"Session refresh failed: {str(e)}")
            return self.login()
    
    def is_session_valid(self) -> bool:
        """
        Check if current session is valid
        
        Returns:
            True if session is valid and not expired
        """
        if not self._tokens:
            return False
        
        # Check if tokens exist
        if not self._tokens.jwt_token:
            return False
        
        # Check expiry with buffer
        buffer_time = datetime.now() + timedelta(seconds=self.TOKEN_EXPIRY_BUFFER)
        if buffer_time >= self._tokens.expires_at:
            logger.debug("Session expiring soon")
            return False
        
        return True
    
    def ensure_valid_session(self) -> AuthTokens:
        """
        Ensure we have a valid session, refreshing if needed
        
        Returns:
            Valid AuthTokens
        """
        if self.is_session_valid():
            return self._tokens
        
        if self._tokens and self._tokens.refresh_token:
            return self.refresh_session()
        
        return self.login()
    
    def logout(self) -> bool:
        """
        Logout and invalidate session
        
        Returns:
            True if logout successful
        """
        try:
            if self._smart_api:
                self._smart_api.terminateSession(self.client_code)
                logger.info("Logged out successfully")
            
            self._tokens = None
            self._smart_api = None
            return True
            
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            self._tokens = None
            self._smart_api = None
            return False
    
    @property
    def tokens(self) -> Optional[AuthTokens]:
        """Get current tokens"""
        return self._tokens
    
    @property
    def jwt_token(self) -> Optional[str]:
        """Get current JWT token"""
        return self._tokens.jwt_token if self._tokens else None
    
    @property
    def feed_token(self) -> Optional[str]:
        """Get current feed token for WebSocket"""
        return self._tokens.feed_token if self._tokens else None
    
    @property
    def smart_api(self):
        """Get SmartConnect instance"""
        return self._smart_api
