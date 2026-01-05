"""
Test Data Replay Look-ahead Bias Fix
"""
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock
from src.backtest.data_replay import DataReplayAgent, MarketSnapshot

def test_get_current_price_uses_open():
    """Verify get_current_price uses Open price"""
    replay = DataReplayAgent("BTCUSDT", "2024-01-01", "2024-01-02")
    
    # Mock snapshot
    mock_snapshot = MagicMock(spec=MarketSnapshot)
    # Set live_5m as dict containing open and close
    mock_snapshot.live_5m = {
        'open': 50000.0,
        'high': 51000.0,
        'low': 49000.0,
        'close': 50500.0  # Close price different from open
    }
    
    replay.latest_snapshot = mock_snapshot
    
    price = replay.get_current_price()
    
    # Should equal Open (50000), not Close (50500)
    assert price == 50000.0, f"Price {price} should be Open price 50000.0"
    assert price != 50500.0, "Price should not be Close price (Limit Look-ahead Bias)"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
