"""
Tests for Data Converter
Includes property-based tests and unit tests

Feature: llm-tradebot-angelone
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from api.angelone.data_converter import DataConverter


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def converter():
    """Create a DataConverter"""
    return DataConverter()


# =============================================================================
# Property-Based Tests
# =============================================================================

class TestCandleConversionProperty:
    """
    Property 4: Candle Data Format Conversion
    *For any* valid AngelOne candle data, converting to Binance format 
    SHALL preserve timestamp, OHLCV values.
    
    **Validates: Requirements 2.5, 7.1**
    """
    
    @given(
        timestamp=st.integers(min_value=1704067200000, max_value=1735689600000),  # 2024-2025
        open_price=st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        high=st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        low=st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        close=st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        volume=st.floats(min_value=0, max_value=1000000000, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_candle_preserves_ohlcv(self, timestamp, open_price, high, low, close, volume):
        """
        Feature: llm-tradebot-angelone, Property 4: Candle Data Format Conversion
        OHLCV values are preserved after conversion
        """
        converter = DataConverter()
        
        # AngelOne candle format
        angelone_candle = [timestamp, open_price, high, low, close, volume]
        
        # Convert
        binance_candle = converter.convert_candle(angelone_candle)
        
        # Property: OHLCV values preserved
        assert abs(binance_candle['open'] - open_price) < 0.0001
        assert abs(binance_candle['high'] - high) < 0.0001
        assert abs(binance_candle['low'] - low) < 0.0001
        assert abs(binance_candle['close'] - close) < 0.0001
        assert abs(binance_candle['volume'] - volume) < 0.0001


class TestFieldPreservationProperty:
    """
    Property 16: Data Converter Field Preservation
    *For any* data conversion (candle, order, position), all required fields 
    in the output format SHALL be present and non-null.
    
    **Validates: Requirements 7.5**
    """
    
    @given(
        timestamp=st.integers(min_value=1704067200000, max_value=1735689600000),
        price=st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        volume=st.floats(min_value=0, max_value=1000000000, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_candle_has_all_required_fields(self, timestamp, price, volume):
        """
        Feature: llm-tradebot-angelone, Property 16: Field Preservation
        Converted candle has all required fields
        """
        converter = DataConverter()
        
        angelone_candle = [timestamp, price, price + 10, price - 10, price + 5, volume]
        binance_candle = converter.convert_candle(angelone_candle)
        
        # Property: All required fields present
        required_fields = [
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote'
        ]
        
        for field in required_fields:
            assert field in binance_candle, f"Missing field: {field}"
            assert binance_candle[field] is not None, f"Field {field} is None"
    
    @given(
        order_id=st.text(min_size=1, max_size=20, alphabet='0123456789'),
        symbol=st.text(min_size=1, max_size=20, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ-'),
        quantity=st.floats(min_value=1, max_value=10000, allow_nan=False),
        price=st.floats(min_value=0.01, max_value=100000, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_order_has_all_required_fields(self, order_id, symbol, quantity, price):
        """
        Feature: llm-tradebot-angelone, Property 16: Field Preservation
        Converted order has all required fields
        """
        converter = DataConverter()
        
        angelone_order = {
            'orderid': order_id,
            'tradingsymbol': symbol,
            'orderstatus': 'complete',
            'transactiontype': 'BUY',
            'ordertype': 'MARKET',
            'price': price,
            'quantity': quantity,
            'filledshares': quantity,
            'averageprice': price
        }
        
        binance_order = converter.convert_order_response(angelone_order)
        
        # Property: All required fields present
        required_fields = [
            'orderId', 'symbol', 'status', 'side', 'type',
            'price', 'origQty', 'executedQty', 'avgPrice', 'time'
        ]
        
        for field in required_fields:
            assert field in binance_order, f"Missing field: {field}"
            assert binance_order[field] is not None, f"Field {field} is None"


class TestMissingFieldDefaultsProperty:
    """
    Property 17: Missing Field Defaults
    *For any* input data with missing optional fields, the converter SHALL 
    use sensible defaults (0 for numbers, empty string for text).
    
    **Validates: Requirements 7.6**
    """
    
    @given(
        order_id=st.text(min_size=1, max_size=20, alphabet='0123456789'),
        symbol=st.text(min_size=1, max_size=20, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ-')
    )
    @settings(max_examples=100)
    def test_missing_fields_get_defaults(self, order_id, symbol):
        """
        Feature: llm-tradebot-angelone, Property 17: Missing Field Defaults
        Missing fields get sensible defaults
        """
        converter = DataConverter()
        
        # Minimal order with missing fields
        angelone_order = {
            'orderid': order_id,
            'tradingsymbol': symbol,
            'orderstatus': 'complete',
            'transactiontype': 'BUY'
            # Missing: price, quantity, filledshares, averageprice
        }
        
        binance_order = converter.convert_order_response(angelone_order)
        
        # Property: Missing numeric fields default to 0
        assert binance_order['price'] == 0.0
        assert binance_order['origQty'] == 0.0
        assert binance_order['executedQty'] == 0.0
        assert binance_order['avgPrice'] == 0.0


class TestPositionConversionProperty:
    """
    Property 13: Position Data Conversion
    *For any* AngelOne position data, converting to original format SHALL 
    preserve symbol, quantity, and price fields.
    
    **Validates: Requirements 5.6, 7.3**
    """
    
    @given(
        symbol=st.text(min_size=1, max_size=20, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ-'),
        quantity=st.floats(min_value=-10000, max_value=10000, allow_nan=False),
        entry_price=st.floats(min_value=0.01, max_value=100000, allow_nan=False),
        current_price=st.floats(min_value=0.01, max_value=100000, allow_nan=False)
    )
    @settings(max_examples=100)
    def test_position_preserves_values(self, symbol, quantity, entry_price, current_price):
        """
        Feature: llm-tradebot-angelone, Property 13: Position Data Conversion
        Position values are preserved after conversion
        """
        converter = DataConverter()
        
        angelone_position = {
            'tradingsymbol': symbol,
            'netqty': quantity,
            'avgnetprice': entry_price,
            'ltp': current_price
        }
        
        binance_position = converter.convert_position(angelone_position)
        
        # Property: Values preserved
        assert binance_position['symbol'] == symbol
        assert abs(binance_position['positionAmt'] - quantity) < 0.0001
        assert abs(binance_position['entryPrice'] - entry_price) < 0.0001
        assert abs(binance_position['markPrice'] - current_price) < 0.0001


# =============================================================================
# Unit Tests
# =============================================================================

class TestDataConverterUnit:
    """Unit tests for DataConverter"""
    
    def test_convert_candle_basic(self, converter):
        """Test basic candle conversion"""
        angelone_candle = [1704067200000, 100.0, 105.0, 95.0, 102.0, 10000]
        
        result = converter.convert_candle(angelone_candle)
        
        assert result['open'] == 100.0
        assert result['high'] == 105.0
        assert result['low'] == 95.0
        assert result['close'] == 102.0
        assert result['volume'] == 10000
    
    def test_convert_candle_empty(self, converter):
        """Test conversion of empty candle"""
        result = converter.convert_candle([])
        
        assert result['open'] == 0.0
        assert result['close'] == 0.0
    
    def test_convert_candles_list(self, converter):
        """Test conversion of multiple candles"""
        candles = [
            [1704067200000, 100.0, 105.0, 95.0, 102.0, 10000],
            [1704067260000, 102.0, 108.0, 100.0, 106.0, 12000],
        ]
        
        results = converter.convert_candles(candles)
        
        assert len(results) == 2
        assert results[0]['open'] == 100.0
        assert results[1]['open'] == 102.0
    
    def test_convert_ticker(self, converter):
        """Test ticker conversion"""
        angelone_ticker = {
            'ltp': 2500.0,
            'symbol': 'RELIANCE-EQ'
        }
        
        result = converter.convert_ticker(angelone_ticker)
        
        assert result['price'] == 2500.0
        assert result['symbol'] == 'RELIANCE-EQ'
    
    def test_convert_order_complete(self, converter):
        """Test complete order conversion"""
        angelone_order = {
            'orderid': '123456',
            'tradingsymbol': 'RELIANCE-EQ',
            'orderstatus': 'complete',
            'transactiontype': 'BUY',
            'ordertype': 'MARKET',
            'price': 2500.0,
            'quantity': 10,
            'filledshares': 10,
            'averageprice': 2500.0
        }
        
        result = converter.convert_order_response(angelone_order)
        
        assert result['orderId'] == '123456'
        assert result['symbol'] == 'RELIANCE-EQ'
        assert result['status'] == 'FILLED'
        assert result['side'] == 'BUY'
        assert result['origQty'] == 10.0
    
    def test_convert_order_status_mapping(self, converter):
        """Test order status mapping"""
        statuses = {
            'complete': 'FILLED',
            'rejected': 'REJECTED',
            'cancelled': 'CANCELED',
            'open': 'NEW',
            'pending': 'NEW'
        }
        
        for angelone_status, expected_binance in statuses.items():
            order = {'orderid': '1', 'orderstatus': angelone_status}
            result = converter.convert_order_response(order)
            assert result['status'] == expected_binance
    
    def test_convert_position(self, converter):
        """Test position conversion"""
        angelone_position = {
            'tradingsymbol': 'RELIANCE-EQ',
            'netqty': 10,
            'avgnetprice': 2500.0,
            'ltp': 2550.0,
            'unrealised': 500.0
        }
        
        result = converter.convert_position(angelone_position)
        
        assert result['symbol'] == 'RELIANCE-EQ'
        assert result['positionAmt'] == 10
        assert result['entryPrice'] == 2500.0
        assert result['markPrice'] == 2550.0
        assert result['unRealizedProfit'] == 500.0
    
    def test_convert_account(self, converter):
        """Test account conversion"""
        angelone_account = {
            'net': 100000.0,
            'availablecash': 50000.0,
            'unrealised': 5000.0
        }
        
        result = converter.convert_account(angelone_account)
        
        assert result['totalBalance'] == 100000.0
        assert result['availableBalance'] == 50000.0
        assert result['totalUnrealizedProfit'] == 5000.0
    
    def test_convert_websocket_tick(self, converter):
        """Test WebSocket tick conversion"""
        tick = {
            'token': '2885',
            'ltp': 2500.0,
            'open': 2480.0,
            'high': 2520.0,
            'low': 2470.0,
            'close': 2490.0,
            'volume': 1000000
        }
        
        result = converter.convert_websocket_tick(tick, 'RELIANCE-EQ')
        
        assert result['symbol'] == 'RELIANCE-EQ'
        assert result['price'] == 2500.0
        assert result['volume'] == 1000000
    
    def test_validate_candle(self, converter):
        """Test candle validation"""
        valid_candle = {
            'open_time': 1704067200000,
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 102.0,
            'volume': 10000
        }
        
        invalid_candle = {'open': 100.0}
        
        assert converter.validate_candle(valid_candle) == True
        assert converter.validate_candle(invalid_candle) == False
    
    def test_safe_float_with_none(self, converter):
        """Test safe float conversion with None"""
        assert converter._safe_float(None) == 0.0
        assert converter._safe_float(None, 5.0) == 5.0
    
    def test_safe_float_with_string(self, converter):
        """Test safe float conversion with string"""
        assert converter._safe_float("100.5") == 100.5
        assert converter._safe_float("invalid") == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
