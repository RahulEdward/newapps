"""
Historical Data Replay Agent
=============================

Simulates DataSyncAgent, generates MarketSnapshot from historical data
Used to provide the same data interface as live trading during backtesting

Author: AI Trader Team
Date: 2025-12-31
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Iterator, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
import os

# Use AngelOne client for Indian market data
try:
    from src.api.angelone.angelone_client import AngelOneClient
except ImportError:
    AngelOneClient = None

from src.agents.data_sync_agent import MarketSnapshot
from src.utils.logger import log


@dataclass
class FundingRateRecord:
    """Funding rate record"""
    timestamp: datetime
    funding_rate: float
    mark_price: float


@dataclass
class DataCache:
    """Historical data cache"""
    symbol: str
    df_5m: pd.DataFrame
    df_15m: pd.DataFrame
    df_1h: pd.DataFrame
    start_date: datetime
    end_date: datetime
    funding_rates: List['FundingRateRecord'] = field(default_factory=list)  # Funding rate history



class DataReplayAgent:
    """
    Historical Data Replay Agent
    
    Features:
    1. Fetch historical K-line data from AngelOne
    2. Local cache (Parquet format)
    3. Generate MarketSnapshot at specified time points
    4. Simulate real-time data stream for backtesting
    """
    
    CACHE_DIR = "data/backtest_cache"
    
    def __init__(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        client: 'AngelOneClient' = None
    ):
        """
        Initialize data replay agent
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE")
            start_date: Start date "YYYY-MM-DD" or "YYYY-MM-DD HH:MM"
            end_date: End date "YYYY-MM-DD" or "YYYY-MM-DD HH:MM"
            client: AngelOne client (optional)
        """
        self.symbol = symbol
        
        # Smart Date Parsing
        try:
            self.start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M")
        except ValueError:
            self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
            
        try:
            # If HH:MM is provided, use it exactly
            self.end_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M")
        except ValueError:
            # If only YYYY-MM-DD, add 1 day to include the full end day
            dt = datetime.strptime(end_date, "%Y-%m-%d")
            self.end_date = dt + timedelta(days=1)
            
        self.client = client
        
        # Data cache
        self.data_cache: Optional[DataCache] = None
        
        # Current replay position
        self.current_idx = 0
        self.timestamps: List[datetime] = []
        
        # Latest snapshot (simulates DataSyncAgent.latest_snapshot)
        self.latest_snapshot: Optional[MarketSnapshot] = None
        
        # Ensure cache directory exists
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        
        log.info(f"📼 DataReplayAgent initialized | {symbol} | {self.start_date} to {self.end_date}")
    
    async def load_data(self) -> bool:
        """
        Load historical data (prioritize reading from cache)
        
        Returns:
            Whether loading was successful
        """
        cache_file = self._get_cache_path()
        
        # Try to load from cache
        if os.path.exists(cache_file):
            log.info(f"📂 Loading cached data from {cache_file}")
            try:
                self._load_from_cache(cache_file)
                # Verify we actually got data for range
                if not self.timestamps:
                    log.warning("Cache loaded but no timestamps in range. Retrying fetch...")
                else:
                    log.info(f"✅ Loaded {len(self.timestamps)} timestamps from cache")
                    return True
            except Exception as e:
                log.warning(f"Cache load failed: {e}, fetching from API...")
        
        # Fetch from API
        log.info(f"📥 Fetching historical data from AngelOne API...")
        try:
            await self._fetch_from_api()
            # Save to cache
            self._save_to_cache(cache_file)
            log.info(f"✅ Fetched and cached {len(self.timestamps)} timestamps")
            return True
        except Exception as e:
            log.error(f"❌ Failed to fetch historical data: {e}")
            return False
    
    def _get_cache_path(self) -> str:
        """Generate cache file path"""
        # Use simple date string for cache key to maximize hits
        # (Even if precise time is used, we cache the whole day range usually)
        # But here start/end might be mid-day. 
        # Strategy: Cache based on DATE part only to allow reuse for different times on same days.
        start_str = self.start_date.strftime("%Y%m%d")
        
        # Use the DATE part of end_date (minus a microsecond to handle clean midnight?)
        # Actually safest is to use the requested window.
        # But if I request 16:00, and later request 00:00, different cache?
        # Ideally cache should cover the widest range.
        # For simplicity, just use the exact request strings converted to safe chars.
        end_str = self.end_date.strftime("%Y%m%d")
        
        # Include lookback in cache path to ensure invalidation when lookback changes
        lookback_days = 30  # Must match the value in _fetch_from_api
        return os.path.join(
            self.CACHE_DIR,
            f"{self.symbol}_{start_str}_{end_str}_lb{lookback_days}.parquet"
        )
    
    async def _fetch_from_api(self):
        """Fetch historical data from AngelOne API"""
        # CRITICAL FIX: Need historical data BEFORE backtest period for technical indicators
        # Add lookback period (default 30 days) before start_date
        lookback_days = 30
        extended_start = self.start_date - timedelta(days=lookback_days)
        
        # Calculate total days including lookback
        total_days = (self.end_date - extended_start).days + 1
        
        # Calculate required candles
        # 5m K-lines: 288 per day
        limit_5m = total_days * 288 * 2 # Safety factor
        # 15m K-lines: 96 per day
        limit_15m = total_days * 96 * 2
        # 1h K-lines: 24 per day
        limit_1h = total_days * 24 * 2
        
        log.info(f"📊 Fetching data from {extended_start.date()} to {self.end_date.date()}")
        log.info(f"   Lookback: {lookback_days} days before backtest start")
        
        # Fetch data using AngelOne client
        if self.client:
            df_5m = await self._fetch_klines_angelone("FIVE_MINUTE", extended_start, self.end_date)
            df_15m = await self._fetch_klines_angelone("FIFTEEN_MINUTE", extended_start, self.end_date)
            df_1h = await self._fetch_klines_angelone("ONE_HOUR", extended_start, self.end_date)
        else:
            # Fallback to empty dataframes if no client
            df_5m = pd.DataFrame()
            df_15m = pd.DataFrame()
            df_1h = pd.DataFrame()
        
        # No funding rates in Indian market (equity/derivatives)
        funding_rates = []
        
        # IMPORTANT: Do NOT filter out historical data before start_date here
        # We need it for technical indicator calculation
        # Only filter data AFTER end_date
        if not df_5m.empty:
            df_5m = df_5m[df_5m.index <= self.end_date]
        if not df_15m.empty:
            df_15m = df_15m[df_15m.index <= self.end_date]
        if not df_1h.empty:
            df_1h = df_1h[df_1h.index <= self.end_date]
        
        # Create cache object
        self.data_cache = DataCache(
            symbol=self.symbol,
            df_5m=df_5m,
            df_15m=df_15m,
            df_1h=df_1h,
            start_date=self.start_date,
            end_date=self.end_date,
            funding_rates=funding_rates
        )
        
        # Generate timestamp list (based on 5m K-lines)
        all_timestamps = df_5m.index.tolist() if not df_5m.empty else []
        
        # Filter timestamps to backtest period only
        # Strict inequality for end_date to avoid processing the exact end second if not in data
        self.timestamps = [ts for ts in all_timestamps if self.start_date <= ts < self.end_date]
        
        log.info(f"   Backtest timestamps (5m): {len(self.timestamps)}")
        if self.timestamps:
            log.info(f"   First: {self.timestamps[0]}, Last: {self.timestamps[-1]}")
    
    async def _fetch_klines_angelone(self, interval: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Fetch K-line data from AngelOne API"""
        if not self.client:
            return pd.DataFrame()
        
        try:
            # Use AngelOne client's get_klines method
            klines = await self.client.get_klines(
                symbol=self.symbol,
                interval=interval,
                from_date=start.strftime("%Y-%m-%d %H:%M"),
                to_date=end.strftime("%Y-%m-%d %H:%M")
            )
            
            if not klines:
                return pd.DataFrame()
            
            # Convert to DataFrame
            return self._klines_to_dataframe(klines)
            
        except Exception as e:
            log.warning(f"Failed to fetch {interval} data: {e}")
            return pd.DataFrame()
    
    async def _fetch_funding_rates(self) -> List[FundingRateRecord]:
        """
        Fetch funding rate historical data
        Note: Indian equity market doesn't have funding rates like crypto futures
        This method is kept for compatibility but returns empty list
        """
        # Indian market doesn't have funding rates
        return []
    
    async def _fetch_klines_batched(self, interval: str, total_limit: int) -> pd.DataFrame:
        """Fetch K-line data in batches - legacy method for compatibility"""
        # Map old interval format to AngelOne format
        interval_map = {
            "5m": "FIVE_MINUTE",
            "15m": "FIFTEEN_MINUTE",
            "1h": "ONE_HOUR",
            "1d": "ONE_DAY"
        }
        angelone_interval = interval_map.get(interval, "FIVE_MINUTE")
        
        # Calculate date range
        lookback_days = 30
        extended_start = self.start_date - timedelta(days=lookback_days)
        
        return await self._fetch_klines_angelone(angelone_interval, extended_start, self.end_date)
    
    def _klines_to_dataframe(self, klines: List) -> pd.DataFrame:
        """Convert K-line list to DataFrame"""
        if not klines:
            return pd.DataFrame()
        
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # Convert data types
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
            df[col] = df[col].astype(float)
        
        df['trades'] = df['trades'].astype(int)
        
        return df[['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trades']]
    
    def _filter_date_range(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter date range"""
        if df.empty:
            return df
        # Use < instead of <= since end_date is now strictly parsed
        return df[(df.index >= self.start_date) & (df.index < self.end_date)]
    
    def _save_to_cache(self, cache_path: str):
        """Save data to cache"""
        if self.data_cache is None:
            return
        
        # Merge all data
        cache_data = {
            'df_5m': self.data_cache.df_5m,
            'df_15m': self.data_cache.df_15m,
            'df_1h': self.data_cache.df_1h,
            'funding_rates': [
                {'timestamp': fr.timestamp, 'funding_rate': fr.funding_rate, 'mark_price': fr.mark_price}
                for fr in self.data_cache.funding_rates
            ],
            # Save date boundaries to verify cache validity
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        
        # Use pickle to save (supports multiple DataFrames)
        import pickle
        with open(cache_path, 'wb') as f:
            pickle.dump(cache_data, f)
    
    def _load_from_cache(self, cache_path: str):
        """Load data from cache"""
        import pickle
        with open(cache_path, 'rb') as f:
            cache_data = pickle.load(f)
        
        # Load funding rates (compatible with old cache)
        funding_rates = []
        if 'funding_rates' in cache_data:
            for fr_dict in cache_data['funding_rates']:
                funding_rates.append(FundingRateRecord(
                    timestamp=fr_dict['timestamp'],
                    funding_rate=fr_dict['funding_rate'],
                    mark_price=fr_dict.get('mark_price', 0)
                ))
        
        # Reconstruct DataCache
        self.data_cache = DataCache(
            symbol=self.symbol,
            df_5m=cache_data['df_5m'],
            df_15m=cache_data['df_15m'],
            df_1h=cache_data['df_1h'],
            start_date=self.start_date,
            end_date=self.end_date,
            funding_rates=funding_rates
        )
        
        self.timestamps = [ts for ts in self.data_cache.df_5m.index.tolist() if self.start_date <= ts < self.end_date]
        
        log.info(f"   Date comparison: start_date={self.start_date}, end_date={self.end_date}")
        if not self.timestamps:
            log.warning(f"   ⚠️ Cache loaded but zero timestamps in requested range!")
        else:
            log.info(f"   Cached range: {self.timestamps[0]} to {self.timestamps[-1]}")
            log.info(f"   Backtest timestamps: {len(self.timestamps)}")
    
    def get_snapshot_at(self, timestamp: datetime, lookback: int = 1000) -> MarketSnapshot:
        """
        Get market snapshot at specified time point
        
        Args:
            timestamp: Target time point
            lookback: Number of K-lines to look back (5m candles). Defaults to 1000 (~3.5 days) to ensure enough 1h data.
            
        Returns:
            MarketSnapshot object (compatible with DataSyncAgent)
        """
        if self.data_cache is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        
        # Get data up to timestamp
        # Ensure we have enough data for 1h analysis (need > 60 candles)
        # 1000 5m candles = 83 1h candles.
        
        df_5m = self.data_cache.df_5m[self.data_cache.df_5m.index <= timestamp].tail(lookback)
        
        # For 15m and 1h, we need at least 100 candles to be safe for indicators
        lb_15m = max(lookback // 3, 100)
        lb_1h = max(lookback // 12, 100)
        
        df_15m = self.data_cache.df_15m[self.data_cache.df_15m.index <= timestamp].tail(lb_15m)
        df_1h = self.data_cache.df_1h[self.data_cache.df_1h.index <= timestamp].tail(lb_1h)
        
        # Stable view: exclude last candle (incomplete)
        # Live view: last candle (as Dict)
        live_5m_dict = df_5m.iloc[-1].to_dict() if len(df_5m) > 0 else {}
        live_15m_dict = df_15m.iloc[-1].to_dict() if len(df_15m) > 0 else {}
        live_1h_dict = df_1h.iloc[-1].to_dict() if len(df_1h) > 0 else {}
        
        snapshot = MarketSnapshot(
            stable_5m=df_5m.iloc[:-1] if len(df_5m) > 1 else df_5m,
            stable_15m=df_15m.iloc[:-1] if len(df_15m) > 1 else df_15m,
            stable_1h=df_1h.iloc[:-1] if len(df_1h) > 1 else df_1h,
            live_5m=live_5m_dict,
            live_15m=live_15m_dict,
            live_1h=live_1h_dict,
            timestamp=timestamp,
            alignment_ok=True,
            fetch_duration=0.0
        )
        
        self.latest_snapshot = snapshot
        return snapshot
    
    def iterate_timestamps(self, step: int = 1) -> Iterator[datetime]:
        """
        Iterate all backtest time points
        
        Args:
            step: Step size (1 = every 5 minutes, 3 = every 15 minutes, 12 = every hour)
            
        Yields:
            datetime time points
        """
        for i in range(0, len(self.timestamps), step):
            self.current_idx = i
            yield self.timestamps[i]
    
    def get_current_price(self) -> float:
        """
        Get current price
        
        CRITICAL FIX (Cycle 2):
        Prevent Look-ahead Bias:
        Return the Open price of current K-line, not the Close price.
        At backtest moment T, we can only see the open price at T, not the close price at T+5m.
        """
        if self.latest_snapshot is None:
            return 0.0
        
        live = self.latest_snapshot.live_5m
        if isinstance(live, dict):
            # Use OPEN price
            return float(live.get('open', 0.0))
        elif hasattr(live, 'empty') and not live.empty:
            # Use OPEN price
            return float(live['open'].iloc[-1])
        return 0.0
    
    def get_open_price(self) -> float:
        """
        Get open price of current K-line
        
        Used to prevent Look-ahead Bias:
        - Signal calculation uses bar[i-1] data
        - Trade execution uses bar[i] open price
        """
        if self.latest_snapshot is None:
            return 0.0
        
        live = self.latest_snapshot.live_5m
        if isinstance(live, dict):
            return float(live.get('open', 0.0))
        elif hasattr(live, 'empty') and not live.empty:
            return float(live['open'].iloc[-1])
        return 0.0
    
    def get_previous_close_price(self) -> float:
        """
        Get close price of previous K-line
        
        Used for Look-ahead Bias protection in signal calculation
        """
        if self.latest_snapshot is None:
            return 0.0
        
        stable = self.latest_snapshot.stable_5m
        if hasattr(stable, 'empty') and not stable.empty:
            return float(stable['close'].iloc[-1])
        return self.get_open_price()
    
    def get_progress(self) -> Tuple[int, int, float]:
        """Get replay progress"""
        total = len(self.timestamps)
        current = self.current_idx
        pct = (current / total * 100) if total > 0 else 0
        return current, total, pct
    
    def get_funding_rate_at(self, timestamp: datetime) -> Optional[FundingRateRecord]:
        """
        Get funding rate at or before specified time point
        
        Binance funding rate settles every 8 hours (UTC 00:00, 08:00, 16:00)
        """
        if self.data_cache is None or not self.data_cache.funding_rates:
            return None
        
        # Find the most recent funding rate before timestamp
        latest_fr = None
        for fr in self.data_cache.funding_rates:
            if fr.timestamp <= timestamp:
                latest_fr = fr
            else:
                break
        
        return latest_fr
    
    def is_funding_settlement_time(self, timestamp: datetime) -> bool:
        """
        Check if it's funding rate settlement time
        
        Note: Indian equity market doesn't have funding rate settlements like crypto
        This method is kept for compatibility but always returns False
        """
        # Indian market doesn't have funding rate settlements
        return False
    
    def get_funding_rate_for_settlement(self, timestamp: datetime) -> Optional[float]:
        """
        Get applicable funding rate at settlement time (returns None if not settlement time)
        """
        if not self.is_funding_settlement_time(timestamp):
            return None
        
        fr = self.get_funding_rate_at(timestamp)
        if fr and abs((fr.timestamp - timestamp).total_seconds()) < 600:  # Within 10 minutes
            return fr.funding_rate
        return None
    
    # ========== DataSyncAgent Compatible Interface ==========
    
    async def fetch_all_timeframes(self, symbol: str = None, limit: int = 300) -> MarketSnapshot:
        """
        Compatible with DataSyncAgent.fetch_all_timeframes interface
        
        In backtest mode, returns snapshot at current time point
        """
        if self.current_idx < len(self.timestamps):
            timestamp = self.timestamps[self.current_idx]
            return self.get_snapshot_at(timestamp, lookback=limit)
        else:
            raise IndexError("Replay finished, no more data")
    
    def get_live_price(self, timeframe: str = '5m') -> float:
        """Compatible with DataSyncAgent.get_live_price interface"""
        return self.get_current_price()
    
    def get_stable_dataframe(self, timeframe: str = '5m') -> pd.DataFrame:
        """Compatible with DataSyncAgent.get_stable_dataframe interface"""
        if self.latest_snapshot is None:
            return pd.DataFrame()
        
        if timeframe == '5m':
            return self.latest_snapshot.stable_5m
        elif timeframe == '15m':
            return self.latest_snapshot.stable_15m
        elif timeframe == '1h':
            return self.latest_snapshot.stable_1h
        else:
            return self.latest_snapshot.stable_5m


# Test function
async def test_data_replay():
    """Test data replay agent"""
    print("\n" + "=" * 60)
    print("🧪 Testing DataReplayAgent")
    print("=" * 60)
    
    # Create replay agent (test 7 days of data)
    replay = DataReplayAgent(
        symbol="RELIANCE",
        start_date="2024-12-01",
        end_date="2024-12-07"
    )
    
    # Load data
    success = await replay.load_data()
    print(f"\n✅ Data loaded: {success}")
    
    if success:
        # Iterate first 5 time points
        print("\n📊 First 5 timestamps:")
        for i, ts in enumerate(replay.iterate_timestamps()):
            if i >= 5:
                break
            snapshot = replay.get_snapshot_at(ts)
            price = replay.get_current_price()
            print(f"   {i+1}. {ts} | Price: ₹{price:.2f}")
        
        # Show progress
        current, total, pct = replay.get_progress()
        print(f"\n📈 Progress: {current}/{total} ({pct:.1f}%)")
    
    print("\n✅ DataReplayAgent test complete!")


if __name__ == "__main__":
    asyncio.run(test_data_replay())
