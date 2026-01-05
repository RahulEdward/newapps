"""
Test backtest configuration validation
"""
import pytest
from src.backtest.engine import BacktestConfig


def test_valid_config():
    """Test valid configuration"""
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_capital=10000,
        leverage=5
    )
    assert config.symbol == "BTCUSDT"
    assert config.leverage == 5


def test_invalid_date_format():
    """Test invalid date format"""
    with pytest.raises(ValueError, match="Invalid date format"):
        BacktestConfig(
            symbol="BTCUSDT",
            start_date="2024/01/01",  # Wrong format
            end_date="2024-12-31"
        )


def test_start_after_end():
    """Test start date after end date"""
    with pytest.raises(ValueError, match="must be before"):
        BacktestConfig(
            symbol="BTCUSDT",
            start_date="2024-12-31",
            end_date="2024-01-01"
        )


def test_negative_capital():
    """Test negative initial capital"""
    with pytest.raises(ValueError, match="initial_capital must be positive"):
        BacktestConfig(
            symbol="BTCUSDT",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=-1000
        )


def test_invalid_leverage():
    """Test invalid leverage"""
    with pytest.raises(ValueError, match="leverage must be between"):
        BacktestConfig(
            symbol="BTCUSDT",
            start_date="2024-01-01",
            end_date="2024-12-31",
            leverage=200  # Out of range
        )


def test_invalid_stop_loss():
    """Test invalid stop loss percentage"""
    with pytest.raises(ValueError, match="stop_loss_pct must be between"):
        BacktestConfig(
            symbol="BTCUSDT",
            start_date="2024-01-01",
            end_date="2024-12-31",
            stop_loss_pct=150  # Out of range
        )


def test_invalid_strategy_mode():
    """Test invalid strategy mode"""
    with pytest.raises(ValueError, match="strategy_mode must be"):
        BacktestConfig(
            symbol="BTCUSDT",
            start_date="2024-01-01",
            end_date="2024-12-31",
            strategy_mode="invalid_mode"
        )


def test_empty_symbol():
    """Test empty trading pair"""
    with pytest.raises(ValueError, match="symbol must be a non-empty string"):
        BacktestConfig(
            symbol="",
            start_date="2024-01-01",
            end_date="2024-12-31"
        )


def test_no_duplicate_fields():
    """Verify no duplicate field definitions"""
    import inspect
    from dataclasses import fields
    
    config_fields = fields(BacktestConfig)
    field_names = [f.name for f in config_fields]
    
    # Check use_llm and llm_cache appear only once
    assert field_names.count('use_llm') == 1, "use_llm should appear only once"
    assert field_names.count('llm_cache') == 1, "llm_cache should appear only once"
    
    # Check no duplicate fields
    assert len(field_names) == len(set(field_names)), "No duplicate field names allowed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
