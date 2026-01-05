"""
Symbol Mapper for AngelOne SmartAPI
Maps trading symbols to AngelOne symbol tokens
Handles NSE, BSE, NFO, MCX exchanges

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
"""

import json
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class Exchange(Enum):
    """Supported exchanges"""
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"  # NSE Futures & Options
    MCX = "MCX"  # Multi Commodity Exchange
    CDS = "CDS"  # Currency Derivatives
    BFO = "BFO"  # BSE Futures & Options


class InstrumentType(Enum):
    """Types of instruments"""
    EQUITY = "EQ"
    FUTURES = "FUT"
    CALL_OPTION = "CE"
    PUT_OPTION = "PE"
    INDEX = "INDEX"
    COMMODITY = "COMMODITY"


@dataclass
class SymbolInfo:
    """Symbol information container"""
    symbol: str
    token: str
    exchange: str
    name: str
    lot_size: int
    tick_size: float
    instrument_type: str
    expiry: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None


class SymbolNotFoundError(Exception):
    """Exception raised when symbol is not found"""
    def __init__(self, symbol: str, exchange: str = None, message: str = None):
        self.symbol = symbol
        self.exchange = exchange
        self.message = message or f"Symbol '{symbol}' not found"
        if exchange:
            self.message += f" in exchange '{exchange}'"
        super().__init__(self.message)


class SymbolMapper:
    """
    Maps trading symbols to AngelOne symbol tokens
    
    Features:
    - Load instrument master from AngelOne
    - Map symbols to tokens for NSE, BSE, NFO, MCX
    - Support equity, futures, and options symbols
    - Search symbols by name
    """
    
    # AngelOne instrument master URL
    INSTRUMENT_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    
    def __init__(self):
        """Initialize SymbolMapper"""
        self._instruments: Dict[str, Dict[str, SymbolInfo]] = {
            Exchange.NSE.value: {},
            Exchange.BSE.value: {},
            Exchange.NFO.value: {},
            Exchange.MCX.value: {},
            Exchange.CDS.value: {},
            Exchange.BFO.value: {},
        }
        self._loaded = False
        self._raw_data: List[Dict] = []
        
        logger.info("SymbolMapper initialized")
    
    def load_instruments(self, data: List[Dict] = None) -> int:
        """
        Load instrument master from AngelOne or provided data
        
        Args:
            data: Optional pre-loaded instrument data (for testing)
        
        Returns:
            Number of instruments loaded
        """
        if data is not None:
            self._raw_data = data
        else:
            logger.info("Fetching instrument master from AngelOne...")
            try:
                response = requests.get(self.INSTRUMENT_URL, timeout=30)
                response.raise_for_status()
                self._raw_data = response.json()
                logger.info(f"Fetched {len(self._raw_data)} instruments")
            except Exception as e:
                logger.error(f"Failed to fetch instruments: {str(e)}")
                raise
        
        # Process instruments
        count = 0
        for item in self._raw_data:
            try:
                symbol_info = self._parse_instrument(item)
                if symbol_info:
                    exchange = symbol_info.exchange
                    if exchange in self._instruments:
                        # Store by trading symbol
                        key = symbol_info.symbol
                        self._instruments[exchange][key] = symbol_info
                        count += 1
            except Exception as e:
                logger.debug(f"Skipping instrument: {str(e)}")
                continue
        
        self._loaded = True
        logger.info(f"Loaded {count} instruments")
        return count
    
    def _parse_instrument(self, item: Dict) -> Optional[SymbolInfo]:
        """Parse raw instrument data into SymbolInfo"""
        try:
            exchange = item.get('exch_seg', '')
            symbol = item.get('symbol', '')
            token = item.get('token', '')
            name = item.get('name', '')
            
            if not all([exchange, symbol, token]):
                return None
            
            # Determine instrument type
            instrument_type = self._determine_instrument_type(item)
            
            # Parse lot size and tick size
            lot_size = int(item.get('lotsize', 1) or 1)
            tick_size = float(item.get('tick_size', 0.05) or 0.05)
            
            # Parse expiry for derivatives
            expiry = item.get('expiry', None)
            
            # Parse strike and option type for options
            strike = None
            option_type = None
            if instrument_type in [InstrumentType.CALL_OPTION.value, InstrumentType.PUT_OPTION.value]:
                strike = float(item.get('strike', 0) or 0) / 100  # AngelOne stores strike * 100
                option_type = instrument_type
            
            return SymbolInfo(
                symbol=symbol,
                token=token,
                exchange=exchange,
                name=name,
                lot_size=lot_size,
                tick_size=tick_size,
                instrument_type=instrument_type,
                expiry=expiry,
                strike=strike,
                option_type=option_type
            )
        except Exception as e:
            logger.debug(f"Failed to parse instrument: {str(e)}")
            return None
    
    def _determine_instrument_type(self, item: Dict) -> str:
        """Determine instrument type from raw data"""
        symbol = item.get('symbol', '')
        instrument_type = item.get('instrumenttype', '')
        
        if instrument_type == 'OPTIDX' or instrument_type == 'OPTSTK':
            if 'CE' in symbol:
                return InstrumentType.CALL_OPTION.value
            elif 'PE' in symbol:
                return InstrumentType.PUT_OPTION.value
        elif instrument_type == 'FUTIDX' or instrument_type == 'FUTSTK':
            return InstrumentType.FUTURES.value
        elif instrument_type == 'AMXIDX':
            return InstrumentType.INDEX.value
        
        # Default to equity
        return InstrumentType.EQUITY.value
    
    def get_token(self, symbol: str, exchange: str = "NSE") -> str:
        """
        Get symbol token for trading
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE-EQ", "NIFTY")
            exchange: Exchange code (NSE, BSE, NFO, MCX)
        
        Returns:
            Symbol token string
        
        Raises:
            SymbolNotFoundError: If symbol not found
        """
        symbol_info = self.get_symbol_info(symbol, exchange)
        return symbol_info.token
    
    def get_symbol_info(self, symbol: str, exchange: str = "NSE") -> SymbolInfo:
        """
        Get full symbol information
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
        
        Returns:
            SymbolInfo object
        
        Raises:
            SymbolNotFoundError: If symbol not found
        """
        if not self._loaded:
            raise SymbolNotFoundError(
                symbol=symbol,
                exchange=exchange,
                message=f"Instruments not loaded. Call load_instruments() first."
            )
        
        exchange = exchange.upper()
        
        if exchange not in self._instruments:
            raise SymbolNotFoundError(
                symbol=symbol,
                exchange=exchange,
                message=f"Invalid exchange '{exchange}'. Valid: NSE, BSE, NFO, MCX, CDS, BFO"
            )
        
        # Try exact match first
        if symbol in self._instruments[exchange]:
            return self._instruments[exchange][symbol]
        
        # Try with -EQ suffix for equity
        if exchange in ["NSE", "BSE"]:
            eq_symbol = f"{symbol}-EQ"
            if eq_symbol in self._instruments[exchange]:
                return self._instruments[exchange][eq_symbol]
        
        # Try uppercase
        symbol_upper = symbol.upper()
        if symbol_upper in self._instruments[exchange]:
            return self._instruments[exchange][symbol_upper]
        
        # Search by name
        for sym, info in self._instruments[exchange].items():
            if info.name.upper() == symbol_upper:
                return info
        
        raise SymbolNotFoundError(symbol=symbol, exchange=exchange)
    
    def search_symbol(self, query: str, exchange: str = None, limit: int = 10) -> List[SymbolInfo]:
        """
        Search symbols by name or symbol
        
        Args:
            query: Search query
            exchange: Optional exchange filter
            limit: Maximum results to return
        
        Returns:
            List of matching SymbolInfo objects
        """
        if not self._loaded:
            return []
        
        query = query.upper()
        results = []
        
        exchanges = [exchange.upper()] if exchange else list(self._instruments.keys())
        
        for exch in exchanges:
            if exch not in self._instruments:
                continue
            
            for symbol, info in self._instruments[exch].items():
                if query in symbol.upper() or query in info.name.upper():
                    results.append(info)
                    if len(results) >= limit:
                        return results
        
        return results
    
    def get_equity_symbol(self, name: str, exchange: str = "NSE") -> SymbolInfo:
        """
        Get equity symbol info
        
        Args:
            name: Stock name (e.g., "RELIANCE", "TCS")
            exchange: NSE or BSE
        
        Returns:
            SymbolInfo for equity
        """
        # Try with -EQ suffix
        try:
            return self.get_symbol_info(f"{name}-EQ", exchange)
        except SymbolNotFoundError:
            pass
        
        # Try without suffix
        return self.get_symbol_info(name, exchange)
    
    def get_futures_symbol(
        self, 
        name: str, 
        expiry: str = None,
        exchange: str = "NFO"
    ) -> SymbolInfo:
        """
        Get futures symbol info
        
        Args:
            name: Underlying name (e.g., "NIFTY", "BANKNIFTY", "RELIANCE")
            expiry: Expiry date string (optional, returns nearest if not specified)
            exchange: NFO or MCX
        
        Returns:
            SymbolInfo for futures
        """
        if not self._loaded:
            raise SymbolNotFoundError(
                symbol=name,
                exchange=exchange,
                message="Instruments not loaded"
            )
        
        # Search for futures
        futures = []
        for symbol, info in self._instruments[exchange].items():
            if info.instrument_type == InstrumentType.FUTURES.value:
                if name.upper() in symbol.upper() or name.upper() in info.name.upper():
                    futures.append(info)
        
        if not futures:
            raise SymbolNotFoundError(
                symbol=name,
                exchange=exchange,
                message=f"No futures found for '{name}'"
            )
        
        # Filter by expiry if specified
        if expiry:
            for f in futures:
                if f.expiry and expiry in f.expiry:
                    return f
        
        # Return first (nearest expiry typically)
        return futures[0]
    
    def get_option_symbol(
        self,
        name: str,
        strike: float,
        option_type: str,  # "CE" or "PE"
        expiry: str = None,
        exchange: str = "NFO"
    ) -> SymbolInfo:
        """
        Get option symbol info
        
        Args:
            name: Underlying name (e.g., "NIFTY", "BANKNIFTY")
            strike: Strike price
            option_type: "CE" for Call, "PE" for Put
            expiry: Expiry date string
            exchange: NFO or BFO
        
        Returns:
            SymbolInfo for option
        """
        if not self._loaded:
            raise SymbolNotFoundError(
                symbol=name,
                exchange=exchange,
                message="Instruments not loaded"
            )
        
        option_type = option_type.upper()
        if option_type not in ["CE", "PE"]:
            raise ValueError(f"Invalid option type: {option_type}. Use 'CE' or 'PE'")
        
        # Search for options
        for symbol, info in self._instruments[exchange].items():
            if info.option_type == option_type:
                if name.upper() in symbol.upper() or name.upper() in info.name.upper():
                    if info.strike and abs(info.strike - strike) < 0.01:
                        if expiry is None or (info.expiry and expiry in info.expiry):
                            return info
        
        raise SymbolNotFoundError(
            symbol=f"{name} {strike} {option_type}",
            exchange=exchange,
            message=f"Option not found: {name} {strike} {option_type}"
        )
    
    @property
    def is_loaded(self) -> bool:
        """Check if instruments are loaded"""
        return self._loaded
    
    def get_instrument_count(self, exchange: str = None) -> int:
        """Get count of loaded instruments"""
        if exchange:
            return len(self._instruments.get(exchange.upper(), {}))
        return sum(len(v) for v in self._instruments.values())
