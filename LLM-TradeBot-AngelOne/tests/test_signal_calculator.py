"""
Test signal calculator functionality
"""
import pytest
import pandas as pd
import numpy as np
from src.backtest.agent_wrapper import BacktestSignalCalculator


def test_rsi_no_division_by_zero():
    """Test RSI calculation doesn't divide by zero"""
    calc = BacktestSignalCalculator()
    
    # Create data with zero changes (would cause loss=0)
    data = pd.Series([100.0] * 50)
    
    # Should not throw exception
    rsi = calc.calculate_rsi(data)
    
    # RSI should be valid values (not NaN or Inf)
    assert not rsi.isna().all(), "RSI should not be all NaN"
    assert not np.isinf(rsi).any(), "RSI should not contain infinity"


def test_rsi_normal_calculation():
    """Test RSI normal calculation"""
    calc = BacktestSignalCalculator()
    
    # Create data with changes
    data = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109] * 5)
    
    rsi = calc.calculate_rsi(data, period=14)
    
    # RSI should be between 0-100
    valid_rsi = rsi.dropna()
    assert (valid_rsi >= 0).all(), "RSI should be >= 0"
    assert (valid_rsi <= 100).all(), "RSI should be <= 100"


def test_rsi_uptrend():
    """Test RSI in uptrend"""
    calc = BacktestSignalCalculator()
    
    # Create uptrend data
    data = pd.Series(range(100, 150))
    
    rsi = calc.calculate_rsi(data, period=14)
    
    # Uptrend RSI should be high
    valid_rsi = rsi.dropna()
    assert valid_rsi.mean() > 50, "Uptrend RSI should be above 50"


def test_rsi_downtrend():
    """Test RSI in downtrend"""
    calc = BacktestSignalCalculator()
    
    # Create downtrend data
    data = pd.Series(range(150, 100, -1))
    
    rsi = calc.calculate_rsi(data, period=14)
    
    # Downtrend RSI should be low
    valid_rsi = rsi.dropna()
    assert valid_rsi.mean() < 50, "Downtrend RSI should be below 50"


def test_ema_calculation():
    """Test EMA calculation"""
    calc = BacktestSignalCalculator()
    
    data = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109] * 5)
    
    ema = calc.calculate_ema(data, span=20)
    
    # EMA should be valid values
    assert not ema.isna().all(), "EMA should not be all NaN"
    assert len(ema) == len(data), "EMA length should match input"


def test_kdj_calculation():
    """Test KDJ calculation"""
    calc = BacktestSignalCalculator()
    
    # Create test data
    high = pd.Series([105, 107, 106, 108, 110, 109, 111, 113, 112, 114] * 5)
    low = pd.Series([95, 97, 96, 98, 100, 99, 101, 103, 102, 104] * 5)
    close = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109] * 5)
    
    k, d, j = calc.calculate_kdj(high, low, close)
    
    # KDJ should be valid values
    assert not k.isna().all(), "K should not be all NaN"
    assert not d.isna().all(), "D should not be all NaN"
    assert not j.isna().all(), "J should not be all NaN"


def test_macd_calculation():
    """Test MACD calculation"""
    calc = BacktestSignalCalculator()
    
    data = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 109] * 5)
    
    macd_line, signal_line, macd_hist = calc.calculate_macd(data)
    
    # MACD should be valid values
    assert not macd_line.isna().all(), "MACD line should not be all NaN"
    assert not signal_line.isna().all(), "Signal line should not be all NaN"
    assert not macd_hist.isna().all(), "MACD histogram should not be all NaN"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
