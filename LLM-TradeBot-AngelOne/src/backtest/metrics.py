"""
Backtest Performance Metrics
===================================

Calculate various performance metrics for backtesting

Author: AI Trader Team
Date: 2025-12-31
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import timedelta

from src.backtest.portfolio import Trade, Side


@dataclass
class MetricsResult:
    """Performance metrics result"""
    # Return metrics
    total_return: float           # Total return (%)
    annualized_return: float      # Annualized return (%)
    final_equity: float           # Final equity ($)
    profit_amount: float          # Profit/loss amount ($)
    max_drawdown: float           # Maximum drawdown ($)
    max_drawdown_pct: float       # Maximum drawdown (%)
    max_drawdown_duration: int    # Maximum drawdown duration (days)
    
    # Risk metrics
    sharpe_ratio: float           # Sharpe ratio
    sortino_ratio: float          # Sortino ratio
    calmar_ratio: float           # Calmar ratio
    volatility: float             # Annualized volatility (%)
    
    # Trade statistics
    total_trades: int             # Total number of trades
    winning_trades: int           # Number of winning trades
    losing_trades: int            # Number of losing trades
    win_rate: float               # Win rate (%)
    profit_factor: float          # Profit factor
    avg_trade_pnl: float          # Average PnL per trade ($)
    avg_win: float                # Average win ($)
    avg_loss: float               # Average loss ($)
    largest_win: float            # Largest single win ($)
    largest_loss: float           # Largest single loss ($)
    avg_holding_time: float       # Average holding time (hours)
    
    # Long/Short statistics
    long_trades: int              # Number of long trades
    short_trades: int             # Number of short trades
    long_win_rate: float          # Long win rate (%)
    short_win_rate: float         # Short win rate (%)
    long_pnl: float               # Long total PnL ($)
    short_pnl: float              # Short total PnL ($)
    
    # Time statistics
    start_date: str
    end_date: str
    total_days: int
    trading_days: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            # Return metrics
            'total_return': f"{self.total_return:.2f}%",
            # 'annualized_return': f"{self.annualized_return:.2f}%",  # Removed: misleading for short backtests
            'final_equity': f"{self.final_equity:.2f}",
            'profit_amount': f"{self.profit_amount:+.2f}",
            'max_drawdown': f"${self.max_drawdown:.2f}",
            'max_drawdown_pct': f"{self.max_drawdown_pct:.2f}%",
            'max_drawdown_duration': f"{self.max_drawdown_duration} days",
            
            # Risk metrics
            'sharpe_ratio': f"{self.sharpe_ratio:.2f}",
            'sortino_ratio': f"{self.sortino_ratio:.2f}",
            'calmar_ratio': f"{self.calmar_ratio:.2f}",
            'volatility': f"{self.volatility:.2f}%",
            
            # Trade statistics
            'total_trades': self.total_trades,
            'win_rate': f"{self.win_rate:.1f}%",
            'profit_factor': f"{self.profit_factor:.2f}",
            'avg_trade_pnl': f"${self.avg_trade_pnl:.2f}",
            'avg_win': f"${self.avg_win:.2f}",
            'avg_loss': f"${self.avg_loss:.2f}",
            'largest_win': f"${self.largest_win:.2f}",
            'largest_loss': f"${self.largest_loss:.2f}",
            'avg_holding_time': f"{self.avg_holding_time:.1f}h",
            
            # Long/Short statistics
            'long_trades': self.long_trades,
            'short_trades': self.short_trades,
            'long_win_rate': f"{self.long_win_rate:.1f}%",
            'short_win_rate': f"{self.short_win_rate:.1f}%",
            'long_pnl': f"${self.long_pnl:.2f}",
            'short_pnl': f"${self.short_pnl:.2f}",
            
            # Time statistics
            'period': f"{self.start_date} to {self.end_date}",
            'total_days': self.total_days,
            'trading_days': self.trading_days,
        }


class PerformanceMetrics:
    """
    Backtest Performance Metrics Calculator
    
    Calculates:
    - Return metrics (total return, annualized return, max drawdown)
    - Risk metrics (Sharpe ratio, Sortino ratio, volatility)
    - Trade metrics (win rate, profit factor, average PnL)
    """
    
    RISK_FREE_RATE = 0.02  # Risk-free rate (2%)
    TRADING_DAYS_PER_YEAR = 365  # Crypto 365 days
    
    @classmethod
    def calculate(
        cls,
        equity_curve: pd.DataFrame,
        trades: List[Trade],
        initial_capital: float
    ) -> MetricsResult:
        """
        Calculate all performance metrics
        
        Args:
            equity_curve: Equity curve DataFrame (columns: total_equity, drawdown, drawdown_pct)
            trades: List of trade records
            initial_capital: Initial capital
            
        Returns:
            MetricsResult object
        """
        # Filter closed trades (trades with PnL)
        closed_trades = [t for t in trades if t.action == "close"]
        
        # Calculate return metrics
        total_return, annualized_return = cls._calculate_returns(
            equity_curve, initial_capital
        )
        
        # Calculate max drawdown
        max_dd, max_dd_pct, max_dd_duration = cls._calculate_max_drawdown(equity_curve)
        
        # Calculate risk metrics (use total return instead of annualized return)
        sharpe, sortino, calmar, volatility = cls._calculate_risk_metrics(
            equity_curve, total_return, max_dd_pct  # Changed: use total_return
        )
        
        # Calculate trade statistics
        trade_stats = cls._calculate_trade_stats(closed_trades)
        
        # Calculate long/short statistics
        long_stats, short_stats = cls._calculate_side_stats(closed_trades)
        
        # Time statistics
        if not equity_curve.empty:
            start_date = equity_curve.index[0].strftime("%Y-%m-%d")
            end_date = equity_curve.index[-1].strftime("%Y-%m-%d")
            total_days = (equity_curve.index[-1] - equity_curve.index[0]).days
        else:
            start_date = end_date = "N/A"
            total_days = 0
        
        trading_days = len(set(t.timestamp.date() for t in closed_trades))
        
        # Calculate final equity and profit amount
        final_equity = equity_curve['total_equity'].iloc[-1] if not equity_curve.empty else initial_capital
        profit_amount = final_equity - initial_capital
        
        return MetricsResult(
            # Return metrics
            total_return=total_return,
            annualized_return=annualized_return,
            final_equity=final_equity,
            profit_amount=profit_amount,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_duration=max_dd_duration,
            
            # Risk metrics
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            volatility=volatility,
            
            # Trade statistics
            total_trades=trade_stats['total'],
            winning_trades=trade_stats['winning'],
            losing_trades=trade_stats['losing'],
            win_rate=trade_stats['win_rate'],
            profit_factor=trade_stats['profit_factor'],
            avg_trade_pnl=trade_stats['avg_pnl'],
            avg_win=trade_stats['avg_win'],
            avg_loss=trade_stats['avg_loss'],
            largest_win=trade_stats['largest_win'],
            largest_loss=trade_stats['largest_loss'],
            avg_holding_time=trade_stats['avg_holding_time'],
            
            # Long/Short statistics
            long_trades=long_stats['count'],
            short_trades=short_stats['count'],
            long_win_rate=long_stats['win_rate'],
            short_win_rate=short_stats['win_rate'],
            long_pnl=long_stats['total_pnl'],
            short_pnl=short_stats['total_pnl'],
            
            # Time statistics
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            trading_days=trading_days,
        )
    
    @classmethod
    def _calculate_returns(
        cls,
        equity_curve: pd.DataFrame,
        initial_capital: float
    ) -> Tuple[float, float]:
        """Calculate returns"""
        if equity_curve.empty:
            return 0.0, 0.0
        
        final_equity = equity_curve['total_equity'].iloc[-1]
        total_return = (final_equity - initial_capital) / initial_capital * 100
        
        # Annualized return
        days = (equity_curve.index[-1] - equity_curve.index[0]).days
        if days > 0:
            annualized_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100
        else:
            annualized_return = 0.0
        
        return total_return, annualized_return
    
    @classmethod
    def _calculate_max_drawdown(
        cls,
        equity_curve: pd.DataFrame
    ) -> Tuple[float, float, int]:
        """Calculate maximum drawdown"""
        if equity_curve.empty:
            return 0.0, 0.0, 0
        
        equity = equity_curve['total_equity']
        
        # Calculate rolling maximum
        rolling_max = equity.expanding().max()
        drawdown = rolling_max - equity
        drawdown_pct = drawdown / rolling_max * 100
        
        max_dd = drawdown.max()
        max_dd_pct = drawdown_pct.max()
        
        # Calculate max drawdown duration
        max_dd_duration = 0
        if max_dd > 0:
            # Find max drawdown start and end positions
            peak_idx = equity[:drawdown.idxmax()].idxmax()
            recovery_candidates = equity[drawdown.idxmax():]
            recovery_candidates = recovery_candidates[recovery_candidates >= equity[peak_idx]]
            
            if not recovery_candidates.empty:
                recovery_idx = recovery_candidates.index[0]
                max_dd_duration = (recovery_idx - peak_idx).days
            else:
                # Not yet recovered
                max_dd_duration = (equity.index[-1] - peak_idx).days
        
        return max_dd, max_dd_pct, max_dd_duration
    
    @classmethod
    def _calculate_risk_metrics(
        cls,
        equity_curve: pd.DataFrame,
        total_return: float,  # Changed from annualized_return
        max_dd_pct: float
    ) -> Tuple[float, float, float, float]:
        """Calculate risk metrics"""
        if equity_curve.empty or len(equity_curve) < 2:
            return 0.0, 0.0, 0.0, 0.0
        
        # Calculate daily returns
        equity = equity_curve['total_equity']
        daily_returns = equity.pct_change().dropna()
        
        if daily_returns.empty:
            return 0.0, 0.0, 0.0, 0.0
        
        # Calculate volatility for backtest period (not annualized)
        volatility = daily_returns.std() * 100
        
        # Sharpe ratio (use total return, not annualized)
        # For short-term backtests, using total return is more reasonable
        risk_free_return = cls.RISK_FREE_RATE * len(daily_returns) / cls.TRADING_DAYS_PER_YEAR * 100
        excess_return = total_return - risk_free_return
        sharpe = excess_return / (volatility * np.sqrt(len(daily_returns))) if volatility > 0 else 0.0
        
        # Sortino ratio (only considers downside volatility)
        negative_returns = daily_returns[daily_returns < 0]
        if len(negative_returns) > 0:
            downside_std = negative_returns.std() * 100
            sortino = excess_return / (downside_std * np.sqrt(len(daily_returns))) if downside_std > 0 else 0.0
        else:
            sortino = 0.0
        
        # Calmar ratio (use total return)
        calmar = total_return / max_dd_pct if max_dd_pct > 0 else 0.0
        
        # Annualized volatility (for display only)
        annualized_volatility = daily_returns.std() * np.sqrt(cls.TRADING_DAYS_PER_YEAR) * 100
        
        return sharpe, sortino, calmar, annualized_volatility
    
    @classmethod
    def _calculate_trade_stats(cls, trades: List[Trade]) -> Dict:
        """Calculate trade statistics"""
        if not trades:
            return {
                'total': 0, 'winning': 0, 'losing': 0,
                'win_rate': 0.0, 'profit_factor': 0.0,
                'avg_pnl': 0.0, 'avg_win': 0.0, 'avg_loss': 0.0,
                'largest_win': 0.0, 'largest_loss': 0.0,
                'avg_holding_time': 0.0,
            }
        
        pnls = [t.pnl for t in trades]
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]
        holding_times = [t.holding_time for t in trades if t.holding_time is not None]
        
        total_win = sum(winning) if winning else 0
        total_loss = abs(sum(losing)) if losing else 0
        
        return {
            'total': len(trades),
            'winning': len(winning),
            'losing': len(losing),
            'win_rate': len(winning) / len(trades) * 100 if trades else 0,
            'profit_factor': total_win / total_loss if total_loss > 0 else float('inf'),
            'avg_pnl': sum(pnls) / len(pnls) if pnls else 0,
            'avg_win': sum(winning) / len(winning) if winning else 0,
            'avg_loss': sum(losing) / len(losing) if losing else 0,
            'largest_win': max(pnls) if pnls else 0,
            'largest_loss': min(pnls) if pnls else 0,
            'avg_holding_time': sum(holding_times) / len(holding_times) if holding_times else 0,
        }
    
    @classmethod
    def _calculate_side_stats(cls, trades: List[Trade]) -> Tuple[Dict, Dict]:
        """Calculate long/short statistics"""
        long_trades = [t for t in trades if t.side == Side.LONG]
        short_trades = [t for t in trades if t.side == Side.SHORT]
        
        def calc_side(trade_list):
            if not trade_list:
                return {'count': 0, 'win_rate': 0.0, 'total_pnl': 0.0}
            
            winning = sum(1 for t in trade_list if t.pnl > 0)
            total_pnl = sum(t.pnl for t in trade_list)
            
            return {
                'count': len(trade_list),
                'win_rate': winning / len(trade_list) * 100,
                'total_pnl': total_pnl,
            }
        
        return calc_side(long_trades), calc_side(short_trades)
    
    @classmethod
    def generate_monthly_returns(cls, equity_curve: pd.DataFrame) -> pd.DataFrame:
        """Generate monthly return statistics"""
        if equity_curve.empty:
            return pd.DataFrame()
        
        equity = equity_curve['total_equity']
        
        # Resample to monthly
        monthly = equity.resample('M').last()
        monthly_returns = monthly.pct_change() * 100
        
        # Convert to pivot table format (year x month)
        monthly_returns = monthly_returns.dropna()
        if monthly_returns.empty:
            return pd.DataFrame()
        
        df = pd.DataFrame({
            'year': monthly_returns.index.year,
            'month': monthly_returns.index.month,
            'return': monthly_returns.values
        })
        
        pivot = df.pivot(index='year', columns='month', values='return')
        pivot.columns = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][:len(pivot.columns)]
        
        return pivot


# Test function
def test_metrics():
    """Test performance metrics calculation"""
    print("\n" + "=" * 60)
    print("🧪 Testing PerformanceMetrics")
    print("=" * 60)
    
    # Create mock data
    from datetime import datetime, timedelta
    
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    np.random.seed(42)
    
    # Simulate equity curve
    returns = np.random.normal(0.002, 0.02, 100)
    equity = 10000 * np.cumprod(1 + returns)
    
    equity_curve = pd.DataFrame({
        'total_equity': equity,
        'drawdown': 0,
        'drawdown_pct': 0,
    }, index=dates)
    
    # Simulate trades
    trades = []
    for i in range(10):
        pnl = np.random.uniform(-100, 200)
        trades.append(Trade(
            trade_id=i,
            symbol="BTCUSDT",
            side=Side.LONG if i % 2 == 0 else Side.SHORT,
            action="close",
            quantity=0.01,
            price=50000,
            timestamp=dates[i * 10],
            pnl=pnl,
            pnl_pct=pnl / 500 * 100,
            holding_time=np.random.uniform(1, 48),
        ))
    
    # Calculate metrics
    metrics = PerformanceMetrics.calculate(equity_curve, trades, 10000)
    
    print("\n📊 Performance Metrics:")
    for k, v in metrics.to_dict().items():
        print(f"   {k}: {v}")
    
    print("\n✅ PerformanceMetrics test complete!")


if __name__ == "__main__":
    test_metrics()
