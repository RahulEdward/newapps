"""
Google Gemini Client Implementation
===================================

Gemini uses Google AI API, format differs from OpenAI.
"""

from typing import Dict, Any, List
from .base import BaseLLMClient, LLMConfig, ChatMessage, LLMResponse


class GeminiClient(BaseLLMClient):
    """
    Google Gemini Client
    
    Gemini API characteristics:
    - Uses API key as URL parameter
    - Message format uses parts instead of content
    - Different endpoint structure
    """
    
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-1.5-flash"
    PROVIDER = "gemini"
    
    def _build_headers(self) -> Dict[str, str]:
        """Gemini uses simple Content-Type header"""
        return {
            "Content-Type": "application/json"
        }
    
    def _build_url(self) -> str:
        """Gemini API URL includes model and api_key"""
        return f"{self.base_url}/models/{self.model}:generateContent?key={self.config.api_key}"
    
    def _build_request_body(
        self, 
        messages: List[ChatMessage],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Build Gemini request body
        
        Gemini format:
        - contents: [{role: "user", parts: [{text: "..."}]}]
        - systemInstruction: {parts: [{text: "..."}]}
        """
        contents = []
        system_instruction = None
        
        for msg in messages:
            if msg.role == "system":
                system_instruction = {
                    "parts": [{"text": msg.content}]
                }
            else:
                # Gemini uses "model" instead of "assistant"
                role = "model" if msg.role == "assistant" else msg.role
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.content}]
                })
        
        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "maxOutputTokens": kwargs.get("max_tokens", self.config.max_tokens)
            }
        }
        
        if system_instruction:
            body["systemInstruction"] = system_instruction
        
        return body
    
    def _parse_response(self, response: Dict[str, Any]) -> LLMResponse:
        """Parse Gemini response"""
        content = ""
        
        candidates = response.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                content = parts[0].get("text", "")
        
        # Gemini usage format is different
        usage_metadata = response.get("usageMetadata", {})
        usage = {
            "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
            "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
            "total_tokens": usage_metadata.get("totalTokenCount", 0)
        }
        
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.PROVIDER,
            usage=usage,
            raw_response=response
        )
