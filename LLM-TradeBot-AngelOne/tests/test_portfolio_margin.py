"""
Test portfolio margin logic
"""
import pytest
from datetime import datetime
from src.backtest.portfolio import BacktestPortfolio, Side, MarginConfig

def test_margin_deduction():
    """Test if margin is correctly deducted when opening position instead of full amount"""
    # Initial capital 10000, 10x leverage, no slippage
    portfolio = BacktestPortfolio(
        initial_capital=10000.0,
        slippage=0.0,
        margin_config=MarginConfig(leverage=10)
    )
    
    # Open 1 BTC @ 50000 USD
    # Notional value = 50000
    # Margin to deduct = 5000
    # Fee (Maker 0.02%) = 10 (assuming ignored or very small here)
    
    trade = portfolio.open_position(
        symbol="BTCUSDT",
        side=Side.LONG,
        quantity=1.0,
        price=50000.0,
        timestamp=datetime.now()
    )
    
    assert trade is not None
    
    # Verify cash balance
    # Expected balance = 10000 - 5000 (Margin) - fee
    # Fee approx 50000 * 0.0004 (Taker default) = 20
    # So balance should be about 4980
    
    expected_margin = 5000.0
    expected_fee = 50000.0 * 0.0004
    expected_cash = 10000.0 - expected_margin - expected_fee
    
    assert abs(portfolio.cash - expected_cash) < 1.0, f"Cash ${portfolio.cash} != Expected ${expected_cash}"

def test_margin_return():
    """Test if margin is returned when closing position"""
    portfolio = BacktestPortfolio(
        initial_capital=10000.0,
        slippage=0.0,
        margin_config=MarginConfig(leverage=10)
    )
    
    # Open position
    portfolio.open_position(
        symbol="BTCUSDT",
        side=Side.LONG,
        quantity=1.0,
        price=50000.0,
        timestamp=datetime.now()
    )
    
    initial_cash_after_open = portfolio.cash
    
    # Close @ 51000 (profit 1000)
    portfolio.close_position(
        symbol="BTCUSDT",
        price=51000.0,
        timestamp=datetime.now()
    )
    
    # Expected balance = cash after open + margin(5000) + profit(1000) - close fee
    # Close fee = 51000 * 0.0004 = 20.4
    
    expected_return = 5000.0 + 1000.0 - (51000.0 * 0.0004)
    expected_final_cash = initial_cash_after_open + expected_return
    
    assert abs(portfolio.cash - expected_final_cash) < 1.0, f"Final Cash ${portfolio.cash} != Expected ${expected_final_cash}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
