"""
Configuration Manager for AngelOne
Handles loading and validating configuration from YAML and environment variables

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7
"""

import os
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from loguru import logger


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails"""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"Config validation error for '{field}': {message}")


@dataclass
class AngelOneConfig:
    """AngelOne configuration container"""
    # Required credentials
    api_key: str
    client_code: str
    password: str
    totp_secret: str
    
    # Trading settings
    default_exchange: str = 'NSE'
    symbols: List[str] = field(default_factory=list)
    
    # Market hours
    market_open: str = '09:15'
    market_close: str = '15:30'
    pre_market_start: str = '09:00'
    
    # Risk management
    max_position_size: int = 100
    max_daily_loss: float = 10000.0
    stop_loss_percent: float = 2.0
    
    # WebSocket settings
    websocket_enabled: bool = True
    websocket_reconnect: bool = True
    websocket_reconnect_interval: int = 5
    
    # Logging
    log_level: str = 'INFO'
    log_file: Optional[str] = None
    
    # Backtesting
    backtest_start_date: Optional[str] = None
    backtest_end_date: Optional[str] = None
    initial_capital: float = 100000.0
    brokerage_per_trade: float = 20.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'api_key': self.api_key,
            'client_code': self.client_code,
            'password': '***',  # Mask password
            'totp_secret': '***',  # Mask secret
            'default_exchange': self.default_exchange,
            'symbols': self.symbols,
            'market_open': self.market_open,
            'market_close': self.market_close,
            'max_position_size': self.max_position_size,
            'max_daily_loss': self.max_daily_loss,
            'websocket_enabled': self.websocket_enabled,
            'log_level': self.log_level,
        }


class ConfigManager:
    """
    Manages configuration loading and validation
    
    Features:
    - Load config from YAML file
    - Support environment variables for secrets
    - Validate required fields
    - Provide defaults for optional fields
    - Support multiple trading symbols
    """
    
    # Required fields that must be present
    REQUIRED_FIELDS = ['api_key', 'client_code', 'password', 'totp_secret']
    
    # Environment variable mapping
    ENV_MAPPING = {
        'api_key': 'ANGELONE_API_KEY',
        'client_code': 'ANGELONE_CLIENT_CODE',
        'password': 'ANGELONE_PASSWORD',
        'totp_secret': 'ANGELONE_TOTP_SECRET',
    }
    
    # Valid exchanges
    VALID_EXCHANGES = ['NSE', 'BSE', 'NFO', 'MCX', 'CDS', 'BFO']
    
    def __init__(self, config_path: str = None):
        """
        Initialize ConfigManager
        
        Args:
            config_path: Path to YAML config file (optional)
        """
        self.config_path = config_path
        self._config: Optional[AngelOneConfig] = None
        self._raw_config: Dict = {}
        
        logger.info("ConfigManager initialized")
    
    def load(self, config_path: str = None) -> AngelOneConfig:
        """
        Load configuration from file and environment
        
        Args:
            config_path: Path to YAML config file
        
        Returns:
            AngelOneConfig object
        
        Raises:
            ConfigValidationError: If validation fails
        """
        path = config_path or self.config_path
        
        # Load from file if provided
        if path:
            self._raw_config = self._load_yaml(path)
        else:
            self._raw_config = {}
        
        # Resolve environment variables
        self._resolve_env_vars()
        
        # Validate configuration
        self._validate()
        
        # Create config object
        self._config = self._create_config()
        
        logger.info(f"Configuration loaded: {len(self._config.symbols)} symbols")
        return self._config
    
    def _load_yaml(self, path: str) -> Dict:
        """Load YAML configuration file"""
        try:
            config_path = Path(path)
            
            if not config_path.exists():
                logger.warning(f"Config file not found: {path}")
                return {}
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded config from: {path}")
            return config
            
        except yaml.YAMLError as e:
            raise ConfigValidationError('yaml', f"Invalid YAML: {str(e)}")
        except Exception as e:
            raise ConfigValidationError('file', f"Failed to load config: {str(e)}")
    
    def _resolve_env_vars(self):
        """Resolve environment variables for sensitive fields"""
        for field, env_var in self.ENV_MAPPING.items():
            # Check if field uses env var syntax: ${VAR_NAME}
            if field in self._raw_config:
                value = self._raw_config[field]
                if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                    env_name = value[2:-1]
                    self._raw_config[field] = os.environ.get(env_name, '')
            
            # If field not in config, try environment variable
            if field not in self._raw_config or not self._raw_config[field]:
                env_value = os.environ.get(env_var)
                if env_value:
                    self._raw_config[field] = env_value
                    logger.debug(f"Loaded {field} from environment variable {env_var}")
    
    def _validate(self):
        """Validate configuration"""
        # Check required fields
        missing = []
        for field in self.REQUIRED_FIELDS:
            if field not in self._raw_config or not self._raw_config[field]:
                missing.append(field)
        
        if missing:
            raise ConfigValidationError(
                'required_fields',
                f"Missing required fields: {', '.join(missing)}"
            )
        
        # Validate exchange
        exchange = self._raw_config.get('default_exchange', 'NSE').upper()
        if exchange not in self.VALID_EXCHANGES:
            raise ConfigValidationError(
                'default_exchange',
                f"Invalid exchange '{exchange}'. Valid: {self.VALID_EXCHANGES}"
            )
        
        # Validate numeric fields
        if 'max_position_size' in self._raw_config:
            try:
                int(self._raw_config['max_position_size'])
            except (ValueError, TypeError):
                raise ConfigValidationError(
                    'max_position_size',
                    "Must be an integer"
                )
        
        if 'max_daily_loss' in self._raw_config:
            try:
                float(self._raw_config['max_daily_loss'])
            except (ValueError, TypeError):
                raise ConfigValidationError(
                    'max_daily_loss',
                    "Must be a number"
                )
        
        # Validate symbols list
        symbols = self._raw_config.get('symbols', [])
        if symbols and not isinstance(symbols, list):
            raise ConfigValidationError(
                'symbols',
                "Must be a list of symbol strings"
            )
    
    def _create_config(self) -> AngelOneConfig:
        """Create AngelOneConfig from raw config"""
        return AngelOneConfig(
            api_key=self._raw_config['api_key'],
            client_code=self._raw_config['client_code'],
            password=self._raw_config['password'],
            totp_secret=self._raw_config['totp_secret'],
            default_exchange=self._raw_config.get('default_exchange', 'NSE').upper(),
            symbols=self._raw_config.get('symbols', []),
            market_open=self._raw_config.get('market_open', '09:15'),
            market_close=self._raw_config.get('market_close', '15:30'),
            pre_market_start=self._raw_config.get('pre_market_start', '09:00'),
            max_position_size=int(self._raw_config.get('max_position_size', 100)),
            max_daily_loss=float(self._raw_config.get('max_daily_loss', 10000.0)),
            stop_loss_percent=float(self._raw_config.get('stop_loss_percent', 2.0)),
            websocket_enabled=self._raw_config.get('websocket_enabled', True),
            websocket_reconnect=self._raw_config.get('websocket_reconnect', True),
            websocket_reconnect_interval=int(self._raw_config.get('websocket_reconnect_interval', 5)),
            log_level=self._raw_config.get('log_level', 'INFO'),
            log_file=self._raw_config.get('log_file'),
            backtest_start_date=self._raw_config.get('backtest_start_date'),
            backtest_end_date=self._raw_config.get('backtest_end_date'),
            initial_capital=float(self._raw_config.get('initial_capital', 100000.0)),
            brokerage_per_trade=float(self._raw_config.get('brokerage_per_trade', 20.0)),
        )
    
    @property
    def config(self) -> Optional[AngelOneConfig]:
        """Get loaded configuration"""
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        if self._config is None:
            return default
        return getattr(self._config, key, default)
    
    def reload(self) -> AngelOneConfig:
        """Reload configuration from file"""
        return self.load(self.config_path)
    
    @staticmethod
    def create_template(path: str = 'config.yaml'):
        """Create a template configuration file"""
        template = """# AngelOne Trading Bot Configuration
# Copy this file to config.yaml and fill in your credentials

# AngelOne API Credentials (required)
# You can use environment variables: ${ANGELONE_API_KEY}
api_key: ""
client_code: ""
password: ""
totp_secret: ""

# Trading Settings
default_exchange: NSE
symbols:
  - RELIANCE-EQ
  - TCS-EQ
  - INFY-EQ

# Market Hours (IST)
market_open: "09:15"
market_close: "15:30"
pre_market_start: "09:00"

# Risk Management
max_position_size: 100
max_daily_loss: 10000.0
stop_loss_percent: 2.0

# WebSocket Settings
websocket_enabled: true
websocket_reconnect: true
websocket_reconnect_interval: 5

# Logging
log_level: INFO
# log_file: logs/trading.log

# Backtesting (optional)
# backtest_start_date: "2024-01-01"
# backtest_end_date: "2024-12-31"
initial_capital: 100000.0
brokerage_per_trade: 20.0
"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(template)
        
        logger.info(f"Created config template: {path}")
        return path
