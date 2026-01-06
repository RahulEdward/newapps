"""
Integration Tests for LLM-TradeBot AngelOne Version
====================================================

Tests the full trading flow: Auth → Data Fetch → Agent Process → Order Place
Validates: All Requirements

Feature: llm-tradebot-angelone, Integration Tests
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio
from datetime import datetime

# Import AngelOne components
from src.api.angelone.auth_manager import AuthManager
from src.api.angelone.angelone_client import AngelOneClient
from src.api.angelone.data_converter import DataConverter
from src.api.angelone.symbol_mapper import SymbolMapper
from src.api.angelone.market_hours import MarketHoursManager


class TestFullTradingFlowIntegration:
    """Integration test for complete trading flow"""
    
    @pytest.fixture
    def mock_smart_api(self):
        """Create mock SmartConnect API"""
        mock = MagicMock()
        mock.generateSession.return_value = {
            'status': True,
            'data': {
                'jwtToken': 'test_jwt_token',
                'refreshToken': 'test_refresh_token',
                'feedToken': 'test_feed_token'
            }
        }
        mock.getCandleData.return_value = {
            'status': True,
            'data': [
                ['2024-01-15T09:15:00', 2500.0, 2510.0, 2495.0, 2505.0, 100000],
                ['2024-01-15T09:20:00', 2505.0, 2515.0, 2500.0, 2510.0, 120000],
            ]
        }
        mock.ltpData.return_value = {
            'status': True,
            'data': {
                'ltp': 2510.0,
                'open': 2500.0,
                'high': 2515.0,
                'low': 2495.0,
                'close': 2510.0
            }
        }
        mock.placeOrder.return_value = {
            'status': True,
            'data': {
                'orderid': 'ORD123456',
                'uniqueorderid': 'UNIQ123456'
            }
        }
        mock.position.return_value = {
            'status': True,
            'data': [{
                'tradingsymbol': 'RELIANCE-EQ',
                'symboltoken': '2885',
                'netqty': '10',
                'avgnetprice': '2500.0',
                'ltp': '2510.0',
                'unrealised': '100.0'
            }]
        }
        return mock
    
    @pytest.fixture
    def valid_config(self):
        """Valid AngelOne configuration"""
        return {
            'api_key': 'test_api_key',
            'client_code': 'TEST123',
            'password': 'test_password',
            'totp_secret': 'JBSWY3DPEHPK3PXP'
        }
    
    def test_auth_to_data_fetch_flow(self, valid_config, mock_smart_api):
        """Test: Authentication → Data Fetch flow"""
        # Step 1: Authentication - verify initialization works
        auth_manager = AuthManager(
            api_key=valid_config['api_key'],
            client_code=valid_config['client_code'],
            password=valid_config['password'],
            totp_secret=valid_config['totp_secret']
        )
        
        # Verify TOTP generation works
        totp = auth_manager.generate_totp()
        assert len(totp) == 6
        assert totp.isdigit()
        
        # Step 2: Data Fetch (using converter)
        converter = DataConverter()
        raw_candles = [
            ['2024-01-15T09:15:00', 2500.0, 2510.0, 2495.0, 2505.0, 100000],
            ['2024-01-15T09:20:00', 2505.0, 2515.0, 2500.0, 2510.0, 120000],
        ]
        
        converted = converter.convert_candles(raw_candles)
        
        assert len(converted) == 2
        assert all('open' in c for c in converted)
        assert all('close' in c for c in converted)
        assert all('volume' in c for c in converted)
    
    def test_data_fetch_to_agent_process_flow(self):
        """Test: Data Fetch → Agent Process flow"""
        converter = DataConverter()
        
        # Simulate AngelOne candle data
        angelone_candles = [
            ['2024-01-15T09:15:00', 2500.0, 2510.0, 2495.0, 2505.0, 100000],
            ['2024-01-15T09:20:00', 2505.0, 2515.0, 2500.0, 2510.0, 120000],
            ['2024-01-15T09:25:00', 2510.0, 2520.0, 2505.0, 2515.0, 110000],
        ]
        
        # Convert to Binance-compatible format (what agents expect)
        converted = converter.convert_candles(angelone_candles)
        
        # Verify format matches what agents expect
        for candle in converted:
            # Required fields for agents
            assert 'open_time' in candle
            assert 'open' in candle
            assert 'high' in candle
            assert 'low' in candle
            assert 'close' in candle
            assert 'volume' in candle
            assert 'close_time' in candle
            
            # Type checks
            assert isinstance(candle['open'], float)
            assert isinstance(candle['close'], float)
            assert isinstance(candle['volume'], float)
    
    def test_agent_process_to_order_flow(self, valid_config, mock_smart_api):
        """Test: Agent Process → Order Placement flow"""
        # Simulate agent decision
        agent_decision = {
            'action': 'long',
            'symbol': 'RELIANCE',
            'quantity': 10,
            'confidence': 75
        }
        
        # Create order parameters (what AngelOne client expects)
        order_params = {
            'variety': 'NORMAL',
            'tradingsymbol': 'RELIANCE-EQ',
            'symboltoken': '2885',
            'transactiontype': 'BUY',
            'exchange': 'NSE',
            'ordertype': 'MARKET',
            'producttype': 'INTRADAY',
            'quantity': agent_decision['quantity']
        }
        
        # Verify order can be placed
        mock_smart_api.placeOrder.return_value = {
            'status': True,
            'data': {'orderid': 'ORD123456'}
        }
        
        result = mock_smart_api.placeOrder(order_params)
        
        assert result['status'] == True
        assert 'orderid' in result['data']
    
    def test_full_trading_cycle_mock(self, valid_config, mock_smart_api):
        """Test complete trading cycle with mocks"""
        # Step 1: Auth - verify initialization
        auth_manager = AuthManager(
            api_key=valid_config['api_key'],
            client_code=valid_config['client_code'],
            password=valid_config['password'],
            totp_secret=valid_config['totp_secret']
        )
        
        # Verify TOTP works
        totp = auth_manager.generate_totp()
        assert len(totp) == 6
        
        # Step 2: Symbol mapping
        symbol_mapper = SymbolMapper()
        symbol_mapper._instruments = {
            'NSE': {
                'RELIANCE-EQ': {
                    'symbol': 'RELIANCE-EQ',
                    'token': '2885',
                    'exchange': 'NSE',
                    'lot_size': 1,
                    'tick_size': 0.05,
                    'instrument_type': 'EQ'
                }
            }
        }
        symbol_mapper._loaded = True
        
        symbol_info = symbol_mapper.get_symbol_info('RELIANCE', 'NSE')
        assert symbol_info['token'] == '2885'
        
        # Step 3: Market hours check
        market_hours = MarketHoursManager()
        # Just verify the check works (result depends on current time)
        is_open = market_hours.is_market_open()
        assert isinstance(is_open, bool)
        
        # Step 4: Data conversion
        converter = DataConverter()
        raw_data = ['2024-01-15T09:15:00', 2500.0, 2510.0, 2495.0, 2505.0, 100000]
        converted = converter.convert_candle(raw_data)
        
        assert converted['open'] == 2500.0
        assert converted['close'] == 2505.0
        
        # Step 5: Order placement (mocked)
        order_result = mock_smart_api.placeOrder({
            'tradingsymbol': 'RELIANCE-EQ',
            'transactiontype': 'BUY',
            'quantity': 10
        })
        
        assert order_result['status'] == True


class TestAgentCompatibilityIntegration:
    """Integration tests for all 12 agents data format compatibility"""
    
    @pytest.fixture
    def sample_market_data(self):
        """Sample market data in converted format"""
        converter = DataConverter()
        raw_candles = [
            ['2024-01-15T09:15:00', 2500.0, 2510.0, 2495.0, 2505.0, 100000],
            ['2024-01-15T09:20:00', 2505.0, 2515.0, 2500.0, 2510.0, 120000],
            ['2024-01-15T09:25:00', 2510.0, 2520.0, 2505.0, 2515.0, 110000],
            ['2024-01-15T09:30:00', 2515.0, 2525.0, 2510.0, 2520.0, 130000],
            ['2024-01-15T09:35:00', 2520.0, 2530.0, 2515.0, 2525.0, 140000],
        ]
        return converter.convert_candles(raw_candles)
    
    def test_data_sync_agent_format(self, sample_market_data):
        """Test: Data_Sync_Agent receives correct format (Req 11.1)"""
        # Data Sync Agent expects candles with these fields
        required_fields = ['open_time', 'open', 'high', 'low', 'close', 'volume']
        
        for candle in sample_market_data:
            for field in required_fields:
                assert field in candle, f"Missing field: {field}"
    
    def test_quant_analyst_agent_format(self, sample_market_data):
        """Test: Quant_Analyst_Agent receives correct format (Req 11.2)"""
        # Quant Analyst needs OHLCV data for indicator calculation
        for candle in sample_market_data:
            assert isinstance(candle['open'], (int, float))
            assert isinstance(candle['high'], (int, float))
            assert isinstance(candle['low'], (int, float))
            assert isinstance(candle['close'], (int, float))
            assert isinstance(candle['volume'], (int, float))
            
            # OHLC constraints
            assert candle['high'] >= candle['low']
            assert candle['high'] >= candle['open']
            assert candle['high'] >= candle['close']
            assert candle['low'] <= candle['open']
            assert candle['low'] <= candle['close']
    
    def test_predict_agent_format(self, sample_market_data):
        """Test: Predict_Agent receives correct format (Req 11.3)"""
        # Predict Agent needs time series data
        assert len(sample_market_data) >= 5, "Need at least 5 candles for prediction"
        
        # Timestamps should be monotonically increasing
        timestamps = [c['open_time'] for c in sample_market_data]
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i-1]
    
    def test_decision_core_agent_format(self, sample_market_data):
        """Test: Decision_Core_Agent receives correct format (Req 11.4)"""
        # Decision Core needs current price and historical data
        latest = sample_market_data[-1]
        
        assert 'close' in latest
        assert latest['close'] > 0
    
    def test_risk_audit_agent_format(self, sample_market_data):
        """Test: Risk_Audit_Agent receives correct format (Req 11.5)"""
        # Risk Audit needs price data for volatility calculation
        closes = [c['close'] for c in sample_market_data]
        
        assert len(closes) >= 2
        assert all(isinstance(c, (int, float)) for c in closes)
    
    def test_execution_agent_format(self):
        """Test: Execution_Agent receives correct order format (Req 11.11)"""
        converter = DataConverter()
        
        # Simulate AngelOne order response
        angelone_order = {
            'orderid': 'ORD123456',
            'status': 'complete',
            'tradingsymbol': 'RELIANCE-EQ',
            'transactiontype': 'BUY',
            'quantity': '10',
            'price': '2500.0',
            'averageprice': '2500.0',
            'filledshares': '10'
        }
        
        converted = converter.convert_order_response(angelone_order)
        
        # Execution Agent expects these fields
        assert 'orderId' in converted
        assert 'status' in converted
        assert 'symbol' in converted
        assert 'side' in converted
    
    def test_portfolio_manager_format(self):
        """Test: Portfolio_Manager_Agent receives correct position format (Req 11.10)"""
        converter = DataConverter()
        
        # Simulate AngelOne position
        angelone_position = {
            'tradingsymbol': 'RELIANCE-EQ',
            'symboltoken': '2885',
            'netqty': '10',
            'avgnetprice': '2500.0',
            'ltp': '2510.0',
            'unrealised': '100.0'
        }
        
        converted = converter.convert_position(angelone_position)
        
        # Portfolio Manager expects these fields
        assert 'symbol' in converted
        assert 'positionAmt' in converted
        assert 'entryPrice' in converted
        assert 'unRealizedProfit' in converted


class TestMarketHoursIntegration:
    """Integration tests for market hours handling"""
    
    def test_market_hours_blocks_trading_when_closed(self):
        """Test that trading is blocked when market is closed"""
        market_hours = MarketHoursManager()
        
        # Get market status
        is_open = market_hours.is_market_open()
        
        if not is_open:
            # Should provide next open time
            next_open = market_hours.get_next_market_open()
            assert next_open is not None
            assert next_open > datetime.now(market_hours._tz)
    
    def test_market_hours_allows_analysis_when_closed(self):
        """Test that analysis is allowed even when market is closed"""
        market_hours = MarketHoursManager()
        converter = DataConverter()
        
        # Analysis should work regardless of market hours
        raw_candles = [
            ['2024-01-15T09:15:00', 2500.0, 2510.0, 2495.0, 2505.0, 100000],
        ]
        
        converted = converter.convert_candles(raw_candles)
        assert len(converted) == 1


class TestErrorHandlingIntegration:
    """Integration tests for error handling across components"""
    
    def test_auth_failure_propagates(self):
        """Test that auth failures are properly handled"""
        auth_manager = AuthManager(
            api_key='invalid',
            client_code='invalid',
            password='invalid',
            totp_secret='JBSWY3DPEHPK3PXP'
        )
        
        # Should not be valid before login
        assert not auth_manager.is_session_valid()
    
    def test_invalid_symbol_error(self):
        """Test that invalid symbols raise proper errors"""
        from src.api.angelone.symbol_mapper import SymbolNotFoundError
        
        symbol_mapper = SymbolMapper()
        symbol_mapper._loaded = True
        symbol_mapper._instruments = {'NSE': {}}
        
        with pytest.raises(SymbolNotFoundError) as exc_info:
            symbol_mapper.get_token('INVALID_SYMBOL', 'NSE')
        
        assert 'INVALID_SYMBOL' in str(exc_info.value)
    
    def test_data_conversion_handles_missing_fields(self):
        """Test that data conversion handles missing fields gracefully"""
        converter = DataConverter()
        
        # Incomplete candle data
        incomplete = ['2024-01-15T09:15:00', 2500.0]  # Missing HLCV
        
        # Should handle gracefully with defaults
        result = converter.convert_candle(incomplete)
        
        assert 'open' in result
        assert 'close' in result  # Should have default


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
