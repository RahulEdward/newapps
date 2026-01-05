"""
Complete Strategy Development Workflow
From data research -> strategy development -> backtesting -> live trading

This script demonstrates the complete strategy development workflow
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import Dict
import time


def step1_data_research():
    """Step 1: Data Research - Explore historical data, discover market patterns"""
    print("\n" + "="*80)
    print("Step 1/4: Data Research")
    print("="*80)
    print("\nGoal: Explore historical market data, discover exploitable trading patterns\n")
    
    from research.data_explorer import DataExplorer
    
    explorer = DataExplorer()
    
    # Fetch historical data
    df = explorer.fetch_historical_data(
        symbol="BTCUSDT",
        interval="1h",
        days=30
    )
    
    if df.empty:
        print("Data fetch failed")
        return None
    
    # Statistical analysis
    stats = explorer.analyze_data(df)
    
    # Pattern recognition
    patterns = explorer.find_patterns(df)
    
    # Visualization
    try:
        explorer.visualize_data(df)
    except Exception as e:
        print(f"Visualization skipped (requires matplotlib): {e}")
    
    # Generate report
    explorer.generate_report(df, stats, patterns)
    
    print("\nData research complete")
    print("Next step: Develop trading strategy based on research results")
    
    return {'stats': stats, 'patterns': patterns, 'data': df}


def step2_strategy_development(research_results: Dict):
    """Step 2: Strategy Development - Develop trading strategy based on research results"""
    print("\n" + "="*80)
    print("Step 2/4: Strategy Development")
    print("="*80)
    print("\nGoal: Develop executable trading strategy based on data research results\n")
    
    # Provide strategy recommendations based on research results
    stats = research_results.get('stats', {})
    patterns = research_results.get('patterns', {})
    
    print("Strategy Development Recommendations (based on data research):")
    
    # Analyze volatility
    volatility = stats.get('volatility', {})
    if volatility.get('std_change', 0) > 2:
        print("  - High market volatility -> Recommend trend-following or breakout strategy")
        strategy_type = "trend_following"
    else:
        print("  - Low market volatility -> Recommend mean reversion strategy")
        strategy_type = "mean_reversion"
    
    # Analyze trend
    trend = stats.get('trend', {})
    if trend.get('bullish_pct', 0) > 60:
        print("  - Predominantly uptrend -> Bias towards long positions")
    elif trend.get('bearish_pct', 0) > 60:
        print("  - Predominantly downtrend -> Bias towards short positions or stay on sidelines")
    else:
        print("  - Ranging market -> Use range trading")
    
    # Analyze signal frequency
    ma_cross = patterns.get('ma_cross', {})
    print(f"  - MA crossover signals: Golden cross {ma_cross.get('golden', 0)} times, Death cross {ma_cross.get('death', 0)} times")
    
    rsi_signals = patterns.get('rsi', {})
    print(f"  - RSI signals: Overbought {rsi_signals.get('overbought', 0)} times, Oversold {rsi_signals.get('oversold', 0)} times")
    
    print(f"\nRecommended strategy type: {strategy_type}")
    print("\nStrategy development complete")
    print("Next step: Backtest to verify strategy performance")
    
    return strategy_type


def step3_backtesting(strategy_type: str):
    """Step 3: Strategy Backtesting - Verify strategy's historical performance"""
    print("\n" + "="*80)
    print("Step 3/4: Strategy Backtesting")
    print("="*80)
    print("\nGoal: Verify strategy's profitability and risk level on historical data\n")
    
    from research.backtester import Backtester, simple_ma_crossover_strategy, rsi_mean_reversion_strategy
    
    backtester = Backtester()
    
    # Select backtest strategy based on strategy type
    if strategy_type == "mean_reversion":
        print("[Backtest Strategy: RSI Mean Reversion]")
        strategy_func = rsi_mean_reversion_strategy
    else:
        print("[Backtest Strategy: MA Crossover Trend Following]")
        strategy_func = simple_ma_crossover_strategy
    
    # Run backtest
    results = backtester.run_backtest(
        strategy_func=strategy_func,
        symbol="BTCUSDT",
        interval="1h",
        days=30,
        initial_capital=10000.0,
        position_size=0.3  # 30% position size for risk control
    )
    
    # Save results
    backtester.save_results(results)
    
    # Evaluate backtest results
    print("\nBacktest Evaluation:")
    
    if results['total_return_pct'] > 0:
        print(f"  Strategy profitable: {results['total_return_pct']:+.2f}%")
    else:
        print(f"  Strategy loss: {results['total_return_pct']:+.2f}%")
    
    if results['win_rate'] > 50:
        print(f"  Good win rate: {results['win_rate']:.1f}%")
    else:
        print(f"  Low win rate: {results['win_rate']:.1f}%")
    
    if results['max_drawdown'] > -20:
        print(f"  Drawdown acceptable: {results['max_drawdown']:.2f}%")
    else:
        print(f"  Large drawdown: {results['max_drawdown']:.2f}%")
    
    # Decide if ready for live trading
    can_go_live = (
        results['total_return_pct'] > 0 and
        results['win_rate'] > 40 and
        results['max_drawdown'] > -30
    )
    
    if can_go_live:
        print("\nBacktest passed, strategy can proceed to live testing")
    else:
        print("\nBacktest results not ideal, recommend optimizing strategy parameters or changing strategy")
    
    print("\nStrategy backtesting complete")
    print("Next step: Run strategy live (small amount testing)")
    
    return results, can_go_live


def step4_live_trading(strategy_type: str, can_go_live: bool):
    """Step 4: Live Trading - Run strategy in live market environment"""
    print("\n" + "="*80)
    print("Step 4/4: Live Strategy Execution")
    print("="*80)
    print("\nGoal: Run strategy in live market, generate trading signals\n")
    
    if not can_go_live:
        print("Backtest results not ideal, recommend optimizing strategy first")
        print("You can still run live signal generation to observe strategy performance")
        response = input("\nContinue running live strategy? (y/n): ")
        if response.lower() != 'y':
            print("Live execution cancelled")
            return
    
    print("Starting live strategy monitoring...")
    print("This is demo mode, no real trades will be executed\n")
    
    # Import live execution script
    from run_strategy_live import main as run_live
    
    # Run a few live signal generations
    for i in range(3):
        print(f"\n--- Signal generation #{i+1} ---")
        run_live()
        
        if i < 2:
            print("\nWaiting 60 seconds before next check...")
            time.sleep(60)
    
    print("\nLive strategy execution demo complete")
    print("\nNext Steps Recommendations:")
    print("  1. Continuously monitor strategy performance")
    print("  2. Record all trading signals and results")
    print("  3. Regularly backtest and optimize parameters")
    print("  4. Strictly execute risk management (stop loss, position sizing)")
    print("  5. Consider multi-strategy portfolio for risk diversification")


def main():
    """Run complete strategy development workflow"""
    print("\n" + "="*80)
    print("AI Trader - Complete Strategy Development Workflow")
    print("="*80)
    print("\nThis workflow will guide you through:")
    print("  1. Data Research - Explore market patterns")
    print("  2. Strategy Development - Design trading strategy")
    print("  3. Backtesting - Verify strategy performance")
    print("  4. Live Execution - Generate trading signals")
    print("\n" + "="*80)
    
    try:
        # Step 1: Data research
        research_results = step1_data_research()
        
        if research_results is None:
            print("\nData research failed, workflow terminated")
            return
        
        input("\nPress Enter to continue to next step...")
        
        # Step 2: Strategy development
        strategy_type = step2_strategy_development(research_results)
        
        input("\nPress Enter to continue to next step...")
        
        # Step 3: Backtesting
        backtest_results, can_go_live = step3_backtesting(strategy_type)
        
        input("\nPress Enter to continue to next step...")
        
        # Step 4: Live execution
        step4_live_trading(strategy_type, can_go_live)
        
        print("\n" + "="*80)
        print("Complete workflow demo finished!")
        print("="*80)
        print("\nRelated Documentation:")
        print("  - STRATEGY_DEVELOPMENT_GUIDE.md - Strategy Development Guide")
        print("  - DATA_PIPELINE.md - Data Pipeline Documentation")
        print("  - research/outputs/ - Research and backtest results")
        
    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user")
    except Exception as e:
        print(f"\n\nError occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
