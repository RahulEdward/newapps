"""
Qwen (Tongyi Qianwen) Client Implementation
===========================================

Qwen uses OpenAI-compatible API (DashScope).
"""

from .openai_client import OpenAIClient


class QwenClient(OpenAIClient):
    """
    Qwen Client
    
    Uses Alibaba Cloud DashScope's OpenAI-compatible mode.
    """
    
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL = "qwen-turbo"
    PROVIDER = "qwen"
