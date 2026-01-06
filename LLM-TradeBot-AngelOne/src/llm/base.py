"""
LLM Abstract Base Class and Configuration
==========================================

Provides unified LLM client interface supporting multiple LLM providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import httpx


@dataclass
class LLMConfig:
    """LLM Configuration Data Class"""
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None
    timeout: int = 120
    max_retries: int = 5
    temperature: float = 0.7
    max_tokens: int = 4096
    
    def __post_init__(self):
        if not self.api_key:
            raise ValueError("api_key is required")


@dataclass
class ChatMessage:
    """Chat Message"""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """LLM Response"""
    content: str
    model: str
    provider: str
    usage: Dict[str, int] = field(default_factory=dict)
    raw_response: Optional[Dict] = None


class BaseLLMClient(ABC):
    """
    LLM Client Abstract Base Class
    
    All LLM provider clients must inherit from this class and implement abstract methods.
    """
    
    # Default values that subclasses need to override
    DEFAULT_BASE_URL: str = ""
    DEFAULT_MODEL: str = ""
    PROVIDER: str = "base"
    
    def __init__(self, config: LLMConfig):
        """
        Initialize LLM client
        
        Args:
            config: LLM configuration
        """
        self.config = config
        self.base_url = config.base_url or self.DEFAULT_BASE_URL
        self.model = config.model or self.DEFAULT_MODEL
        self.client = httpx.Client(timeout=config.timeout)
    
    @abstractmethod
    def _build_headers(self) -> Dict[str, str]:
        """Build request headers (subclasses implement different authentication methods)"""
        pass
    
    @abstractmethod
    def _build_request_body(
        self, 
        messages: List[ChatMessage],
        **kwargs
    ) -> Dict[str, Any]:
        """Build request body (subclasses can override for different formats)"""
        pass
    
    @abstractmethod
    def _parse_response(self, response: Dict[str, Any]) -> LLMResponse:
        """Parse response (subclasses can override for different formats)"""
        pass
    
    def _build_url(self) -> str:
        """Build request URL"""
        return f"{self.base_url}/chat/completions"
    
    def _messages_to_list(self, messages: List[ChatMessage]) -> List[Dict[str, str]]:
        """Convert ChatMessage list to dictionary list"""
        return [{"role": m.role, "content": m.content} for m in messages]
    
    def chat(
        self, 
        system_prompt: str, 
        user_prompt: str,
        **kwargs
    ) -> LLMResponse:
        """
        Unified call entry point (simplified version)
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            LLMResponse object
        """
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt)
        ]
        return self.chat_messages(messages, **kwargs)
    
    def chat_messages(
        self, 
        messages: List[ChatMessage],
        **kwargs
    ) -> LLMResponse:
        """
        Multi-turn conversation call
        
        Args:
            messages: Message list
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse object
        """
        url = self._build_url()
        headers = self._build_headers()
        body = self._build_request_body(messages, **kwargs)
        
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.post(url, json=body, headers=headers)
                response.raise_for_status()
                return self._parse_response(response.json())
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in [429, 500, 502, 503, 504]:
                    # Retryable HTTP errors
                    import time
                    wait_time = 2 ** attempt
                    print(f"⚠️ LLM HTTP Error {e.response.status_code}, retrying in {wait_time}s (attempt {attempt + 1}/{self.config.max_retries})")
                    time.sleep(wait_time)
                    continue
                raise
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError, 
                    ConnectionResetError, ConnectionError, OSError) as e:
                # Network connection errors, need to retry
                last_error = e
                import time
                wait_time = 2 ** attempt
                print(f"⚠️ LLM Connection Error: {type(e).__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{self.config.max_retries})")
                time.sleep(wait_time)
                continue
            except Exception as e:
                last_error = e
                # Other unknown errors, throw after last attempt
                if attempt < self.config.max_retries - 1:
                    import time
                    wait_time = 2 ** attempt
                    print(f"⚠️ LLM Unexpected Error: {type(e).__name__}: {e}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                raise
        
        raise last_error or Exception("Max retries exceeded")

    
    def close(self):
        """Close HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
