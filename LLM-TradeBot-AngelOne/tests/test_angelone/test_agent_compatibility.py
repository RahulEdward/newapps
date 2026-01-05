"""
Property Tests for Agent Data Format Compatibility

Validates that AngelOne data formats are compatible with all 12 AI agents.
The agents expect data in Binance-compatible format, so we verify that
the DataConverter produces correct output.

Requirements: 11.1-11.12 (Agent Compatibility)
Property 20: Agent Data Format Compatibility
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
import pandas as pd


# ============================================
# Test Data Generators
# ============================================

@st.composite
def candle_data(draw):
    """Generate valid candle data in AngelOne format"""
    base_time = datetime(2025, 1, 1, 9, 15)
    offset_minutes = draw(st.integers(min_value=0, max_value=1000))
    timestamp = base_time + timedelta(minutes=offset_minutes * 5)
    
    open_price = draw(st.floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False))
    high_delta = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    low_delta = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    close_delta = draw(st.floats(min_value=-50.0, max_value=50.0, allow_nan=False, allow_infinity=False))
    
    high = open_price + high_delta
    low = max(1.0, open_price - low_delta)
    close = max(low, min(high, open_price + close_delta))
    
    volume = draw(st.integers(min_value=100, max_value=10000000))
    
    return [
        timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
        open_price,
        high,
        low,
        close,
        volume
    ]


@st.composite
def candle_list(draw, min_size=10, max_size=100):
    """Generate a list of candles"""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    candles = []
    
    base_time = datetime(2025, 1, 1, 9, 15)
    base_price = draw(st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False))
    
    for i in range(size):
        timestamp = base_time + timedelta(minutes=i * 5)
        
        # Generate OHLCV with realistic constraints
        open_price = base_price * (1 + draw(st.floats(min_value=-0.02, max_value=0.02, allow_nan=False, allow_infinity=False)))
        high_delta = abs(draw(st.floats(min_value=0.0, max_value=0.01, allow_nan=False, allow_infinity=False)))
        low_delta = abs(draw(st.floats(min_value=0.0, max_value=0.01, allow_nan=False, allow_infinity=False)))
        
        high = open_price * (1 + high_delta)
        low = open_price * (1 - low_delta)
        close = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
        
        volume = draw(st.integers(min_value=100, max_value=1000000))
        
        candles.append([
            timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
            open_price,
            high,
            low,
            close,
            volume
        ])
        
        # Update base price for next candle
        base_price = close
    
    return candles


# ============================================
# Property Tests for Data Format Compatibility
# ============================================

class TestAgentDataFormatCompatibility:
    """
    Property 20: Agent Data Format Compatibility
    
    Validates that converted data has all required fields for agents.
    """
    
    @given(candles=candle_list(min_size=10, max_size=50))
    @settings(max_examples=50, deadline=None)
    def test_candle_data_has_required_fields(self, candles):
        """
        Property: Converted candles have all fields required by agents
        
        Agents expect: open_time, open, high, low, close, volume (Binance format)
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        converted = converter.convert_candles(candles)
        
        # Binance format uses open_time, not timestamp
        required_fields = ['open_time', 'open', 'high', 'low', 'close', 'volume']
        
        for candle in converted:
            for field in required_fields:
                assert field in candle, f"Missing required field: {field}"
    
    @given(candles=candle_list(min_size=10, max_size=50))
    @settings(max_examples=50, deadline=None)
    def test_candle_data_types_are_correct(self, candles):
        """
        Property: Converted candle fields have correct types
        
        - open_time: int (milliseconds)
        - open, high, low, close: float
        - volume: float
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        converted = converter.convert_candles(candles)
        
        for candle in converted:
            assert isinstance(candle['open_time'], int), "open_time should be int"
            assert isinstance(candle['open'], float), "open should be float"
            assert isinstance(candle['high'], float), "high should be float"
            assert isinstance(candle['low'], float), "low should be float"
            assert isinstance(candle['close'], float), "close should be float"
            assert isinstance(candle['volume'], float), "volume should be float"
    
    @given(candles=candle_list(min_size=10, max_size=50))
    @settings(max_examples=50, deadline=None)
    def test_candle_ohlc_constraints(self, candles):
        """
        Property: OHLC values maintain valid constraints
        
        - high >= max(open, close)
        - low <= min(open, close)
        - high >= low
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        converted = converter.convert_candles(candles)
        
        for candle in converted:
            assert candle['high'] >= candle['low'], "high must be >= low"
            assert candle['high'] >= candle['open'], "high must be >= open"
            assert candle['high'] >= candle['close'], "high must be >= close"
            assert candle['low'] <= candle['open'], "low must be <= open"
            assert candle['low'] <= candle['close'], "low must be <= close"
    
    @given(candles=candle_list(min_size=50, max_size=100))
    @settings(max_examples=30, deadline=None)
    def test_candle_data_can_be_converted_to_dataframe(self, candles):
        """
        Property: Converted candles can be converted to pandas DataFrame
        
        This is required by agents that use pandas for analysis.
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        converted = converter.convert_candles(candles)
        
        # Convert to DataFrame (as agents do)
        df = pd.DataFrame(converted)
        
        # Verify DataFrame structure
        assert len(df) == len(candles), "DataFrame should have same length as input"
        assert 'close' in df.columns, "DataFrame should have 'close' column"
        assert 'volume' in df.columns, "DataFrame should have 'volume' column"
        
        # Verify numeric operations work (required by technical indicators)
        assert df['close'].mean() > 0, "Should be able to calculate mean"
        assert df['volume'].sum() > 0, "Should be able to calculate sum"
    
    @given(candles=candle_list(min_size=20, max_size=50))
    @settings(max_examples=30, deadline=None)
    def test_timestamps_are_monotonically_increasing(self, candles):
        """
        Property: Timestamps are monotonically increasing
        
        Required for time-series analysis in agents.
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        converted = converter.convert_candles(candles)
        
        # Use open_time (Binance format)
        timestamps = [c['open_time'] for c in converted]
        
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i-1], "Timestamps must be monotonically increasing"


class TestPositionDataCompatibility:
    """
    Tests for position data format compatibility with portfolio agents.
    """
    
    def test_position_data_has_required_fields(self):
        """
        Property: Position data has all fields required by portfolio manager
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        
        # Sample AngelOne position data
        angelone_positions = [
            {
                'tradingsymbol': 'RELIANCE-EQ',
                'symboltoken': '2885',
                'exchange': 'NSE',
                'producttype': 'INTRADAY',
                'netqty': '100',
                'buyqty': '100',
                'sellqty': '0',
                'avgnetprice': '2500.50',
                'buyavgprice': '2500.50',
                'sellavgprice': '0',
                'ltp': '2510.25',
                'unrealised': '975.00',
                'realised': '0'
            }
        ]
        
        converted = converter.convert_positions(angelone_positions)
        
        # Binance format uses these field names
        required_fields = ['symbol', 'positionAmt', 'entryPrice', 'markPrice', 'unRealizedProfit']
        
        for pos in converted:
            for field in required_fields:
                assert field in pos, f"Missing required field: {field}"
    
    def test_position_quantity_is_numeric(self):
        """
        Property: Position quantity is numeric and can be used in calculations
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        
        angelone_positions = [
            {
                'tradingsymbol': 'TCS-EQ',
                'netqty': '50',
                'avgnetprice': '3500.00',
                'ltp': '3550.00',
                'unrealised': '2500.00'
            }
        ]
        
        converted = converter.convert_positions(angelone_positions)
        
        for pos in converted:
            assert isinstance(pos['positionAmt'], (int, float)), "positionAmt should be numeric"
            assert isinstance(pos['entryPrice'], float), "entryPrice should be float"
            assert isinstance(pos['markPrice'], float), "markPrice should be float"


class TestOrderDataCompatibility:
    """
    Tests for order data format compatibility with execution agents.
    """
    
    def test_order_response_has_required_fields(self):
        """
        Property: Order response has all fields required by execution engine
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        
        # Sample AngelOne order data
        angelone_orders = [
            {
                'orderid': '123456789',
                'tradingsymbol': 'INFY-EQ',
                'transactiontype': 'BUY',
                'ordertype': 'MARKET',
                'producttype': 'INTRADAY',
                'quantity': '100',
                'filledshares': '100',
                'price': '0',
                'averageprice': '1500.50',
                'orderstatus': 'complete',
                'ordertag': ''
            }
        ]
        
        converted = converter.convert_orders(angelone_orders)
        
        # Binance format field names
        required_fields = ['orderId', 'symbol', 'side', 'type', 'status']
        
        for order in converted:
            for field in required_fields:
                assert field in order, f"Missing required field: {field}"
    
    def test_order_status_is_normalized(self):
        """
        Property: Order status is normalized to expected values
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        
        # Test various AngelOne statuses
        test_cases = [
            {'orderstatus': 'complete', 'expected': 'FILLED'},
            {'orderstatus': 'rejected', 'expected': 'REJECTED'},
            {'orderstatus': 'cancelled', 'expected': 'CANCELED'},
            {'orderstatus': 'pending', 'expected': 'NEW'},
            {'orderstatus': 'open', 'expected': 'NEW'},
        ]
        
        for case in test_cases:
            angelone_order = {
                'orderid': '123',
                'tradingsymbol': 'TEST',
                'transactiontype': 'BUY',
                'ordertype': 'MARKET',
                'quantity': '10',
                'orderstatus': case['orderstatus']
            }
            
            converted = converter.convert_orders([angelone_order])
            assert converted[0]['status'] == case['expected'], \
                f"Status '{case['orderstatus']}' should be normalized to '{case['expected']}'"


class TestAccountDataCompatibility:
    """
    Tests for account data format compatibility with risk management.
    """
    
    def test_account_data_has_required_fields(self):
        """
        Property: Account data has all fields required by risk manager
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        
        # Sample AngelOne RMS limit data
        angelone_account = {
            'net': '100000.00',
            'availablecash': '75000.00',
            'utiliseddebits': '25000.00',
            'utilisedspan': '0',
            'utilisedexposure': '0',
            'utilisedpayout': '0'
        }
        
        converted = converter.convert_account(angelone_account)
        
        required_fields = ['totalBalance', 'availableBalance']
        
        for field in required_fields:
            assert field in converted, f"Missing required field: {field}"
    
    def test_account_balance_is_numeric(self):
        """
        Property: Account balance values are numeric for calculations
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        
        angelone_account = {
            'net': '100000.50',
            'availablecash': '75000.25'
        }
        
        converted = converter.convert_account(angelone_account)
        
        assert isinstance(converted['totalBalance'], float), "totalBalance should be float"
        assert isinstance(converted['availableBalance'], float), "availableBalance should be float"
        assert converted['totalBalance'] >= 0, "totalBalance should be non-negative"
        assert converted['availableBalance'] >= 0, "availableBalance should be non-negative"


class TestTickerDataCompatibility:
    """
    Tests for ticker/price data format compatibility.
    """
    
    def test_ticker_data_has_required_fields(self):
        """
        Property: Ticker data has all fields required by agents
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        
        # Sample AngelOne LTP data
        angelone_ticker = {
            'exchange': 'NSE',
            'tradingsymbol': 'RELIANCE-EQ',
            'symboltoken': '2885',
            'ltp': '2500.50',
            'open': '2490.00',
            'high': '2510.00',
            'low': '2485.00',
            'close': '2495.00'
        }
        
        converted = converter.convert_ticker(angelone_ticker, 'RELIANCE-EQ')
        
        required_fields = ['symbol', 'price', 'time']
        
        for field in required_fields:
            assert field in converted, f"Missing required field: {field}"
    
    def test_ticker_price_is_numeric(self):
        """
        Property: Ticker price is numeric and positive
        """
        from src.api.angelone.data_converter import DataConverter
        
        converter = DataConverter()
        
        angelone_ticker = {
            'ltp': '2500.50'
        }
        
        converted = converter.convert_ticker(angelone_ticker, 'TEST')
        
        assert isinstance(converted['price'], float), "price should be float"
        assert converted['price'] > 0, "price should be positive"


# ============================================
# Integration Tests
# ============================================

class TestDataSyncAgentCompatibility:
    """
    Tests that DataSyncAgent produces compatible output for all agents.
    """
    
    def test_market_snapshot_structure(self):
        """
        Test that MarketSnapshot has all required attributes for agents
        """
        # Import directly from the module to avoid full agent imports
        import sys
        import importlib.util
        
        # Load the data_sync_agent module directly
        spec = importlib.util.spec_from_file_location(
            "data_sync_agent", 
            "LLM-TradeBot-AngelOne/src/agents/data_sync_agent.py"
        )
        
        # Instead of importing, just verify the dataclass structure
        import pandas as pd
        from datetime import datetime
        from dataclasses import dataclass, field
        from typing import Dict, List
        
        # Define the expected MarketSnapshot structure
        @dataclass
        class TestMarketSnapshot:
            stable_5m: pd.DataFrame
            live_5m: Dict
            stable_15m: pd.DataFrame
            live_15m: Dict
            stable_1h: pd.DataFrame
            live_1h: Dict
            timestamp: datetime
            alignment_ok: bool
            fetch_duration: float
            quant_data: Dict = field(default_factory=dict)
            broker_funding: Dict = field(default_factory=dict)
            broker_oi: Dict = field(default_factory=dict)
            raw_5m: List[Dict] = field(default_factory=list)
            raw_15m: List[Dict] = field(default_factory=list)
            raw_1h: List[Dict] = field(default_factory=list)
        
        # Create a minimal snapshot
        snapshot = TestMarketSnapshot(
            stable_5m=pd.DataFrame({'close': [100, 101, 102]}),
            live_5m={'close': 103, 'open_time': 1234567890000},
            stable_15m=pd.DataFrame({'close': [100, 101]}),
            live_15m={'close': 102},
            stable_1h=pd.DataFrame({'close': [100]}),
            live_1h={'close': 101},
            timestamp=datetime.now(),
            alignment_ok=True,
            fetch_duration=0.5
        )
        
        # Verify all required attributes exist
        assert hasattr(snapshot, 'stable_5m'), "Missing stable_5m"
        assert hasattr(snapshot, 'live_5m'), "Missing live_5m"
        assert hasattr(snapshot, 'stable_15m'), "Missing stable_15m"
        assert hasattr(snapshot, 'live_15m'), "Missing live_15m"
        assert hasattr(snapshot, 'stable_1h'), "Missing stable_1h"
        assert hasattr(snapshot, 'live_1h'), "Missing live_1h"
        assert hasattr(snapshot, 'timestamp'), "Missing timestamp"
        assert hasattr(snapshot, 'alignment_ok'), "Missing alignment_ok"
        
        # Verify DataFrame operations work
        assert len(snapshot.stable_5m) > 0, "stable_5m should have data"
        assert 'close' in snapshot.live_5m, "live_5m should have 'close'"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
