"""
AI Trader - Configuration Management Module
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables (use override=True to ensure .env settings override current process environment variables)
load_dotenv(override=True)


class Config:
    """Configuration Management Class"""
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Load configuration file"""
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        
        if not config_path.exists():
            # If no config.yaml, use example
            example_path = Path(__file__).parent.parent.parent / "config.example.yaml"
            if example_path.exists():
                with open(example_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f)
        else:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        
        # Override sensitive information from environment variables
        self._override_from_env()
    
    def _override_from_env(self):
        """Override configuration from environment variables"""
        # Binance
        if os.getenv('BINANCE_API_KEY'):
            self._config['binance']['api_key'] = os.getenv('BINANCE_API_KEY')
        if os.getenv('BINANCE_API_SECRET'):
            self._config['binance']['api_secret'] = os.getenv('BINANCE_API_SECRET')
        
        # DeepSeek (backward compatible)
        if os.getenv('DEEPSEEK_API_KEY'):
            self._config['deepseek']['api_key'] = os.getenv('DEEPSEEK_API_KEY')
        
        # Redis
        if os.getenv('REDIS_HOST'):
            self._config['redis']['host'] = os.getenv('REDIS_HOST')
        if os.getenv('REDIS_PORT'):
            self._config['redis']['port'] = int(os.getenv('REDIS_PORT'))
        
        # LLM multi-provider support
        if 'llm' not in self._config:
            self._config['llm'] = {}
        
        # API Keys for each provider
        # Support ANTHROPIC_API_KEY as alias for CLAUDE_API_KEY (higher priority)
        claude_api_key = os.getenv('ANTHROPIC_API_KEY') or os.getenv('CLAUDE_API_KEY')
        
        llm_api_keys = {
            'openai': os.getenv('OPENAI_API_KEY'),
            'deepseek': os.getenv('DEEPSEEK_API_KEY'),
            'claude': claude_api_key,
            'qwen': os.getenv('QWEN_API_KEY'),
            'gemini': os.getenv('GEMINI_API_KEY'),
        }
        self._config['llm']['api_keys'] = {k: v for k, v in llm_api_keys.items() if v}
        
        # Custom base URL (for proxies)
        # Support ANTHROPIC_BASE_URL as alias for LLM_BASE_URL (higher priority)
        base_url = os.getenv('ANTHROPIC_BASE_URL') or os.getenv('LLM_BASE_URL')
        if base_url:
            self._config['llm']['base_url'] = base_url
    
    def get(self, key_path: str, default=None):
        """
        Get configuration value
        key_path: Dot-separated path, e.g. 'binance.api_key'
        """
        keys = key_path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    @property
    def binance(self):
        return self._config.get('binance', {})
    
    @property
    def deepseek(self):
        return self._config.get('deepseek', {})
    
    @property
    def trading(self):
        return self._config.get('trading', {})
    
    @property
    def risk(self):
        return self._config.get('risk', {})
    
    @property
    def redis(self):
        return self._config.get('redis', {})
    
    @property
    def logging(self):
        return self._config.get('logging', {})
    
    @property
    def backtest(self):
        return self._config.get('backtest', {})
    
    @property
    def llm(self):
        return self._config.get('llm', {})


# Global configuration instance
config = Config()
