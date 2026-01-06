"""
Claude Client Implementation
============================

Anthropic Claude uses a different API format, requires separate implementation.
"""

from typing import Dict, Any, List
from .base import BaseLLMClient, LLMConfig, ChatMessage, LLMResponse


class ClaudeClient(BaseLLMClient):
    """
    Claude Client (Anthropic API)
    
    Claude uses a different API format:
    - Authentication uses x-api-key instead of Bearer token
    - Endpoint is /messages instead of /chat/completions
    - System prompt is a separate field
    """
    
    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    PROVIDER = "claude"
    
    ANTHROPIC_VERSION = "2023-06-01"
    
    def _build_headers(self) -> Dict[str, str]:
        """Build Anthropic authentication headers"""
        return {
            "x-api-key": self.config.api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "Content-Type": "application/json"
        }
    
    def _build_url(self) -> str:
        """Claude uses /messages endpoint"""
        return f"{self.base_url}/messages"
    
    def _build_request_body(
        self, 
        messages: List[ChatMessage],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Build Claude request body
        
        Claude's system prompt is a separate field, not in messages
        """
        # Extract system message
        system_content = ""
        user_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            else:
                user_messages.append({"role": msg.role, "content": msg.content})
        
        body = {
            "model": self.model,
            "messages": user_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens)
        }
        
        if system_content:
            body["system"] = system_content
        
        # Claude doesn't support temperature=0, minimum is 0.1
        temperature = kwargs.get("temperature", self.config.temperature)
        if temperature > 0:
            body["temperature"] = max(0.1, temperature)
        
        return body
    
    def _parse_response(self, response: Dict[str, Any]) -> LLMResponse:
        """Parse Claude response"""
        content = ""
        for block in response.get("content", []):
            if block.get("type") == "text":
                content = block.get("text", "")
                break
        
        return LLMResponse(
            content=content,
            model=response.get("model", self.model),
            provider=self.PROVIDER,
            usage=response.get("usage", {}),
            raw_response=response
        )
