import asyncio
from datetime import datetime
from src.backtest.engine import BacktestEngine, BacktestConfig

async def run_verification():
    print("🚀 Starting Verification Backtest...")
    
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_date="2025-12-28",
        end_date="2025-12-31",
        initial_capital=10000.0,
        strategy_mode="agent", # Correct mode for multi-agent test
        use_llm=True  # Important: Use LLM/Agents
    )
    
    engine = BacktestEngine(config)
    result = await engine.run()
    
    print("\n📊 Backtest Result Summary:")
    print(f"Total Trades: {result['total_trades']}")
    print(f"Win Rate: {result['win_rate']:.2f}%")
    print(f"Total Return: {result['total_return']:.2f}%")
    print(f"Sharpe Ratio: {result['sharpe_ratio']:.2f}")

if __name__ == "__main__":
    asyncio.run(run_verification())
