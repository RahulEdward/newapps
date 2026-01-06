"""
Exchange Trader Factory

Creates appropriate trader instances based on exchange type.
"""

from typing import Dict, Any, Optional

from .base import BaseTrader, ExchangeAccount, ExchangeType

# Import AngelOne trader (primary for Indian market)
from .angelone_trader import AngelOneTrader

# Try to import Binance trader (optional, for backward compatibility)
try:
    from .binance_trader import BinanceTrader
    BINANCE_AVAILABLE = True
except ImportError:
    BinanceTrader = None
    BINANCE_AVAILABLE = False

from src.utils.logger import log


# Mapping of exchange types to trader classes
TRADER_CLASSES: Dict[ExchangeType, type] = {
    ExchangeType.ANGELONE: AngelOneTrader,
}

# Add Binance if available
if BINANCE_AVAILABLE:
    TRADER_CLASSES[ExchangeType.BINANCE] = BinanceTrader


def create_trader(account: ExchangeAccount) -> BaseTrader:
    """
    Create a trader instance for the given account configuration.
    
    Args:
        account: ExchangeAccount with exchange type and credentials
        
    Returns:
        BaseTrader instance for the specified exchange
        
    Raises:
        ValueError: If exchange type is not supported
    """
    trader_class = TRADER_CLASSES.get(account.exchange_type)
    
    if not trader_class:
        supported = [e.value for e in TRADER_CLASSES.keys()]
        raise ValueError(
            f"Unsupported exchange type: {account.exchange_type.value}. "
            f"Supported: {supported}"
        )
    
    log.info(f"Creating trader for account '{account.account_name}' ({account.exchange_type.value})")
    return trader_class(account)


async def create_and_initialize_trader(account: ExchangeAccount) -> Optional[BaseTrader]:
    """
    Create and initialize a trader instance.
    
    Convenience function that creates the trader and calls initialize().
    
    Args:
        account: ExchangeAccount configuration
        
    Returns:
        Initialized BaseTrader instance, or None if initialization failed
    """
    try:
        trader = create_trader(account)
        success = await trader.initialize()
        
        if success:
            return trader
        else:
            log.error(f"Failed to initialize trader for account: {account.account_name}")
            return None
            
    except Exception as e:
        log.error(f"Error creating trader for account {account.account_name}: {e}")
        return None


def get_supported_exchanges() -> list:
    """Get list of supported exchange types."""
    return [e.value for e in TRADER_CLASSES.keys()]
