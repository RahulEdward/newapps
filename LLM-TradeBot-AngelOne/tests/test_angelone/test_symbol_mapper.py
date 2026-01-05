"""
Tests for Symbol Mapper
Includes property-based tests and unit tests

Feature: llm-tradebot-angelone
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from api.angelone.symbol_mapper import (
    SymbolMapper, SymbolInfo, SymbolNotFoundError,
    Exchange, InstrumentType
)


# =============================================================================
# Test Data - Mock Instrument Master
# =============================================================================

MOCK_INSTRUMENTS = [
    # NSE Equity
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
        "token": "3045",
        "symbol": "TCS-EQ",
        "name": "TCS",
        "expiry": "",
        "strike": "-1",
        "lotsize": "1",
        "instrumenttype": "",
        "exch_seg": "NSE",
        "tick_size": "0.05"
    },
    {
        "token": "1594",
        "symbol": "INFY-EQ",
        "name": "INFOSYS",
        "expiry": "",
        "strike": "-1",
        "lotsize": "1",
        "instrumenttype": "",
        "exch_seg": "NSE",
        "tick_size": "0.05"
    },
    # BSE Equity
    {
        "token": "500325",
        "symbol": "RELIANCE-EQ",
        "name": "RELIANCE",
        "expiry": "",
        "strike": "-1",
        "lotsize": "1",
        "instrumenttype": "",
        "exch_seg": "BSE",
        "tick_size": "0.05"
    },
    # NFO Futures
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
    {
        "token": "35002",
        "symbol": "BANKNIFTY25JANFUT",
        "name": "BANKNIFTY",
        "expiry": "25JAN2025",
        "strike": "-1",
        "lotsize": "25",
        "instrumenttype": "FUTIDX",
        "exch_seg": "NFO",
        "tick_size": "0.05"
    },
    # NFO Options - Call
    {
        "token": "45001",
        "symbol": "NIFTY25JAN24000CE",
        "name": "NIFTY",
        "expiry": "25JAN2025",
        "strike": "2400000",  # Strike * 100
        "lotsize": "50",
        "instrumenttype": "OPTIDX",
        "exch_seg": "NFO",
        "tick_size": "0.05"
    },
    # NFO Options - Put
    {
        "token": "45002",
        "symbol": "NIFTY25JAN24000PE",
        "name": "NIFTY",
        "expiry": "25JAN2025",
        "strike": "2400000",
        "lotsize": "50",
        "instrumenttype": "OPTIDX",
        "exch_seg": "NFO",
        "tick_size": "0.05"
    },
    # MCX Commodity
    {
        "token": "220822",
        "symbol": "GOLDM25JANFUT",
        "name": "GOLDM",
        "expiry": "25JAN2025",
        "strike": "-1",
        "lotsize": "10",
        "instrumenttype": "FUTCOM",
        "exch_seg": "MCX",
        "tick_size": "1"
    },
]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mapper():
    """Create a SymbolMapper with mock data"""
    m = SymbolMapper()
    m.load_instruments(MOCK_INSTRUMENTS)
    return m


@pytest.fixture
def empty_mapper():
    """Create an empty SymbolMapper"""
    return SymbolMapper()


# =============================================================================
# Property-Based Tests
# =============================================================================

class TestSymbolMappingProperty:
    """
    Property 7: Symbol Token Mapping
    *For any* valid trading symbol, the Symbol_Manager SHALL return a 
    non-empty symbol token and valid exchange.
    
    **Validates: Requirements 3.2, 3.3**
    """
    
    @given(st.sampled_from([
        ("RELIANCE-EQ", "NSE"),
        ("TCS-EQ", "NSE"),
        ("INFY-EQ", "NSE"),
        ("RELIANCE-EQ", "BSE"),
        ("NIFTY25JANFUT", "NFO"),
        ("BANKNIFTY25JANFUT", "NFO"),
        ("NIFTY25JAN24000CE", "NFO"),
        ("NIFTY25JAN24000PE", "NFO"),
    ]))
    @settings(max_examples=100)
    def test_valid_symbol_returns_token(self, symbol_exchange):
        """
        Feature: llm-tradebot-angelone, Property 7: Symbol Token Mapping
        For any valid symbol, get_token returns non-empty token
        """
        symbol, exchange = symbol_exchange
        
        mapper = SymbolMapper()
        mapper.load_instruments(MOCK_INSTRUMENTS)
        
        token = mapper.get_token(symbol, exchange)
        
        # Property: Token must be non-empty
        assert token is not None
        assert len(token) > 0
        assert token.isdigit()  # AngelOne tokens are numeric


class TestSymbolTypeProperty:
    """
    Property 8: Symbol Type Support
    *For any* equity symbol (ending in -EQ), futures symbol (containing FUT),
    or options symbol (containing CE/PE), the Symbol_Manager SHALL correctly
    identify and map the symbol.
    
    **Validates: Requirements 3.4, 3.5, 3.6**
    """
    
    @given(st.sampled_from([
        ("RELIANCE-EQ", "NSE", InstrumentType.EQUITY.value),
        ("TCS-EQ", "NSE", InstrumentType.EQUITY.value),
        ("NIFTY25JANFUT", "NFO", InstrumentType.FUTURES.value),
        ("BANKNIFTY25JANFUT", "NFO", InstrumentType.FUTURES.value),
        ("NIFTY25JAN24000CE", "NFO", InstrumentType.CALL_OPTION.value),
        ("NIFTY25JAN24000PE", "NFO", InstrumentType.PUT_OPTION.value),
    ]))
    @settings(max_examples=100)
    def test_symbol_type_identification(self, symbol_data):
        """
        Feature: llm-tradebot-angelone, Property 8: Symbol Type Support
        Symbol types are correctly identified
        """
        symbol, exchange, expected_type = symbol_data
        
        mapper = SymbolMapper()
        mapper.load_instruments(MOCK_INSTRUMENTS)
        
        info = mapper.get_symbol_info(symbol, exchange)
        
        # Property: Instrument type matches expected
        assert info.instrument_type == expected_type


class TestInvalidSymbolProperty:
    """
    Property 9: Invalid Symbol Error
    *For any* non-existent symbol, the Symbol_Manager SHALL raise a 
    descriptive error containing the symbol name.
    
    **Validates: Requirements 3.7**
    """
    
    @given(st.text(min_size=5, max_size=20, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'))
    @settings(max_examples=100)
    def test_invalid_symbol_raises_error(self, random_symbol):
        """
        Feature: llm-tradebot-angelone, Property 9: Invalid Symbol Error
        Invalid symbols raise descriptive errors
        """
        # Skip if symbol accidentally matches a real one
        valid_symbols = ["RELIANCE", "TCS", "INFY", "NIFTY", "BANKNIFTY", "GOLDM"]
        assume(not any(v in random_symbol for v in valid_symbols))
        
        mapper = SymbolMapper()
        mapper.load_instruments(MOCK_INSTRUMENTS)
        
        with pytest.raises(SymbolNotFoundError) as exc_info:
            mapper.get_token(random_symbol, "NSE")
        
        # Property: Error message contains the symbol name
        assert random_symbol in str(exc_info.value)


# =============================================================================
# Unit Tests
# =============================================================================

class TestSymbolMapperUnit:
    """Unit tests for SymbolMapper"""
    
    def test_load_instruments(self, mapper):
        """Test instrument loading"""
        assert mapper.is_loaded
        assert mapper.get_instrument_count() > 0
    
    def test_get_nse_equity(self, mapper):
        """Test getting NSE equity symbol"""
        info = mapper.get_symbol_info("RELIANCE-EQ", "NSE")
        
        assert info.symbol == "RELIANCE-EQ"
        assert info.token == "2885"
        assert info.exchange == "NSE"
        assert info.name == "RELIANCE"
    
    def test_get_equity_without_suffix(self, mapper):
        """Test getting equity without -EQ suffix"""
        info = mapper.get_equity_symbol("RELIANCE", "NSE")
        
        assert info.symbol == "RELIANCE-EQ"
        assert info.token == "2885"
    
    def test_get_bse_equity(self, mapper):
        """Test getting BSE equity symbol"""
        info = mapper.get_symbol_info("RELIANCE-EQ", "BSE")
        
        assert info.exchange == "BSE"
        assert info.token == "500325"
    
    def test_get_futures(self, mapper):
        """Test getting futures symbol"""
        info = mapper.get_symbol_info("NIFTY25JANFUT", "NFO")
        
        assert info.instrument_type == InstrumentType.FUTURES.value
        assert info.lot_size == 50
        assert "25JAN" in info.expiry
    
    def test_get_call_option(self, mapper):
        """Test getting call option symbol"""
        info = mapper.get_symbol_info("NIFTY25JAN24000CE", "NFO")
        
        assert info.instrument_type == InstrumentType.CALL_OPTION.value
        assert info.option_type == "CE"
        assert info.strike == 24000.0
    
    def test_get_put_option(self, mapper):
        """Test getting put option symbol"""
        info = mapper.get_symbol_info("NIFTY25JAN24000PE", "NFO")
        
        assert info.instrument_type == InstrumentType.PUT_OPTION.value
        assert info.option_type == "PE"
    
    def test_search_symbol(self, mapper):
        """Test symbol search"""
        results = mapper.search_symbol("RELIANCE")
        
        assert len(results) >= 1
        assert any(r.name == "RELIANCE" for r in results)
    
    def test_search_with_exchange_filter(self, mapper):
        """Test symbol search with exchange filter"""
        results = mapper.search_symbol("RELIANCE", exchange="NSE")
        
        assert all(r.exchange == "NSE" for r in results)
    
    def test_invalid_symbol_error(self, mapper):
        """Test error for invalid symbol"""
        with pytest.raises(SymbolNotFoundError) as exc_info:
            mapper.get_token("INVALID_SYMBOL_XYZ", "NSE")
        
        assert "INVALID_SYMBOL_XYZ" in str(exc_info.value)
    
    def test_invalid_exchange_error(self, mapper):
        """Test error for invalid exchange"""
        with pytest.raises(SymbolNotFoundError) as exc_info:
            mapper.get_token("RELIANCE-EQ", "INVALID")
        
        assert "Invalid exchange" in str(exc_info.value)
    
    def test_not_loaded_error(self, empty_mapper):
        """Test error when instruments not loaded"""
        with pytest.raises(SymbolNotFoundError) as exc_info:
            empty_mapper.get_token("RELIANCE-EQ", "NSE")
        
        assert "not loaded" in str(exc_info.value)
    
    def test_instrument_count_by_exchange(self, mapper):
        """Test instrument count by exchange"""
        nse_count = mapper.get_instrument_count("NSE")
        bse_count = mapper.get_instrument_count("BSE")
        nfo_count = mapper.get_instrument_count("NFO")
        
        assert nse_count == 3  # RELIANCE, TCS, INFY
        assert bse_count == 1  # RELIANCE
        assert nfo_count == 4  # 2 futures + 2 options


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
