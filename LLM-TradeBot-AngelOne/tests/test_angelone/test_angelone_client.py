"""
Tests for AngelOne Client
Includes property-based tests and unit tests

Feature: llm-tradebot-angelone
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import MagicMock, patch
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from api.angelone.angelone_client import AngelOneClient


# =============================================================================
# Mock Classes
# =============================================================================

class MockSmartConnect:
    """Mock SmartConnect for testing"""
    
    def __init__(self, api_key):
        self.api_key = api_key
    
    def generateSession(self, client_code, password, totp):
        return {
            'status': True,
            'data': {
                'jwtToken': 'test_jwt',
                'refreshToken': 'test_refresh'
            }
        }
    
    def getfeedToken(self):
        return 'test_feed_token'
    
    def getCandleData(self, params):
        return {
            'status': True,
            'data': [
                [1704067200000, 100.0, 105.0, 95.0, 102.0, 10000],
                [1704067260000, 102.0, 108.0, 100.0, 106.0, 12000],
            ]
        }
    
    def ltpData(self, exchange, symbol, token):
        return {
            'status': True,
            'data': {
                'ltp': 2500.0,
                'symbol': symbol
            }
        }
    
    def rmsLimit(self):
        return {
            'status': True,
            'data': {
                'net': 100000.0,
                'availablecash': 50000.0
            }
        }
    
    def position(self):
        return {
            'status': True,
            'data': [
                {
                    'tradingsymbol': 'RELIANCE-EQ',
                    'netqty': 10,
                    'avgnetprice': 2500.0,
                    'ltp': 2550.0
                }
            ]
        }
    
    def holding(self):
        return {
            'status': True,
            'data': []
        }
    
    def terminateSession(self, client_code):
        return {'status': True}


# Mock instrument data
MOCK_INSTRUMENTS = [
    {
        "token": "2885",
        "symbol": "RELIANCE-EQ",
        "name": "RELIANCE",
        "expiry": "",
        "strike": "-1",
        "lotsize": "1",
        "instrumenttype": "",
        "exch_seg": "NSE",
        "tick_size": "0.05"
    },
    {
        "token": "35001",
        "symbol": "NIFTY25JANFUT",
        "name": "NIFTY",
        "expiry": "25JAN2025",
        "strike": "-1",
        "lotsize": "50",
        "instrumenttype": "FUTIDX",
        "exch_seg": "NFO",
        "tick_size": "0.05"
    },
]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client():
    """Create AngelOne client"""
    return AngelOneClient(
        api_key="test_api_key",
        client_code="TEST123",
        password="test_password",
        totp_secret="JBSWY3DPEHPK3PXP"
    )


@pytest.fixture
def connected_client(client):
    """Create connected AngelOne client"""
    client.connect_sync(smart_api_class=MockSmartConnect)
    client.symbol_mapper.load_instruments(MOCK_INSTRUMENTS)
    return client


# =============================================================================
# Property-Based Tests
# =============================================================================

class TestIntervalSupportProperty:
    """
    Property 5: Interval Support
    *For any* interval in {ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, ONE_HOUR, ONE_DAY},
    the client SHALL accept and process the request without error.
    
    **Validates: Requirements 2.3**
    """
    
    @given(st.sampled_from([
        '1m', '5m', '15m', '30m', '1h', '1d',
        'ONE_MINUTE', 'FIVE_MINUTE', 'FIFTEEN_MINUTE', 'THIRTY_MINUTE', 'ONE_HOUR', 'ONE_DAY'
    ]))
    @settings(max_examples=100)
    def test_valid_intervals_accepted(self, interval):
        """
        Feature: llm-tradebot-angelone, Property 5: Interval Support
        Valid intervals are accepted without error
        """
        client = AngelOneClient(
            api_key="test",
            client_code="TEST",
            password="test",
            totp_secret="JBSWY3DPEHPK3PXP"
        )
        
        # Should not raise error
        angelone_interval = client._get_angelone_interval(interval)
        
        # Property: Result is a valid AngelOne interval
        valid_intervals = [
            'ONE_MINUTE', 'THREE_MINUTE', 'FIVE_MINUTE', 'TEN_MINUTE',
            'FIFTEEN_MINUTE', 'THIRTY_MINUTE', 'ONE_HOUR', 'ONE_DAY'
        ]
        assert angelone_interval in valid_intervals


class TestExchangeSupportProperty:
    """
    Property 6: Exchange Support
    *For any* exchange in {NSE, BSE, NFO, MCX}, the client SHALL accept 
    and process the request without error.
    
    **Validates: Requirements 2.4**
    """
    
    @given(st.sampled_from(['NSE', 'BSE', 'NFO', 'MCX', 'CDS', 'BFO']))
    @settings(max_examples=100)
    def test_valid_exchanges_accepted(self, exchange):
        """
        Feature: llm-tradebot-angelone, Property 6: Exchange Support
        Valid exchanges are accepted without error
        """
        client = AngelOneClient(
            api_key="test",
            client_code="TEST",
            password="test",
            totp_secret="JBSWY3DPEHPK3PXP"
        )
        
        # Should not raise error
        validated = client._validate_exchange(exchange)
        
        # Property: Exchange is normalized to uppercase
        assert validated == exchange.upper()
    
    @given(st.text(min_size=1, max_size=10, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    @settings(max_examples=50)
    def test_invalid_exchanges_rejected(self, exchange):
        """
        Feature: llm-tradebot-angelone, Property 6: Exchange Support
        Invalid exchanges are rejected
        """
        valid_exchanges = ['NSE', 'BSE', 'NFO', 'MCX', 'CDS', 'BFO']
        
        if exchange.upper() in valid_exchanges:
            return  # Skip valid exchanges
        
        client = AngelOneClient(
            api_key="test",
            client_code="TEST",
            password="test",
            totp_secret="JBSWY3DPEHPK3PXP"
        )
        
        with pytest.raises(ValueError) as exc_info:
            client._validate_exchange(exchange)
        
        assert "Invalid exchange" in str(exc_info.value)


# =============================================================================
# Unit Tests
# =============================================================================

class TestAngelOneClientUnit:
    """Unit tests for AngelOneClient"""
    
    def test_initialization(self, client):
        """Test client initialization"""
        assert client.client_code == "TEST123"
        assert client.default_exchange == "NSE"
        assert client.is_connected == False
    
    def test_connect(self, client):
        """Test connection"""
        client.connect_sync(smart_api_class=MockSmartConnect)
        
        assert client.is_connected == True
    
    def test_disconnect(self, connected_client):
        """Test disconnection"""
        connected_client.disconnect()
        
        assert connected_client.is_connected == False
    
    def test_get_klines(self, connected_client):
        """Test getting historical candles"""
        candles = connected_client.get_klines(
            symbol="RELIANCE-EQ",
            interval="5m",
            limit=100,
            exchange="NSE"
        )
        
        assert len(candles) == 2
        assert candles[0]['open'] == 100.0
        assert candles[0]['close'] == 102.0
    
    def test_get_ticker_price(self, connected_client):
        """Test getting current price"""
        ticker = connected_client.get_ticker_price("RELIANCE-EQ", "NSE")
        
        assert ticker['price'] == 2500.0
        assert ticker['symbol'] == "RELIANCE-EQ"
    
    def test_get_account(self, connected_client):
        """Test getting account info"""
        account = connected_client.get_account()
        
        assert account['totalBalance'] == 100000.0
        assert account['availableBalance'] == 50000.0
    
    def test_get_positions(self, connected_client):
        """Test getting positions"""
        positions = connected_client.get_positions()
        
        assert len(positions) == 1
        assert positions[0]['symbol'] == 'RELIANCE-EQ'
        assert positions[0]['positionAmt'] == 10
    
    def test_interval_conversion(self, client):
        """Test interval conversion"""
        assert client._get_angelone_interval('1m') == 'ONE_MINUTE'
        assert client._get_angelone_interval('5m') == 'FIVE_MINUTE'
        assert client._get_angelone_interval('1h') == 'ONE_HOUR'
        assert client._get_angelone_interval('1d') == 'ONE_DAY'
    
    def test_invalid_interval(self, client):
        """Test invalid interval raises error"""
        with pytest.raises(ValueError) as exc_info:
            client._get_angelone_interval('invalid')
        
        assert "Invalid interval" in str(exc_info.value)
    
    def test_exchange_validation(self, client):
        """Test exchange validation"""
        assert client._validate_exchange('nse') == 'NSE'
        assert client._validate_exchange('NFO') == 'NFO'
    
    def test_invalid_exchange(self, client):
        """Test invalid exchange raises error"""
        with pytest.raises(ValueError) as exc_info:
            client._validate_exchange('INVALID')
        
        assert "Invalid exchange" in str(exc_info.value)
    
    def test_market_hours_check(self, client):
        """Test market hours check"""
        # This will return based on current time
        is_open = client.is_market_open()
        session = client.get_market_session()
        
        assert isinstance(is_open, bool)
        assert session in ['pre_market', 'market', 'post_market', 'closed']
    
    def test_not_connected_error(self, client):
        """Test error when not connected"""
        with pytest.raises(ConnectionError) as exc_info:
            client.get_klines("RELIANCE-EQ", "5m")
        
        assert "Not connected" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
