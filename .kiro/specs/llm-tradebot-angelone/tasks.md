# Implementation Plan: LLM-TradeBot AngelOne Version

## Overview

This implementation plan transforms LLM-TradeBot from Binance/Crypto to AngelOne/Indian Stock Market. The approach is to replace the broker layer while keeping all AI agents, LLM integrations, and UI unchanged. Implementation uses Python with smartapi-python library.

## Tasks

- [x] 1. Fork and Setup Project
  - [x] 1.1 Clone LLM-TradeBot repository to new folder `LLM-TradeBot-AngelOne`
    - Clone from https://github.com/EthanAlgoX/LLM-TradeBot
    - _Requirements: Project Setup_
  - [x] 1.2 Remove Binance dependencies from requirements.txt
    - Remove python-binance, binance-connector
    - Add smartapi-python>=1.3.0, pyotp>=2.8.0, pytz>=2023.3
    - _Requirements: 8.1_
  - [x] 1.3 Create new directory structure for AngelOne modules
    - Create src/api/angelone/ directory
    - _Requirements: Project Setup_

- [x] 2. Implement Authentication Manager
  - [x] 2.1 Create auth_manager.py with TOTP generation
    - Implement AuthManager class with login, refresh, validate methods
    - Use pyotp for TOTP generation
    - Store JWT token, refresh token, feed token
    - _Requirements: 1.1, 1.2, 1.3, 1.5_
  - [x] 2.2 Write property test for TOTP generation
    - **Property 1: TOTP Generation Validity**
    - **Validates: Requirements 1.2**
  - [x] 2.3 Write unit tests for authentication flow
    - Test valid/invalid credentials
    - Test session refresh
    - _Requirements: 1.4, 1.6_

- [x] 3. Implement Symbol Mapper
  - [x] 3.1 Create symbol_mapper.py with instrument loading
    - Implement SymbolMapper class
    - Load AngelOne instrument master file
    - Map symbols to tokens for NSE, BSE, NFO, MCX
    - _Requirements: 3.1, 3.2, 3.3_
  - [x] 3.2 Add support for equity, futures, and options symbols
    - Handle RELIANCE-EQ, TCS-EQ format for equity
    - Handle NIFTY futures, BANKNIFTY futures
    - Handle options with CE/PE suffix
    - _Requirements: 3.4, 3.5, 3.6_
  - [x] 3.3 Write property test for symbol mapping
    - **Property 7: Symbol Token Mapping**
    - **Property 8: Symbol Type Support**
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.5, 3.6**
  - [x] 3.4 Write property test for invalid symbol handling
    - **Property 9: Invalid Symbol Error**
    - **Validates: Requirements 3.7**

- [x] 4. Implement Market Hours Manager
  - [x] 4.1 Create market_hours.py with Indian market timing
    - Implement MarketHoursManager class
    - Define market hours 9:15 AM - 3:30 PM IST
    - Handle pre-market session 9:00 AM - 9:15 AM
    - _Requirements: 6.1, 6.3_
  - [x] 4.2 Add NSE holiday calendar and weekend handling
    - Load NSE holiday list
    - Detect weekends as closed
    - Calculate next market open time
    - _Requirements: 6.4, 6.5, 6.6_
  - [x] 4.3 Write property test for market hours detection
    - **Property 14: Market Hours Detection**
    - **Property 15: Next Market Open Calculation**
    - **Validates: Requirements 6.1, 6.2, 6.4, 6.5, 6.6**

- [x] 5. Checkpoint - Core Infrastructure
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Data Converter
  - [x] 6.1 Create data_converter.py with format conversion methods
    - Implement DataConverter class
    - Convert AngelOne candle to Binance format
    - Convert ticker, order response, position data
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [x] 6.2 Add field preservation and default value handling
    - Ensure all required fields present
    - Use sensible defaults for missing fields
    - _Requirements: 7.5, 7.6_
  - [x] 6.3 Write property test for candle data conversion
    - **Property 4: Candle Data Format Conversion**
    - **Validates: Requirements 2.5, 7.1**
  - [x] 6.4 Write property test for field preservation
    - **Property 16: Data Converter Field Preservation**
    - **Property 17: Missing Field Defaults**
    - **Validates: Requirements 7.5, 7.6**

- [x] 7. Implement AngelOne Client (Core)
  - [x] 7.1 Create angelone_client.py with main broker interface
    - Implement AngelOneClient class
    - Initialize SmartConnect with auth manager
    - Provide same interface as original Binance client
    - _Requirements: 1.1, 2.1_
  - [x] 7.2 Implement historical data fetching (get_klines)
    - Use getCandleData API
    - Support all intervals (ONE_MINUTE to ONE_DAY)
    - Convert response to Binance format
    - _Requirements: 2.1, 2.3, 2.5_
  - [x] 7.3 Implement current price fetching (get_ticker_price)
    - Get LTP from AngelOne
    - Convert to Binance ticker format
    - _Requirements: 2.1_
  - [x] 7.4 Write property test for interval and exchange support
    - **Property 5: Interval Support**
    - **Property 6: Exchange Support**
    - **Validates: Requirements 2.3, 2.4**

- [x] 8. Implement Order Execution
  - [x] 8.1 Implement order placement (create_order)
    - Support BUY/SELL transactions
    - Support MARKET, LIMIT, SL, SL-M order types
    - Support INTRADAY, DELIVERY, CARRYFORWARD products
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [x] 8.2 Implement order modification and cancellation
    - Modify existing orders
    - Cancel orders by order ID
    - _Requirements: 4.6, 4.7_
  - [x] 8.3 Implement order response handling
    - Return order ID and status
    - Handle order rejection with error details
    - _Requirements: 4.5, 4.8_
  - [x] 8.4 Write property test for order types
    - **Property 10: Order Type Support**
    - **Property 11: Order Response Format**
    - **Validates: Requirements 4.3, 4.5**

- [x] 9. Implement Position and Portfolio Management
  - [x] 9.1 Implement position and holdings fetching
    - Get current positions
    - Get current holdings
    - Get margin available
    - _Requirements: 5.1, 5.2, 5.4_
  - [x] 9.2 Implement P&L calculation and data conversion
    - Calculate unrealized P&L
    - Convert position data to original format
    - _Requirements: 5.3, 5.6_
  - [x] 9.3 Write property test for P&L calculation
    - **Property 12: P&L Calculation**
    - **Property 13: Position Data Conversion**
    - **Validates: Requirements 5.3, 5.6**

- [x] 10. Checkpoint - Broker Integration Complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement WebSocket Manager
  - [x] 11.1 Create websocket_manager.py for live data
    - Implement WebSocketManager class
    - Connect to AngelOne WebSocket
    - Subscribe to configured symbols
    - _Requirements: 9.1, 9.2_
  - [x] 11.2 Implement message handling and reconnection
    - Handle price updates and notify agents
    - Handle heartbeat messages
    - Auto-reconnect on disconnect
    - Graceful disconnect at market close
    - _Requirements: 9.3, 9.4, 9.5, 9.6_

- [x] 12. Implement Configuration Manager
  - [x] 12.1 Create config_manager.py with AngelOne config structure
    - Load config from YAML file
    - Support environment variables for secrets
    - Validate required fields
    - _Requirements: 8.1, 8.2, 8.3_
  - [x] 12.2 Add default values and multi-symbol support
    - Provide defaults for optional fields
    - Support multiple trading symbols
    - Support exchange selection
    - _Requirements: 8.4, 8.6, 8.7_
  - [x] 12.3 Write property test for config validation
    - **Property 18: Config Validation**
    - **Property 19: Environment Variable Resolution**
    - **Validates: Requirements 8.2, 8.3, 8.5**

- [x] 13. Implement Error Handling
  - [x] 13.1 Create error classes and logging
    - Define AngelOneError with error codes
    - Log all API errors with details
    - Log all order placements and auth events
    - _Requirements: 10.1, 10.4, 10.5_
  - [x] 13.2 Implement retry logic and rate limiting
    - Retry network errors with exponential backoff
    - Handle rate limit exceeded
    - Stop trading on critical errors
    - _Requirements: 10.2, 10.3, 10.6_

- [x] 14. Checkpoint - All New Components Complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Update Existing Agents (Minimal Changes)
  - [x] 15.1 Update data_sync_agent.py to use AngelOne client
    - Replace Binance client import with AngelOne client
    - Use converted data format (no logic changes)
    - _Requirements: 11.1_
  - [x] 15.2 Update decision_core_agent.py to use AngelOne client
    - Replace order execution calls
    - Use same signal format (no logic changes)
    - _Requirements: 11.4_
  - [x] 15.3 Update execution_agent.py to use AngelOne client
    - Replace order placement calls
    - Use converted order format
    - _Requirements: 11.11_
  - [x] 15.4 Update portfolio_manager.py to use AngelOne client
    - Replace position/holdings calls
    - Use converted position format
    - _Requirements: 11.10_
  - [x] 15.5 Write property test for agent data format compatibility
    - **Property 20: Agent Data Format Compatibility**
    - **Validates: Requirements 11.1-11.12**

- [x] 16. Update Backtesting Engine
  - [x] 16.1 Update backtest engine for Indian market
    - Use AngelOne historical data
    - Respect market hours in simulation
    - Calculate Indian brokerage and taxes
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [-] 17. Convert Chinese Text to English
  - [x] 17.1 Convert all Chinese comments to English
    - Scan all .py files for Chinese characters
    - Translate comments to English
    - _Requirements: 14.1_
  - [ ] 17.2 Convert Chinese variable names and strings
    - Find Chinese variable names
    - Translate to English equivalents
    - _Requirements: 14.2, 14.3, 14.4_
  - [ ] 17.3 Convert Chinese UI text and documentation
    - Update any Chinese text in web files
    - Update README files to English
    - _Requirements: 14.5, 14.6, 14.8_
  - [ ] 17.4 Write property test for no Chinese characters
    - **Property 21: No Chinese Characters in Codebase**
    - **Validates: Requirements 14.1-14.8**

- [ ] 18. Update Configuration Files
  - [ ] 18.1 Create new config.yaml template for AngelOne
    - Add AngelOne credential fields
    - Add Indian market symbol examples
    - Add market hours configuration
    - _Requirements: 8.1, 8.6, 8.7_
  - [ ] 18.2 Create .env.example for sensitive credentials
    - Add ANGELONE_API_KEY, CLIENT_CODE, PASSWORD, TOTP_SECRET
    - _Requirements: 8.2_

- [ ] 19. Update main.py Entry Point
  - [ ] 19.1 Update main.py to initialize AngelOne client
    - Replace Binance client initialization
    - Add market hours check before trading
    - _Requirements: 1.1, 6.2, 6.7_

- [ ] 20. Final Checkpoint - Full Integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 21. Integration Testing
  - [ ] 21.1 Write integration test for full trading flow
    - Test: Auth → Data Fetch → Agent Process → Order Place
    - _Requirements: All_
  - [ ] 21.2 Write integration test for all 12 agents
    - Verify each agent receives correct data format
    - _Requirements: 11.1-11.12_

- [ ] 22. Documentation Update
  - [ ] 22.1 Update README.md for AngelOne version
    - Add AngelOne setup instructions
    - Add Indian market specific notes
    - Remove Binance/crypto references
    - _Requirements: 14.8_

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- UI remains completely unchanged (Requirement 13)
- All 12 AI agents work without modification - only data source changes
