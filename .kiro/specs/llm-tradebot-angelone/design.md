# Design Document: LLM-TradeBot AngelOne Version

## Overview

This design document describes how to transform the original LLM-TradeBot (Binance/Crypto) into an AngelOne-integrated version for Indian stock market trading. The core principle is **minimal change** - all 12 AI agents, LLM integrations, strategy engine, and web dashboard remain exactly the same. Only the broker layer (data fetching + order execution) changes from Binance to AngelOne.

### Design Goals

1. **Zero Agent Modification** - All 12 AI agents work without any code changes
2. **Zero UI Modification** - Web dashboard buttons, layouts, charts remain identical
3. **Data Format Compatibility** - AngelOne data converted to match original Binance format
4. **Chinese to English** - All Chinese text converted to English
5. **Full AngelOne Integration** - Authentication, data, orders, positions, WebSocket

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        UNCHANGED LAYER                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ LLM Engine  │ │ 12 AI Agents│ │  Strategy   │ │ Web Dashboard│   │
│  │ (Same)      │ │ (Same)      │ │  (Same)     │ │ (Same)      │   │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘   │
│         │               │               │               │           │
│         └───────────────┴───────────────┴───────────────┘           │
│                                 │                                    │
│                    ┌────────────▼────────────┐                      │
│                    │   Data Format Adapter   │                      │
│                    │   (Conversion Layer)    │                      │
│                    └────────────┬────────────┘                      │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
┌─────────────────────────────────┼───────────────────────────────────┐
│                        NEW LAYER                                     │
│                    ┌────────────▼────────────┐                      │
│                    │   AngelOne Client       │                      │
│                    │   (Replace Binance)     │                      │
│                    └────────────┬────────────┘                      │
│         ┌───────────────────────┼───────────────────────┐           │
│         │                       │                       │           │
│  ┌──────▼──────┐  ┌─────────────▼─────────────┐  ┌─────▼─────┐     │
│  │ Auth Manager│  │ Market Data Manager       │  │Order Exec │     │
│  │ (TOTP)      │  │ (REST + WebSocket)        │  │Manager    │     │
│  └─────────────┘  └───────────────────────────┘  └───────────┘     │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │Symbol Mapper│  │Market Hours │  │Config Loader│                  │
│  │(NSE/BSE/NFO)│  │Manager      │  │             │                  │
│  └─────────────┘  └─────────────┘  └─────────────┘                  │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │   AngelOne SmartAPI     │
                    │   (External Service)    │
                    └─────────────────────────┘
```

## Architecture

### Component Overview

| Component | Status | Description |
|-----------|--------|-------------|
| LLM Engine | UNCHANGED | OpenAI, DeepSeek, Claude, Qwen, Gemini integrations |
| 12 AI Agents | UNCHANGED | All agents work with converted data format |
| Strategy Engine | UNCHANGED | Bull/Bear analysis, decision making |
| Web Dashboard | UNCHANGED | All UI elements, buttons, charts same |
| Binance Client | REMOVED | Replaced by AngelOne Client |
| AngelOne Client | NEW | Full broker integration |
| Data Converter | NEW | AngelOne → Original format conversion |
| Symbol Mapper | NEW | Indian market symbol management |
| Market Hours Manager | NEW | Indian market timing |

### File Structure Changes

```
LLM-TradeBot-AngelOne/
├── src/
│   ├── api/
│   │   ├── binance_client.py      # REMOVE
│   │   ├── angelone_client.py     # NEW - Main broker client
│   │   ├── auth_manager.py        # NEW - TOTP authentication
│   │   ├── symbol_mapper.py       # NEW - Symbol token mapping
│   │   ├── market_hours.py        # NEW - Market timing
│   │   └── data_converter.py      # NEW - Format conversion
│   │
│   ├── agents/                    # UNCHANGED (all 12 agents)
│   │   ├── data_sync_agent.py     # Minor: use new client
│   │   ├── quant_analyst_agent.py # UNCHANGED
│   │   ├── predict_agent.py       # UNCHANGED
│   │   ├── decision_core_agent.py # Minor: use new client
│   │   ├── risk_audit_agent.py    # UNCHANGED
│   │   ├── regime_detector.py     # UNCHANGED
│   │   ├── reflection_agent.py    # UNCHANGED
│   │   ├── bull_agent.py          # UNCHANGED
│   │   ├── bear_agent.py          # UNCHANGED
│   │   ├── debate_agent.py        # UNCHANGED
│   │   ├── portfolio_manager.py   # Minor: use new client
│   │   └── execution_agent.py     # Minor: use new client
│   │
│   ├── llm/                       # UNCHANGED
│   ├── strategy/                  # UNCHANGED
│   ├── backtest/                  # Minor: use converted data
│   └── server/                    # UNCHANGED
│
├── web/                           # UNCHANGED (UI same)
├── config/
│   └── config.yaml                # MODIFIED: AngelOne credentials
└── main.py                        # Minor: initialize AngelOne client
```

## Components and Interfaces

### 1. AngelOne Client (Core Component)

```python
# src/api/angelone_client.py

class AngelOneClient:
    """
    Main broker client - replaces Binance client
    Provides same interface as original for compatibility
    """
    
    def __init__(self, config: dict):
        self.auth_manager = AuthManager(config)
        self.symbol_mapper = SymbolMapper()
        self.market_hours = MarketHoursManager()
        self.data_converter = DataConverter()
        self.smart_api = None
        
    async def connect(self) -> bool:
        """Authenticate and connect to AngelOne"""
        pass
    
    async def get_klines(self, symbol: str, interval: str, 
                         limit: int = 500) -> List[dict]:
        """
        Get historical candles - SAME INTERFACE as Binance
        Returns data in original format for agent compatibility
        """
        pass
    
    async def get_ticker_price(self, symbol: str) -> dict:
        """Get current price - SAME INTERFACE as Binance"""
        pass
    
    async def create_order(self, symbol: str, side: str, 
                          order_type: str, quantity: float,
                          price: float = None) -> dict:
        """Place order - SAME INTERFACE as Binance"""
        pass
    
    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        """Cancel order - SAME INTERFACE as Binance"""
        pass
    
    async def get_account(self) -> dict:
        """Get account info - SAME INTERFACE as Binance"""
        pass
    
    async def get_open_orders(self, symbol: str = None) -> List[dict]:
        """Get open orders - SAME INTERFACE as Binance"""
        pass
```

### 2. Authentication Manager

```python
# src/api/auth_manager.py

class AuthManager:
    """
    Handles AngelOne authentication with TOTP
    """
    
    def __init__(self, config: dict):
        self.api_key = config['api_key']
        self.client_code = config['client_code']
        self.password = config['password']
        self.totp_secret = config['totp_secret']
        
    def generate_totp(self) -> str:
        """Generate time-based OTP using pyotp"""
        pass
    
    async def login(self) -> dict:
        """
        Login to AngelOne
        Returns: {jwt_token, refresh_token, feed_token}
        """
        pass
    
    async def refresh_session(self) -> dict:
        """Refresh expired JWT token"""
        pass
    
    def is_session_valid(self) -> bool:
        """Check if current session is valid"""
        pass
```

### 3. Symbol Mapper

```python
# src/api/symbol_mapper.py

class SymbolMapper:
    """
    Maps trading symbols to AngelOne symbol tokens
    Handles NSE, BSE, NFO, MCX exchanges
    """
    
    def __init__(self):
        self.instrument_list = {}  # Loaded from AngelOne
        
    async def load_instruments(self) -> None:
        """Load instrument master from AngelOne"""
        pass
    
    def get_token(self, symbol: str, exchange: str = "NSE") -> str:
        """Get symbol token for trading"""
        pass
    
    def get_symbol_info(self, symbol: str) -> dict:
        """
        Get full symbol information
        Returns: {symbol, token, exchange, lot_size, tick_size}
        """
        pass
    
    def search_symbol(self, query: str) -> List[dict]:
        """Search symbols by name"""
        pass
```

### 4. Market Hours Manager

```python
# src/api/market_hours.py

class MarketHoursManager:
    """
    Manages Indian market trading hours
    """
    
    MARKET_OPEN = time(9, 15)   # 9:15 AM IST
    MARKET_CLOSE = time(15, 30) # 3:30 PM IST
    TIMEZONE = 'Asia/Kolkata'
    
    def __init__(self):
        self.holidays = self._load_nse_holidays()
        
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        pass
    
    def is_trading_day(self, date: datetime = None) -> bool:
        """Check if given date is a trading day"""
        pass
    
    def get_next_market_open(self) -> datetime:
        """Get next market opening time"""
        pass
    
    def time_to_market_close(self) -> timedelta:
        """Get time remaining until market close"""
        pass
```

### 5. Data Converter

```python
# src/api/data_converter.py

class DataConverter:
    """
    Converts AngelOne data format to original LLM-TradeBot format
    Ensures all agents receive data in expected format
    """
    
    def convert_candle(self, angelone_candle: dict) -> dict:
        """
        Convert AngelOne candle to Binance format
        
        AngelOne format:
        [timestamp, open, high, low, close, volume]
        
        Output format (Binance-compatible):
        {
            'open_time': timestamp,
            'open': open,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'close_time': timestamp,
            'quote_volume': volume * close,
            'trades': 0,
            'taker_buy_base': 0,
            'taker_buy_quote': 0
        }
        """
        pass
    
    def convert_ticker(self, angelone_ticker: dict) -> dict:
        """Convert AngelOne ticker to Binance format"""
        pass
    
    def convert_order_response(self, angelone_order: dict) -> dict:
        """Convert AngelOne order response to Binance format"""
        pass
    
    def convert_position(self, angelone_position: dict) -> dict:
        """Convert AngelOne position to Binance format"""
        pass
    
    def convert_account(self, angelone_account: dict) -> dict:
        """Convert AngelOne account info to Binance format"""
        pass
```

### 6. WebSocket Manager

```python
# src/api/websocket_manager.py

class WebSocketManager:
    """
    Manages AngelOne WebSocket connection for live data
    """
    
    def __init__(self, auth_manager: AuthManager, 
                 data_converter: DataConverter):
        self.auth = auth_manager
        self.converter = data_converter
        self.callbacks = []
        
    async def connect(self) -> None:
        """Connect to AngelOne WebSocket"""
        pass
    
    async def subscribe(self, symbols: List[str], 
                       exchange: str = "NSE") -> None:
        """Subscribe to symbol updates"""
        pass
    
    async def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribe from symbols"""
        pass
    
    def on_message(self, callback: Callable) -> None:
        """Register callback for price updates"""
        pass
    
    async def disconnect(self) -> None:
        """Gracefully disconnect"""
        pass
```

## Data Models

### Configuration Model

```yaml
# config/config.yaml

broker:
  name: "angelone"
  api_key: "${ANGELONE_API_KEY}"
  client_code: "${ANGELONE_CLIENT_CODE}"
  password: "${ANGELONE_PASSWORD}"
  totp_secret: "${ANGELONE_TOTP_SECRET}"

trading:
  exchange: "NSE"
  symbols:
    - symbol: "RELIANCE"
      exchange: "NSE"
    - symbol: "TCS"
      exchange: "NSE"
    - symbol: "NIFTY"
      exchange: "NFO"
      expiry: "weekly"
  
  default_quantity: 1
  product_type: "INTRADAY"  # INTRADAY, DELIVERY, CARRYFORWARD

market:
  timezone: "Asia/Kolkata"
  pre_market_start: "09:00"
  market_open: "09:15"
  market_close: "15:30"

# LLM settings remain same
llm:
  provider: "openai"
  model: "gpt-4"
  # ... same as original

# Agent settings remain same
agents:
  # ... same as original
```

### Internal Data Models

```python
# Data models for internal use

@dataclass
class Candle:
    """Unified candle format"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class Order:
    """Unified order format"""
    order_id: str
    symbol: str
    side: str  # BUY/SELL
    order_type: str  # MARKET/LIMIT/SL/SL-M
    quantity: float
    price: float
    status: str
    filled_quantity: float
    average_price: float

@dataclass
class Position:
    """Unified position format"""
    symbol: str
    quantity: float
    average_price: float
    current_price: float
    pnl: float
    pnl_percent: float

@dataclass 
class SymbolInfo:
    """Symbol information"""
    symbol: str
    token: str
    exchange: str
    lot_size: int
    tick_size: float
    instrument_type: str  # EQ, FUT, CE, PE
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system - essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*



### Property 1: TOTP Generation Validity
*For any* valid TOTP secret, the generated TOTP SHALL be a 6-digit numeric string that changes every 30 seconds.
**Validates: Requirements 1.2**

### Property 2: Authentication Token Storage
*For any* successful authentication, the client SHALL store non-empty JWT token, refresh token, and feed token.
**Validates: Requirements 1.3**

### Property 3: Credential Validation
*For any* set of credentials with missing or empty required fields (api_key, client_code, password, totp_secret), the client SHALL raise a validation error before attempting connection.
**Validates: Requirements 1.6**

### Property 4: Candle Data Format Conversion
*For any* valid AngelOne candle data, converting to Binance format and back SHALL preserve timestamp, OHLCV values.
**Validates: Requirements 2.5, 7.1**

### Property 5: Interval Support
*For any* interval in {ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, ONE_HOUR, ONE_DAY}, the client SHALL accept and process the request without error.
**Validates: Requirements 2.3**

### Property 6: Exchange Support
*For any* exchange in {NSE, BSE, NFO, MCX}, the client SHALL accept and process the request without error.
**Validates: Requirements 2.4**

### Property 7: Symbol Token Mapping
*For any* valid trading symbol, the Symbol_Manager SHALL return a non-empty symbol token and valid exchange.
**Validates: Requirements 3.2, 3.3**

### Property 8: Symbol Type Support
*For any* equity symbol (ending in -EQ), futures symbol (containing FUT), or options symbol (containing CE/PE), the Symbol_Manager SHALL correctly identify and map the symbol.
**Validates: Requirements 3.4, 3.5, 3.6**

### Property 9: Invalid Symbol Error
*For any* non-existent symbol, the Symbol_Manager SHALL raise a descriptive error containing the symbol name.
**Validates: Requirements 3.7**

### Property 10: Order Type Support
*For any* order type in {MARKET, LIMIT, SL, SL-M}, the client SHALL create a valid order request.
**Validates: Requirements 4.3**

### Property 11: Order Response Format
*For any* successful order placement, the response SHALL contain a non-empty order_id and valid status.
**Validates: Requirements 4.5**

### Property 12: P&L Calculation
*For any* position with quantity, average_price, and current_price, the calculated P&L SHALL equal (current_price - average_price) * quantity.
**Validates: Requirements 5.3**

### Property 13: Position Data Conversion
*For any* AngelOne position data, converting to original format SHALL preserve symbol, quantity, and price fields.
**Validates: Requirements 5.6, 7.3**

### Property 14: Market Hours Detection
*For any* datetime in IST timezone, is_market_open() SHALL return True if and only if: (1) it's a weekday, (2) not a holiday, and (3) time is between 9:15 AM and 3:30 PM.
**Validates: Requirements 6.1, 6.2, 6.4, 6.5**

### Property 15: Next Market Open Calculation
*For any* datetime when market is closed, get_next_market_open() SHALL return a datetime that is: (1) in the future, (2) at 9:15 AM IST, and (3) on a valid trading day.
**Validates: Requirements 6.6**

### Property 16: Data Converter Field Preservation
*For any* data conversion (candle, order, position), all required fields in the output format SHALL be present and non-null.
**Validates: Requirements 7.5**

### Property 17: Missing Field Defaults
*For any* input data with missing optional fields, the converter SHALL use sensible defaults (0 for numbers, empty string for text).
**Validates: Requirements 7.6**

### Property 18: Config Validation
*For any* configuration missing required fields (api_key, client_code, password, totp_secret), loading SHALL raise a validation error listing the missing fields.
**Validates: Requirements 8.3, 8.5**

### Property 19: Environment Variable Resolution
*For any* config value in format "${VAR_NAME}", the Config_Manager SHALL resolve it to the environment variable value.
**Validates: Requirements 8.2**

### Property 20: Agent Data Format Compatibility
*For any* data passed to AI agents, the format SHALL match the original Binance data format expected by agents.
**Validates: Requirements 11.1-11.12**

### Property 21: No Chinese Characters in Codebase
*For any* source file in the codebase, there SHALL be no Chinese characters in comments, strings, or variable names.
**Validates: Requirements 14.1-14.8**

## Error Handling

### Error Categories

| Category | Handling Strategy |
|----------|-------------------|
| Authentication Errors | Retry with TOTP regeneration, max 3 attempts |
| Network Errors | Exponential backoff retry (1s, 2s, 4s) |
| Rate Limit Errors | Wait for specified time, then retry |
| Invalid Symbol | Raise descriptive error, no retry |
| Market Closed | Return cached data or reject order |
| Order Rejection | Log reason, notify user, no retry |
| WebSocket Disconnect | Auto-reconnect with backoff |
| Critical Errors | Stop trading, notify user |

### Error Response Format

```python
class AngelOneError(Exception):
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        
# Error codes
AUTH_FAILED = "AUTH_001"
INVALID_TOTP = "AUTH_002"
SESSION_EXPIRED = "AUTH_003"
INVALID_SYMBOL = "SYMBOL_001"
MARKET_CLOSED = "MARKET_001"
ORDER_REJECTED = "ORDER_001"
RATE_LIMITED = "API_001"
NETWORK_ERROR = "NET_001"
```

## Testing Strategy

### Unit Tests

Unit tests will verify specific examples and edge cases:

1. **Authentication Tests**
   - Valid credentials login
   - Invalid credentials rejection
   - TOTP generation correctness
   - Session refresh flow

2. **Symbol Mapper Tests**
   - Equity symbol mapping
   - Futures symbol mapping
   - Options symbol mapping
   - Invalid symbol handling

3. **Data Converter Tests**
   - Candle format conversion
   - Order response conversion
   - Position data conversion
   - Missing field handling

4. **Market Hours Tests**
   - Market open detection
   - Holiday handling
   - Weekend handling
   - Next open calculation

### Property-Based Tests

Property-based tests will verify universal properties using **hypothesis** library (Python):

```python
# Test configuration
# Minimum 100 iterations per property test
# Tag format: Feature: llm-tradebot-angelone, Property N: description
```

1. **Property 1 Test**: TOTP validity - generate many TOTPs, verify all are 6-digit
2. **Property 4 Test**: Candle conversion round-trip
3. **Property 7 Test**: Symbol mapping returns valid tokens
4. **Property 12 Test**: P&L calculation correctness
5. **Property 14 Test**: Market hours detection accuracy
6. **Property 21 Test**: No Chinese characters in source files

### Integration Tests

1. **End-to-End Flow**: Authentication → Data Fetch → Agent Processing → Order Placement
2. **Agent Compatibility**: Verify all 12 agents receive correct data format
3. **WebSocket Flow**: Connect → Subscribe → Receive → Process → Disconnect

## Implementation Notes

### Dependencies

```
# requirements.txt additions
smartapi-python>=1.3.0
pyotp>=2.8.0
pytz>=2023.3
hypothesis>=6.0.0  # For property-based testing

# Remove
# python-binance
# binance-connector
```

### Migration Checklist

1. [ ] Fork LLM-TradeBot repository
2. [ ] Remove Binance client and dependencies
3. [ ] Add AngelOne client implementation
4. [ ] Add authentication manager with TOTP
5. [ ] Add symbol mapper with instrument loading
6. [ ] Add market hours manager
7. [ ] Add data converter layer
8. [ ] Update config structure
9. [ ] Convert all Chinese text to English
10. [ ] Update agents to use new client (minimal changes)
11. [ ] Update backtesting for Indian market
12. [ ] Write unit tests
13. [ ] Write property-based tests
14. [ ] Integration testing
15. [ ] Documentation update
