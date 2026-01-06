"""
DeepSeek Client Implementation
==============================

DeepSeek uses OpenAI-compatible API, only needs to modify default configuration.
"""

from .openai_client import OpenAIClient


class DeepSeekClient(OpenAIClient):
    """
    DeepSeek Client
    
    Inherits from OpenAI client, uses OpenAI-compatible API.
    """
    
    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-chat"
    PROVIDER = "deepseek"
