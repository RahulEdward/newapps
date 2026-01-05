"""
Data Research Tool - For exploring historical market data and discovering trading patterns

Features:
1. Fetch historical candlestick data
2. Calculate technical indicators
3. Visualization analysis
4. Statistical analysis and pattern recognition
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional
import json

from src.api.binance_client import BinanceClient
from src.data.processor import MarketDataProcessor
from src.config import Config


class DataExplorer:
    """Historical Data Exploration Tool"""
    
    def __init__(self):
        """Initialize data explorer"""
        self.config = Config()
        self.client = BinanceClient()
        self.processor = MarketDataProcessor()
        
        # Set plotting style
        sns.set_style("darkgrid")
        plt.rcParams['figure.figsize'] = (15, 10)
        
    def fetch_historical_data(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1h",
        days: int = 30
    ) -> pd.DataFrame:
        """
        Fetch historical candlestick data
        
        Args:
            symbol: Trading pair
            interval: Candlestick interval
            days: Number of historical days
            
        Returns:
            Raw candlestick data DataFrame
        """
        print(f"\n{'='*60}")
        print(f"Fetching historical data: {symbol} ({interval}), last {days} days")
        print(f"{'='*60}")
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Convert to millisecond timestamps
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        # Fetch candlestick data
        klines = self.client.get_klines(
            symbol=symbol,
            interval=interval,
            start_time=start_ms,
            end_time=end_ms,
            limit=1000
        )
        
        if not klines:
            print(f"No data retrieved")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # Data type conversion
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
        
        print(f"Successfully fetched {len(df)} candlesticks")
        print(f"Time range: {df['open_time'].min()} to {df['open_time'].max()}")
        print(f"\nData preview:")
        print(df[['open_time', 'open', 'high', 'low', 'close', 'volume']].head())
        
        return df
    
    def analyze_data(self, df: pd.DataFrame) -> Dict:
        """
        Analyze data statistical features
        
        Args:
            df: Candlestick data DataFrame
            
        Returns:
            Statistical analysis results
        """
        if df.empty:
            return {}
        
        print(f"\n{'='*60}")
        print("Data Statistical Analysis")
        print(f"{'='*60}")
        
        # Basic statistics
        stats = {
            'count': len(df),
            'price_range': {
                'min': float(df['low'].min()),
                'max': float(df['high'].max()),
                'mean': float(df['close'].mean()),
                'std': float(df['close'].std())
            },
            'volume': {
                'total': float(df['volume'].sum()),
                'mean': float(df['volume'].mean()),
                'max': float(df['volume'].max())
            }
        }
        
        # Price change analysis
        df['price_change'] = df['close'].pct_change() * 100
        df['price_range'] = ((df['high'] - df['low']) / df['low'] * 100)
        
        stats['volatility'] = {
            'mean_change': float(df['price_change'].mean()),
            'std_change': float(df['price_change'].std()),
            'max_rise': float(df['price_change'].max()),
            'max_fall': float(df['price_change'].min()),
            'mean_range': float(df['price_range'].mean())
        }
        
        # Trend analysis
        sma_20 = df['close'].rolling(window=20).mean()
        df['trend'] = df['close'] > sma_20
        
        bullish_count = df['trend'].sum()
        bearish_count = len(df) - bullish_count
        
        stats['trend'] = {
            'bullish_pct': float(bullish_count / len(df) * 100),
            'bearish_pct': float(bearish_count / len(df) * 100)
        }
        
        # Print statistical results
        print(f"\nBasic Statistics:")
        print(f"  Total candlesticks: {stats['count']}")
        print(f"  Price range: {stats['price_range']['min']:.2f} - {stats['price_range']['max']:.2f}")
        print(f"  Average price: {stats['price_range']['mean']:.2f} +/- {stats['price_range']['std']:.2f}")
        
        print(f"\nVolatility Analysis:")
        print(f"  Average change: {stats['volatility']['mean_change']:.3f}%")
        print(f"  Volatility std: {stats['volatility']['std_change']:.3f}%")
        print(f"  Max rise: {stats['volatility']['max_rise']:.2f}%")
        print(f"  Max fall: {stats['volatility']['max_fall']:.2f}%")
        print(f"  Average range: {stats['volatility']['mean_range']:.2f}%")
        
        print(f"\nTrend Analysis:")
        print(f"  Bullish periods: {stats['trend']['bullish_pct']:.1f}%")
        print(f"  Bearish periods: {stats['trend']['bearish_pct']:.1f}%")
        
        return stats
    
    def visualize_data(self, df: pd.DataFrame, save_path: Optional[str] = None):
        """
        Visualize data analysis
        
        Args:
            df: Candlestick data DataFrame
            save_path: Save path (optional)
        """
        if df.empty:
            return
        
        print(f"\n{'='*60}")
        print("Generating visualization charts")
        print(f"{'='*60}")
        
        # Create subplots
        fig, axes = plt.subplots(4, 1, figsize=(15, 12))
        
        # 1. Price trend
        axes[0].plot(df['open_time'], df['close'], label='Close Price', linewidth=1)
        sma_20 = df['close'].rolling(window=20).mean()
        sma_50 = df['close'].rolling(window=50).mean()
        axes[0].plot(df['open_time'], sma_20, label='SMA 20', alpha=0.7)
        axes[0].plot(df['open_time'], sma_50, label='SMA 50', alpha=0.7)
        axes[0].set_title('Price Trend with Moving Averages')
        axes[0].set_ylabel('Price (USDT)')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # 2. Volume
        axes[1].bar(df['open_time'], df['volume'], alpha=0.5, color='blue')
        axes[1].set_title('Trading Volume')
        axes[1].set_ylabel('Volume')
        axes[1].grid(True, alpha=0.3)
        
        # 3. Price change rate
        df['price_change'] = df['close'].pct_change() * 100
        colors = ['green' if x > 0 else 'red' for x in df['price_change']]
        axes[2].bar(df['open_time'], df['price_change'], alpha=0.6, color=colors)
        axes[2].set_title('Price Change (%)')
        axes[2].set_ylabel('Change (%)')
        axes[2].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        axes[2].grid(True, alpha=0.3)
        
        # 4. RSI indicator
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        axes[3].plot(df['open_time'], rsi, label='RSI', color='purple', linewidth=1)
        axes[3].axhline(y=70, color='red', linestyle='--', alpha=0.5, label='Overbought (70)')
        axes[3].axhline(y=30, color='green', linestyle='--', alpha=0.5, label='Oversold (30)')
        axes[3].set_title('RSI Indicator')
        axes[3].set_ylabel('RSI')
        axes[3].set_xlabel('Time')
        axes[3].legend()
        axes[3].grid(True, alpha=0.3)
        axes[3].set_ylim(0, 100)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Chart saved to: {save_path}")
        else:
            # Default save path
            os.makedirs('research/outputs', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_path = f'research/outputs/data_analysis_{timestamp}.png'
            plt.savefig(default_path, dpi=300, bbox_inches='tight')
            print(f"Chart saved to: {default_path}")
        
        plt.close()
    
    def find_patterns(self, df: pd.DataFrame) -> Dict:
        """
        Identify trading patterns
        
        Args:
            df: Candlestick data DataFrame
            
        Returns:
            Pattern recognition results
        """
        if df.empty:
            return {}
        
        print(f"\n{'='*60}")
        print("Pattern Recognition Analysis")
        print(f"{'='*60}")
        
        patterns = {}
        
        # 1. Breakout patterns
        df['high_20'] = df['high'].rolling(window=20).max()
        df['low_20'] = df['low'].rolling(window=20).min()
        df['breakout_high'] = df['close'] > df['high_20'].shift(1)
        df['breakout_low'] = df['close'] < df['low_20'].shift(1)
        
        patterns['breakout'] = {
            'upward': int(df['breakout_high'].sum()),
            'downward': int(df['breakout_low'].sum())
        }
        
        # 2. Golden cross and death cross
        sma_10 = df['close'].rolling(window=10).mean()
        sma_30 = df['close'].rolling(window=30).mean()
        df['golden_cross'] = (sma_10 > sma_30) & (sma_10.shift(1) <= sma_30.shift(1))
        df['death_cross'] = (sma_10 < sma_30) & (sma_10.shift(1) >= sma_30.shift(1))
        
        patterns['ma_cross'] = {
            'golden': int(df['golden_cross'].sum()),
            'death': int(df['death_cross'].sum())
        }
        
        # 3. RSI overbought/oversold
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        df['rsi'] = rsi
        df['rsi_overbought'] = rsi > 70
        df['rsi_oversold'] = rsi < 30
        
        patterns['rsi'] = {
            'overbought': int(df['rsi_overbought'].sum()),
            'oversold': int(df['rsi_oversold'].sum())
        }
        
        # 4. Large volatility moves
        df['price_change_pct'] = df['close'].pct_change() * 100
        df['large_up'] = df['price_change_pct'] > 3
        df['large_down'] = df['price_change_pct'] < -3
        
        patterns['volatility'] = {
            'large_up_moves': int(df['large_up'].sum()),
            'large_down_moves': int(df['large_down'].sum())
        }
        
        # Print pattern statistics
        print(f"\nBreakout Patterns:")
        print(f"  Upward breakout: {patterns['breakout']['upward']} times")
        print(f"  Downward breakout: {patterns['breakout']['downward']} times")
        
        print(f"\nMA Crossovers:")
        print(f"  Golden cross: {patterns['ma_cross']['golden']} times")
        print(f"  Death cross: {patterns['ma_cross']['death']} times")
        
        print(f"\nRSI Signals:")
        print(f"  Overbought zone: {patterns['rsi']['overbought']} times")
        print(f"  Oversold zone: {patterns['rsi']['oversold']} times")
        
        print(f"\nLarge Volatility Moves:")
        print(f"  Large rise (>3%): {patterns['volatility']['large_up_moves']} times")
        print(f"  Large fall (<-3%): {patterns['volatility']['large_down_moves']} times")
        
        return patterns
    
    def generate_report(
        self,
        df: pd.DataFrame,
        stats: Dict,
        patterns: Dict,
        save_path: Optional[str] = None
    ):
        """
        Generate research report
        
        Args:
            df: Candlestick data DataFrame
            stats: Statistical analysis results
            patterns: Pattern recognition results
            save_path: Save path (optional)
        """
        print(f"\n{'='*60}")
        print("Generating Research Report")
        print(f"{'='*60}")
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'data_summary': {
                'total_bars': len(df),
                'time_range': {
                    'start': df['open_time'].min().isoformat(),
                    'end': df['open_time'].max().isoformat()
                }
            },
            'statistics': stats,
            'patterns': patterns,
            'recommendations': self._generate_recommendations(stats, patterns)
        }
        
        # Save JSON report
        if not save_path:
            os.makedirs('research/outputs', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = f'research/outputs/research_report_{timestamp}.json'
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Research report saved to: {save_path}")
        
        # Print recommendations
        print(f"\nStrategy Recommendations:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"  {i}. {rec}")
    
    def _generate_recommendations(self, stats: Dict, patterns: Dict) -> List[str]:
        """Generate trading strategy recommendations"""
        recommendations = []
        
        # Volatility-based recommendations
        if stats.get('volatility', {}).get('std_change', 0) > 2:
            recommendations.append("High market volatility - consider breakout or trend-following strategies")
        else:
            recommendations.append("Low market volatility - consider mean reversion strategies")
        
        # Trend-based recommendations
        trend = stats.get('trend', {})
        if trend.get('bullish_pct', 0) > 60:
            recommendations.append("Overall uptrend - consider long strategies")
        elif trend.get('bearish_pct', 0) > 60:
            recommendations.append("Overall downtrend - consider short strategies or stay on sidelines")
        else:
            recommendations.append("Ranging market - consider range trading strategies")
        
        # RSI-based recommendations
        rsi_patterns = patterns.get('rsi', {})
        if rsi_patterns.get('oversold', 0) > rsi_patterns.get('overbought', 0):
            recommendations.append("More RSI oversold signals - potential bounce opportunities")
        elif rsi_patterns.get('overbought', 0) > rsi_patterns.get('oversold', 0):
            recommendations.append("More RSI overbought signals - watch for pullback risks")
        
        return recommendations


def main():
    """Main function - Run complete data exploration workflow"""
    print("\n" + "="*60)
    print("AI Trader - Data Research Tool")
    print("="*60)
    
    # Initialize explorer
    explorer = DataExplorer()
    
    # 1. Fetch historical data
    df = explorer.fetch_historical_data(
        symbol="BTCUSDT",
        interval="1h",
        days=30
    )
    
    if df.empty:
        print("Data fetch failed, exiting")
        return
    
    # 2. Statistical analysis
    stats = explorer.analyze_data(df)
    
    # 3. Pattern recognition
    patterns = explorer.find_patterns(df)
    
    # 4. Visualization
    explorer.visualize_data(df)
    
    # 5. Generate report
    explorer.generate_report(df, stats, patterns)
    
    print(f"\n{'='*60}")
    print("Data research complete!")
    print("="*60)


if __name__ == "__main__":
    main()
