"""
Exchange Trading Abstraction Layer

Provides a unified interface for trading across multiple exchanges.
"""

from .base import (
    BaseTrader,
    ExchangeAccount,
    ExchangeType,
    Position,
    AccountBalance,
    OrderResult
)
from .factory import (
    create_trader,
    create_and_initialize_trader,
    get_supported_exchanges
)
from .account_manager import AccountManager
from .angelone_trader import AngelOneTrader

# Try to import Binance trader (optional, for backward compatibility)
try:
    from .binance_trader import BinanceTrader
    BINANCE_AVAILABLE = True
except ImportError:
    BinanceTrader = None
    BINANCE_AVAILABLE = False


__all__ = [
    # Base classes
    'BaseTrader',
    'ExchangeAccount', 
    'ExchangeType',
    'Position',
    'AccountBalance',
    'OrderResult',
    
    # Factory
    'create_trader',
    'create_and_initialize_trader',
    'get_supported_exchanges',
    
    # Manager
    'AccountManager',
    
    # Implementations
    'AngelOneTrader',
]

# Add BinanceTrader to exports if available
if BINANCE_AVAILABLE:
    __all__.append('BinanceTrader')
