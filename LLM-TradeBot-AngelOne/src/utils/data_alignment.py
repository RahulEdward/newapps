#!/usr/bin/env python3
"""
Data Alignment Helper Module
Provides utility functions for multi-timeframe data alignment and real-time/lagged mode switching

Usage example:
    from src.utils.data_alignment import DataAlignmentHelper
    
    helper = DataAlignmentHelper()
    latest_data = helper.get_aligned_candle(df, timeframe='5m')
"""

import yaml
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from typing import Dict, Optional, Tuple
import logging


class DataAlignmentHelper:
    """Data Alignment Helper Class"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize data alignment helper
        
        Args:
            config_path: Config file path, defaults to config/data_alignment.yaml
        """
        self.logger = logging.getLogger(__name__)
        
        # Load config
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / 'config' / 'data_alignment.yaml'
        
        self.config = self._load_config(config_path)
        self.mode = self.config.get('mode', 'backtest')
        
        # Period duration mapping (minutes)
        self.period_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '12h': 720,
            '1d': 1440, '1w': 10080
        }
        
        self.logger.info(f"Data alignment helper initialized: mode={self.mode}")
    
    def _load_config(self, config_path: Path) -> Dict:
        """Load config file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.warning(f"Unable to load config file {config_path}: {e}, using default config")
            return {
                'mode': 'backtest',
                'timeframe_settings': {}
            }
    
    def get_aligned_candle(
        self, 
        df: pd.DataFrame, 
        timeframe: str,
        now: Optional[datetime] = None
    ) -> Tuple[pd.Series, Dict]:
        """
        Get aligned candlestick data based on config
        
        Args:
            df: Candlestick DataFrame (index is DatetimeIndex)
            timeframe: Period ('5m', '15m', '1h', etc.)
            now: Current time (for calculating lag), defaults to current UTC time
        
        Returns:
            (candle_data, metadata)
            - candle_data: Selected candlestick data (Series)
            - metadata: Metadata dictionary containing:
                - index: Index used (-1 or -2)
                - timestamp: Candlestick time
                - lag_minutes: Lag in minutes
                - is_realtime: Whether real-time candlestick
                - is_completed: Whether candlestick is completed
                - completion_pct: Completion percentage
        """
        if len(df) < 2:
            raise ValueError(f"DataFrame length insufficient: {len(df)} < 2")
        
        if now is None:
            now = datetime.now(timezone.utc)
        
        # Get config for this timeframe
        settings = self.config.get('timeframe_settings', {}).get(timeframe, {})
        
        # Decide whether to use real-time or lagged data
        use_realtime = self._should_use_realtime(timeframe, settings)
        
        if use_realtime:
            # Try to use real-time candlestick
            candle = df.iloc[-1]
            index = -1
            
            # Calculate completion
            completion_pct = self._calculate_completion(df, timeframe, now)
            is_completed = completion_pct >= 100.0
            
            # Check minimum completion requirement
            min_completion = settings.get('min_completion_pct', 0)
            if completion_pct < min_completion:
                self.logger.warning(
                    f"[{timeframe}] Candlestick completion {completion_pct:.1f}% < {min_completion}%, "
                    f"falling back to completed candlestick"
                )
                candle = df.iloc[-2]
                index = -2
                completion_pct = 100.0
                is_completed = True
        else:
            # Use completed candlestick
            candle = df.iloc[-2]
            index = -2
            completion_pct = 100.0
            is_completed = True
        
        # Calculate metadata
        timestamp = df.index[index]
        lag_minutes = self._calculate_lag_minutes(timestamp, now)
        
        metadata = {
            'index': index,
            'timestamp': timestamp,
            'lag_minutes': lag_minutes,
            'is_realtime': (index == -1),
            'is_completed': is_completed,
            'completion_pct': completion_pct,
            'timeframe': timeframe,
            'mode': self.mode
        }
        
        # Check lag warning
        self._check_lag_warning(timeframe, lag_minutes, settings)
        
        return candle, metadata
    
    def _should_use_realtime(self, timeframe: str, settings: Dict) -> bool:
        """Determine whether to use real-time candlestick"""
        
        # Backtest mode: always use completed candlestick
        if self.mode == 'backtest':
            return False
        
        # Live mode: decide based on config
        use_realtime = settings.get('use_realtime', False)
        
        # live_aggressive mode: enable real-time by default (unless explicitly disabled)
        if self.mode == 'live_aggressive' and 'use_realtime' not in settings:
            return True
        
        return use_realtime
    
    def _calculate_completion(
        self, 
        df: pd.DataFrame, 
        timeframe: str, 
        now: datetime
    ) -> float:
        """
        Calculate current candlestick completion percentage
        
        Returns:
            Completion (0-100)
        """
        if len(df) < 1:
            return 0.0
        
        last_time = df.index[-1]
        
        # Ensure timezone consistency
        if last_time.tzinfo is None and now.tzinfo is not None:
            last_time = last_time.tz_localize('UTC')
        elif last_time.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        
        # Get period length
        period_minutes = self.period_minutes.get(timeframe, 5)
        
        # Calculate candlestick expected end time
        candle_end = last_time + pd.Timedelta(minutes=period_minutes)
        
        # Already completed
        if now >= candle_end:
            return 100.0
        
        # Calculate completion
        elapsed = (now - last_time).total_seconds()
        total = period_minutes * 60
        completion = (elapsed / total) * 100
        
        return max(0.0, min(100.0, completion))
    
    def _calculate_lag_minutes(self, data_time: pd.Timestamp, current_time: datetime) -> float:
        """Calculate data lag in minutes"""
        
        # Ensure timezone consistency
        if data_time.tzinfo is None and current_time.tzinfo is not None:
            data_time = data_time.tz_localize('UTC')
        elif data_time.tzinfo is not None and current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        
        lag_seconds = (current_time - data_time).total_seconds()
        return lag_seconds / 60.0
    
    def _check_lag_warning(self, timeframe: str, lag_minutes: float, settings: Dict):
        """Check if lag exceeds threshold and issue warning"""
        
        threshold = settings.get('lag_warning_threshold', 
                                self.config.get('lag_detection', {}).get('warning_threshold_minutes', 30))
        
        if lag_minutes > threshold:
            self.logger.warning(
                f"[{timeframe}] Data lag warning: {lag_minutes:.1f} minutes > {threshold} minute threshold"
            )
    
    def get_multi_timeframe_metadata(
        self, 
        timeframe_data: Dict[str, pd.DataFrame],
        now: Optional[datetime] = None
    ) -> Dict:
        """
        Get metadata and time misalignment analysis for multi-timeframe data
        
        Args:
            timeframe_data: {timeframe: DataFrame} dictionary
            now: Current time
        
        Returns:
            Metadata dictionary containing:
            - timeframes: {timeframe: metadata}
            - time_gap_minutes: Maximum time difference (minutes)
            - earliest_timestamp: Earliest data time
            - latest_timestamp: Latest data time
            - max_lag_minutes: Maximum lag
        """
        if now is None:
            now = datetime.now(timezone.utc)
        
        timeframes_meta = {}
        timestamps = []
        
        for timeframe, df in timeframe_data.items():
            try:
                _, metadata = self.get_aligned_candle(df, timeframe, now)
                timeframes_meta[timeframe] = metadata
                timestamps.append(metadata['timestamp'])
            except Exception as e:
                self.logger.error(f"[{timeframe}] Failed to get metadata: {e}")
        
        if not timestamps:
            return {}
        
        # Calculate time misalignment
        earliest = min(timestamps)
        latest = max(timestamps)
        time_gap = self._calculate_lag_minutes(earliest, latest)
        
        # Calculate maximum lag
        max_lag = max([meta['lag_minutes'] for meta in timeframes_meta.values()])
        
        result = {
            'timeframes': timeframes_meta,
            'time_gap_minutes': time_gap,
            'earliest_timestamp': earliest,
            'latest_timestamp': latest,
            'max_lag_minutes': max_lag,
            'current_time': now
        }
        
        # Time misalignment warning
        gap_threshold = self.config.get('lag_detection', {}).get('time_gap_threshold_minutes', 60)
        if time_gap > gap_threshold:
            self.logger.warning(
                f"⚠️ Severe multi-timeframe time misalignment: {time_gap:.1f} minutes > {gap_threshold} minute threshold"
            )
        
        return result
    
    def format_metadata_log(self, metadata: Dict) -> str:
        """Format metadata as log string"""
        
        if 'timeframes' in metadata:
            # Multi-timeframe metadata
            lines = ["Multi-timeframe data status:"]
            for tf, meta in metadata['timeframes'].items():
                status = "realtime" if meta['is_realtime'] else "lagged"
                lines.append(
                    f"  [{tf:3s}] {meta['timestamp'].strftime('%H:%M:%S')} | "
                    f"Lag: {meta['lag_minutes']:5.1f}min | "
                    f"Completion: {meta['completion_pct']:5.1f}% | "
                    f"Mode: {status}"
                )
            lines.append(f"  Time gap: {metadata['time_gap_minutes']:.1f} minutes")
            lines.append(f"  Max lag: {metadata['max_lag_minutes']:.1f} minutes")
            return "\n".join(lines)
        else:
            # Single timeframe metadata
            status = "realtime" if metadata['is_realtime'] else "lagged"
            return (
                f"[{metadata['timeframe']}] "
                f"Time: {metadata['timestamp'].strftime('%H:%M:%S')} | "
                f"Lag: {metadata['lag_minutes']:.1f}min | "
                f"Completion: {metadata['completion_pct']:.1f}% | "
                f"Mode: {status}"
            )


# Convenience function
def get_aligned_candle(df: pd.DataFrame, timeframe: str, config_path: Optional[str] = None):
    """
    Convenience function: Get aligned candlestick data
    
    Usage example:
        from src.utils.data_alignment import get_aligned_candle
        
        candle, metadata = get_aligned_candle(df, '5m')
        print(f"Data used: {metadata['timestamp']}, lag: {metadata['lag_minutes']} minutes")
    """
    helper = DataAlignmentHelper(config_path)
    return helper.get_aligned_candle(df, timeframe)


if __name__ == "__main__":
    # Simple test
    logging.basicConfig(level=logging.INFO)
    
    # Create test data
    timestamps = pd.date_range('2025-12-18 16:00:00', periods=100, freq='5min', tz='UTC')
    df = pd.DataFrame({
        'open': 88000,
        'high': 88100,
        'low': 87900,
        'close': 88050,
        'volume': 1000
    }, index=timestamps)
    
    # Test
    helper = DataAlignmentHelper()
    candle, metadata = helper.get_aligned_candle(df, '5m')
    
    print("Test result:")
    print(helper.format_metadata_log(metadata))
