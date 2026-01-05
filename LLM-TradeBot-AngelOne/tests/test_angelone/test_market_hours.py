"""
Tests for Market Hours Manager
Includes property-based tests and unit tests

Feature: llm-tradebot-angelone
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, date, time, timedelta
import pytz
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from api.angelone.market_hours import MarketHoursManager


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def manager():
    """Create a MarketHoursManager"""
    return MarketHoursManager()


IST = pytz.timezone('Asia/Kolkata')


# =============================================================================
# Property-Based Tests
# =============================================================================

class TestMarketHoursDetectionProperty:
    """
    Property 14: Market Hours Detection
    *For any* datetime in IST timezone, is_market_open() SHALL return True 
    if and only if: (1) it's a weekday, (2) not a holiday, and (3) time is 
    between 9:15 AM and 3:30 PM.
    
    **Validates: Requirements 6.1, 6.2, 6.4, 6.5**
    """
    
    @given(
        year=st.integers(min_value=2025, max_value=2026),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),  # Safe for all months
        hour=st.integers(min_value=0, max_value=23),
        minute=st.integers(min_value=0, max_value=59)
    )
    @settings(max_examples=100)
    def test_market_open_conditions(self, year, month, day, hour, minute):
        """
        Feature: llm-tradebot-angelone, Property 14: Market Hours Detection
        Market is open iff weekday, not holiday, and within trading hours
        """
        manager = MarketHoursManager()
        
        try:
            test_date = date(year, month, day)
            test_time = time(hour, minute, 0)
            test_dt = IST.localize(datetime.combine(test_date, test_time))
        except ValueError:
            return  # Invalid date
        
        is_open = manager.is_market_open(test_dt)
        
        # Check conditions
        is_weekday = test_date.weekday() < 5
        is_not_holiday = test_date not in manager._holidays
        is_trading_hours = (
            time(9, 15, 0) <= test_time <= time(15, 30, 0)
        )
        
        expected_open = is_weekday and is_not_holiday and is_trading_hours
        
        # Property: is_market_open matches expected conditions
        assert is_open == expected_open, (
            f"Date: {test_date}, Time: {test_time}, "
            f"Weekday: {is_weekday}, Not Holiday: {is_not_holiday}, "
            f"Trading Hours: {is_trading_hours}, "
            f"Expected: {expected_open}, Got: {is_open}"
        )


class TestNextMarketOpenProperty:
    """
    Property 15: Next Market Open Calculation
    *For any* datetime when market is closed, get_next_market_open() SHALL 
    return a datetime that is: (1) in the future, (2) at 9:15 AM IST, and 
    (3) on a valid trading day.
    
    **Validates: Requirements 6.6**
    """
    
    @given(
        year=st.integers(min_value=2025, max_value=2026),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
        hour=st.integers(min_value=0, max_value=23),
        minute=st.integers(min_value=0, max_value=59)
    )
    @settings(max_examples=100)
    def test_next_market_open_is_valid(self, year, month, day, hour, minute):
        """
        Feature: llm-tradebot-angelone, Property 15: Next Market Open Calculation
        Next market open is in future, at 9:15 AM, on trading day
        """
        manager = MarketHoursManager()
        
        try:
            test_date = date(year, month, day)
            test_time = time(hour, minute, 0)
            test_dt = IST.localize(datetime.combine(test_date, test_time))
        except ValueError:
            return
        
        # Skip if market is currently open
        if manager.is_market_open(test_dt):
            return
        
        next_open = manager.get_next_market_open(test_dt)
        
        # Property 1: Next open is in the future
        assert next_open > test_dt, f"Next open {next_open} should be after {test_dt}"
        
        # Property 2: Next open is at 9:15 AM
        assert next_open.time() == time(9, 15, 0), (
            f"Next open time should be 9:15 AM, got {next_open.time()}"
        )
        
        # Property 3: Next open is on a trading day
        assert manager.is_trading_day(next_open.date()), (
            f"Next open date {next_open.date()} should be a trading day"
        )


class TestWeekendDetectionProperty:
    """
    Property: Weekend Detection
    *For any* Saturday or Sunday, is_weekend() SHALL return True
    
    **Validates: Requirements 6.5**
    """
    
    @given(
        year=st.integers(min_value=2025, max_value=2026),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28)
    )
    @settings(max_examples=100)
    def test_weekend_detection(self, year, month, day):
        """
        Feature: llm-tradebot-angelone, Weekend Detection
        Weekends are correctly identified
        """
        manager = MarketHoursManager()
        
        try:
            test_date = date(year, month, day)
        except ValueError:
            return
        
        is_weekend = manager.is_weekend(test_date)
        expected_weekend = test_date.weekday() >= 5
        
        assert is_weekend == expected_weekend


# =============================================================================
# Unit Tests
# =============================================================================

class TestMarketHoursUnit:
    """Unit tests for MarketHoursManager"""
    
    def test_market_open_during_trading_hours(self, manager):
        """Test market is open during trading hours on weekday"""
        # Monday at 10:00 AM
        test_dt = IST.localize(datetime(2025, 1, 6, 10, 0, 0))
        
        assert manager.is_market_open(test_dt) == True
    
    def test_market_closed_before_open(self, manager):
        """Test market is closed before 9:15 AM"""
        # Monday at 9:00 AM
        test_dt = IST.localize(datetime(2025, 1, 6, 9, 0, 0))
        
        assert manager.is_market_open(test_dt) == False
    
    def test_market_closed_after_close(self, manager):
        """Test market is closed after 3:30 PM"""
        # Monday at 4:00 PM
        test_dt = IST.localize(datetime(2025, 1, 6, 16, 0, 0))
        
        assert manager.is_market_open(test_dt) == False
    
    def test_market_closed_on_weekend(self, manager):
        """Test market is closed on weekend"""
        # Saturday at 10:00 AM
        test_dt = IST.localize(datetime(2025, 1, 4, 10, 0, 0))
        
        assert manager.is_market_open(test_dt) == False
        assert manager.is_weekend(test_dt.date()) == True
    
    def test_market_closed_on_holiday(self, manager):
        """Test market is closed on holiday"""
        # Republic Day 2025
        test_dt = IST.localize(datetime(2025, 1, 26, 10, 0, 0))
        
        assert manager.is_market_open(test_dt) == False
        assert manager.is_holiday(test_dt.date()) == True
    
    def test_pre_market_session(self, manager):
        """Test pre-market session detection"""
        # Monday at 9:10 AM
        test_dt = IST.localize(datetime(2025, 1, 6, 9, 10, 0))
        
        assert manager.is_pre_market(test_dt) == True
        assert manager.is_market_open(test_dt) == False
    
    def test_post_market_session(self, manager):
        """Test post-market session detection"""
        # Monday at 3:45 PM
        test_dt = IST.localize(datetime(2025, 1, 6, 15, 45, 0))
        
        assert manager.is_post_market(test_dt) == True
        assert manager.is_market_open(test_dt) == False
    
    def test_next_market_open_from_weekend(self, manager):
        """Test next market open from weekend"""
        # Saturday at 10:00 AM
        test_dt = IST.localize(datetime(2025, 1, 4, 10, 0, 0))
        
        next_open = manager.get_next_market_open(test_dt)
        
        # Should be Monday 9:15 AM
        assert next_open.date() == date(2025, 1, 6)
        assert next_open.time() == time(9, 15, 0)
    
    def test_next_market_open_same_day(self, manager):
        """Test next market open on same day before market opens"""
        # Monday at 8:00 AM
        test_dt = IST.localize(datetime(2025, 1, 6, 8, 0, 0))
        
        next_open = manager.get_next_market_open(test_dt)
        
        # Should be same day 9:15 AM
        assert next_open.date() == date(2025, 1, 6)
        assert next_open.time() == time(9, 15, 0)
    
    def test_time_to_market_close(self, manager):
        """Test time remaining until market close"""
        # Monday at 3:00 PM
        test_dt = IST.localize(datetime(2025, 1, 6, 15, 0, 0))
        
        time_remaining = manager.time_to_market_close(test_dt)
        
        # Should be 30 minutes
        assert time_remaining == timedelta(minutes=30)
    
    def test_market_session_names(self, manager):
        """Test market session name detection"""
        # Pre-market
        pre_dt = IST.localize(datetime(2025, 1, 6, 9, 10, 0))
        assert manager.get_market_session(pre_dt) == 'pre_market'
        
        # Market
        market_dt = IST.localize(datetime(2025, 1, 6, 10, 0, 0))
        assert manager.get_market_session(market_dt) == 'market'
        
        # Post-market
        post_dt = IST.localize(datetime(2025, 1, 6, 15, 45, 0))
        assert manager.get_market_session(post_dt) == 'post_market'
        
        # Closed
        closed_dt = IST.localize(datetime(2025, 1, 6, 20, 0, 0))
        assert manager.get_market_session(closed_dt) == 'closed'
    
    def test_trading_days_in_range(self, manager):
        """Test getting trading days in a range"""
        start = date(2025, 1, 1)
        end = date(2025, 1, 10)
        
        trading_days = manager.get_trading_days_in_range(start, end)
        
        # Should exclude weekends and holidays
        for day in trading_days:
            assert day.weekday() < 5
            assert day not in manager._holidays
    
    def test_add_custom_holiday(self, manager):
        """Test adding custom holiday"""
        # Use a weekday that's not already a holiday
        custom_date = date(2025, 6, 16)  # Monday
        
        assert manager.is_trading_day(custom_date) == True
        
        manager.add_holiday(custom_date)
        
        assert manager.is_trading_day(custom_date) == False
        assert manager.is_holiday(custom_date) == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
