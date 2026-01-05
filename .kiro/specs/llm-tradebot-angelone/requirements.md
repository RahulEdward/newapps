# Requirements Document

## Introduction

LLM-TradeBot ka AngelOne version - Original LLM-TradeBot repository ko fork karke Binance/Crypto trading ko hatakar AngelOne (Indian Stock Broker) integration karna hai. Saare 12 AI agents, LLM integrations, strategy engine, backtesting, aur web dashboard same rahenge - sirf broker layer change hogi.

**Key Principle:** Features, functions, agents, LLM output - sab same rahega. Sirf data source aur order execution AngelOne ke through hoga.

## Glossary

- **LLM_TradeBot**: Original multi-agent AI trading system jo Binance use karta hai
- **AngelOne_Client**: New broker client jo AngelOne SmartAPI use karega
- **SmartAPI**: AngelOne ka official Python SDK for trading
- **TOTP**: Time-based One-Time Password for AngelOne authentication
- **NSE**: National Stock Exchange of India
- **BSE**: Bombay Stock Exchange
- **NFO**: NSE Futures & Options segment
- **MCX**: Multi Commodity Exchange
- **Symbol_Token**: AngelOne ka unique identifier for each tradable instrument
- **Feed_Token**: AngelOne WebSocket authentication token
- **Data_Sync_Agent**: Agent responsible for fetching market data
- **Quant_Analyst_Agent**: Agent for technical analysis
- **Decision_Core_Agent**: Agent for trade execution decisions
- **Market_Hours**: Indian market trading hours (9:15 AM - 3:30 PM IST)

## Requirements

### Requirement 1: AngelOne Authentication System

**User Story:** As a trader, I want to authenticate with AngelOne broker, so that I can access my trading account securely.

#### Acceptance Criteria

1. WHEN the system starts, THE AngelOne_Client SHALL authenticate using API key, client code, password, and TOTP
2. WHEN TOTP is required, THE AngelOne_Client SHALL generate TOTP automatically using pyotp library
3. WHEN authentication succeeds, THE AngelOne_Client SHALL store JWT token, refresh token, and feed token
4. IF authentication fails, THEN THE AngelOne_Client SHALL retry with exponential backoff up to 3 times
5. WHEN JWT token expires, THE AngelOne_Client SHALL automatically refresh the session
6. THE AngelOne_Client SHALL validate all credentials before attempting connection

### Requirement 2: Market Data Fetching (Replace Binance Data)

**User Story:** As a trader, I want to fetch real-time and historical market data from AngelOne, so that AI agents can analyze Indian stocks.

#### Acceptance Criteria

1. WHEN Data_Sync_Agent requests historical data, THE AngelOne_Client SHALL fetch candle data using getCandleData API
2. WHEN Data_Sync_Agent requests live data, THE AngelOne_Client SHALL connect to AngelOne WebSocket
3. THE AngelOne_Client SHALL support multiple intervals: ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, ONE_HOUR, ONE_DAY
4. THE AngelOne_Client SHALL support multiple exchanges: NSE, BSE, NFO, MCX
5. WHEN fetching data, THE AngelOne_Client SHALL convert AngelOne data format to match original LLM-TradeBot format
6. IF market is closed, THEN THE AngelOne_Client SHALL return cached data or last available data
7. THE AngelOne_Client SHALL handle rate limits by implementing request throttling

### Requirement 3: Symbol Management System

**User Story:** As a trader, I want to trade Indian stocks and derivatives using familiar symbol names, so that I can easily configure trading pairs.

#### Acceptance Criteria

1. WHEN system initializes, THE Symbol_Manager SHALL load AngelOne instrument master file
2. THE Symbol_Manager SHALL map trading symbols to AngelOne symbol tokens
3. WHEN a symbol is requested, THE Symbol_Manager SHALL return correct symbol token and exchange
4. THE Symbol_Manager SHALL support equity symbols (RELIANCE-EQ, TCS-EQ)
5. THE Symbol_Manager SHALL support futures symbols (NIFTY futures, BANKNIFTY futures)
6. THE Symbol_Manager SHALL support options symbols (NIFTY CE/PE, stock options)
7. IF symbol not found, THEN THE Symbol_Manager SHALL raise descriptive error

### Requirement 4: Order Execution System

**User Story:** As a trader, I want to place, modify, and cancel orders through AngelOne, so that AI agents can execute trading decisions.

#### Acceptance Criteria

1. WHEN Decision_Core_Agent generates BUY signal, THE AngelOne_Client SHALL place buy order
2. WHEN Decision_Core_Agent generates SELL signal, THE AngelOne_Client SHALL place sell order
3. THE AngelOne_Client SHALL support order types: MARKET, LIMIT, SL (Stop Loss), SL-M (Stop Loss Market)
4. THE AngelOne_Client SHALL support product types: INTRADAY, DELIVERY, CARRYFORWARD
5. WHEN order is placed, THE AngelOne_Client SHALL return order ID and status
6. WHEN order modification is requested, THE AngelOne_Client SHALL modify existing order
7. WHEN order cancellation is requested, THE AngelOne_Client SHALL cancel the order
8. IF order placement fails, THEN THE AngelOne_Client SHALL return error with reason

### Requirement 5: Position and Portfolio Management

**User Story:** As a trader, I want to view my positions and holdings, so that AI agents can make informed decisions.

#### Acceptance Criteria

1. WHEN position data is requested, THE AngelOne_Client SHALL fetch current positions
2. WHEN holdings data is requested, THE AngelOne_Client SHALL fetch current holdings
3. THE AngelOne_Client SHALL calculate unrealized P&L for open positions
4. THE AngelOne_Client SHALL provide margin available information
5. WHEN portfolio data changes, THE AngelOne_Client SHALL update cached data
6. THE AngelOne_Client SHALL convert position data format to match original LLM-TradeBot format

### Requirement 6: Market Hours Management

**User Story:** As a trader, I want the system to respect Indian market hours, so that trading only happens during valid market sessions.

#### Acceptance Criteria

1. THE Market_Hours_Manager SHALL track Indian market hours (9:15 AM - 3:30 PM IST)
2. WHEN market is closed, THE Market_Hours_Manager SHALL prevent live order placement
3. THE Market_Hours_Manager SHALL handle pre-market session (9:00 AM - 9:15 AM)
4. THE Market_Hours_Manager SHALL handle NSE holidays from official calendar
5. WHEN weekend is detected, THE Market_Hours_Manager SHALL mark market as closed
6. THE Market_Hours_Manager SHALL provide next market open time when closed
7. WHILE market is closed, THE system SHALL allow backtesting and analysis

### Requirement 7: Data Format Conversion Layer

**User Story:** As a developer, I want data formats to be consistent with original LLM-TradeBot, so that all AI agents work without modification.

#### Acceptance Criteria

1. THE Data_Converter SHALL convert AngelOne candle data to Binance-compatible format
2. THE Data_Converter SHALL convert AngelOne order response to original format
3. THE Data_Converter SHALL convert AngelOne position data to original format
4. THE Data_Converter SHALL convert AngelOne WebSocket data to original format
5. WHEN conversion happens, THE Data_Converter SHALL preserve all required fields
6. IF data field is missing, THEN THE Data_Converter SHALL use sensible defaults

### Requirement 8: Configuration Management

**User Story:** As a trader, I want to configure AngelOne credentials and trading parameters, so that I can customize the system.

#### Acceptance Criteria

1. THE Config_Manager SHALL load AngelOne credentials from config file
2. THE Config_Manager SHALL support environment variables for sensitive data
3. THE Config_Manager SHALL validate all required configuration fields
4. THE Config_Manager SHALL provide default values for optional fields
5. IF configuration is invalid, THEN THE Config_Manager SHALL raise descriptive error
6. THE Config_Manager SHALL support multiple trading symbols configuration
7. THE Config_Manager SHALL support exchange selection (NSE, BSE, NFO, MCX)

### Requirement 9: WebSocket Live Data Stream

**User Story:** As a trader, I want real-time price updates, so that AI agents can react to market changes instantly.

#### Acceptance Criteria

1. WHEN live trading starts, THE WebSocket_Manager SHALL connect to AngelOne WebSocket
2. THE WebSocket_Manager SHALL subscribe to configured symbols
3. WHEN price update received, THE WebSocket_Manager SHALL notify Data_Sync_Agent
4. IF WebSocket disconnects, THEN THE WebSocket_Manager SHALL reconnect automatically
5. THE WebSocket_Manager SHALL handle heartbeat messages
6. WHEN market closes, THE WebSocket_Manager SHALL disconnect gracefully

### Requirement 10: Error Handling and Logging

**User Story:** As a trader, I want comprehensive error handling, so that the system handles failures gracefully.

#### Acceptance Criteria

1. WHEN API error occurs, THE AngelOne_Client SHALL log error with details
2. WHEN network error occurs, THE AngelOne_Client SHALL retry with backoff
3. IF rate limit exceeded, THEN THE AngelOne_Client SHALL wait and retry
4. THE system SHALL log all order placements and executions
5. THE system SHALL log all authentication events
6. IF critical error occurs, THEN THE system SHALL notify user and stop trading

### Requirement 11: Preserve All AI Agents Functionality

**User Story:** As a trader, I want all 12 AI agents to work exactly as before, so that trading intelligence remains unchanged.

#### Acceptance Criteria

1. THE Data_Sync_Agent SHALL receive market data in expected format
2. THE Quant_Analyst_Agent SHALL calculate indicators without modification
3. THE Predict_Agent SHALL generate predictions without modification
4. THE Decision_Core_Agent SHALL make decisions without modification
5. THE Risk_Audit_Agent SHALL evaluate risk without modification
6. THE Regime_Detector SHALL detect market regimes without modification
7. THE Reflection_Agent SHALL analyze performance without modification
8. THE Bull_Agent and Bear_Agent SHALL provide analysis without modification
9. THE Debate_Agent SHALL synthesize views without modification
10. THE Portfolio_Manager_Agent SHALL manage portfolio without modification
11. THE Execution_Agent SHALL receive orders in expected format
12. THE News_Agent SHALL process news without modification

### Requirement 12: Backtesting Compatibility

**User Story:** As a trader, I want to backtest strategies on Indian market data, so that I can validate trading strategies.

#### Acceptance Criteria

1. THE Backtest_Engine SHALL work with AngelOne historical data
2. THE Backtest_Engine SHALL simulate Indian market conditions
3. THE Backtest_Engine SHALL respect market hours in simulation
4. THE Backtest_Engine SHALL calculate realistic brokerage and taxes
5. WHEN backtesting, THE system SHALL use converted data format

### Requirement 13: UI Preservation (No Changes)

**User Story:** As a trader, I want the web dashboard to remain exactly the same, so that my user experience is unchanged.

#### Acceptance Criteria

1. THE Web_Dashboard SHALL keep all buttons exactly as original
2. THE Web_Dashboard SHALL keep all layouts exactly as original
3. THE Web_Dashboard SHALL keep all styling exactly as original
4. THE Web_Dashboard SHALL keep all charts and visualizations exactly as original
5. THE Web_Dashboard SHALL keep all navigation exactly as original
6. THE Web_Dashboard SHALL only change data source from Binance to AngelOne
7. IF any UI element displays crypto-specific text, THEN THE Web_Dashboard SHALL update only that text to Indian market equivalent
8. THE Web_Dashboard SHALL preserve all agent output displays without modification

### Requirement 14: Chinese Text to English Conversion

**User Story:** As a developer, I want all Chinese comments and text converted to English, so that the codebase is readable for English speakers.

#### Acceptance Criteria

1. THE Codebase SHALL have all Chinese comments converted to English
2. THE Codebase SHALL have all Chinese variable names converted to English
3. THE Codebase SHALL have all Chinese log messages converted to English
4. THE Codebase SHALL have all Chinese error messages converted to English
5. THE Codebase SHALL have all Chinese documentation converted to English
6. THE Codebase SHALL have all Chinese UI text converted to English
7. WHEN converting text, THE system SHALL preserve original meaning accurately
8. THE README files SHALL be in English only
