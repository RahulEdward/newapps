"""
OI (Open Interest) History Tracker

Stores historical OI data and calculates 24h change rate
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from collections import defaultdict
from src.utils.logger import log


class OITracker:
    """
    OI History Tracker
    
    Features:
    1. Memory cache + file persistence
    2. Auto-cleanup of data older than 48 hours
    3. Calculate 24h / 1h change rate
    """
    
    def __init__(self, data_dir: str = "data/oi_history"):
        self.data_dir = data_dir
        self.history: Dict[str, List[Dict]] = defaultdict(list)  # {symbol: [{ts, oi}, ...]}
        self.max_history_hours = 48  # Keep last 48 hours of data
        
        # Ensure directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Load historical data
        self._load_history()
        
        log.info(f"OI Tracker initialized | Data dir: {data_dir}")
    
    def _get_file_path(self, symbol: str) -> str:
        """Get history file path for a symbol"""
        return os.path.join(self.data_dir, f"{symbol}_oi.json")
    
    def _load_history(self):
        """Load historical data from files"""
        try:
            for filename in os.listdir(self.data_dir):
                if filename.endswith("_oi.json"):
                    symbol = filename.replace("_oi.json", "")
                    filepath = os.path.join(self.data_dir, filename)
                    
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        self.history[symbol] = data
                        
            total_records = sum(len(v) for v in self.history.values())
            if total_records > 0:
                log.info(f"OI history loaded: {len(self.history)} symbols, {total_records} records")
        except Exception as e:
            log.warning(f"Failed to load OI history: {e}")
    
    def _save_history(self, symbol: str):
        """Save history data for a single symbol"""
        try:
            filepath = self._get_file_path(symbol)
            with open(filepath, 'w') as f:
                json.dump(self.history[symbol], f)
        except Exception as e:
            log.error(f"Failed to save OI history ({symbol}): {e}")
    
    def _cleanup_old_data(self, symbol: str):
        """Clean up data older than 48 hours"""
        cutoff = datetime.now() - timedelta(hours=self.max_history_hours)
        cutoff_ts = cutoff.timestamp() * 1000
        
        original_count = len(self.history[symbol])
        self.history[symbol] = [
            record for record in self.history[symbol]
            if record.get('ts', 0) > cutoff_ts
        ]
        
        removed = original_count - len(self.history[symbol])
        if removed > 0:
            log.debug(f"Cleaned up {symbol} old OI data: {removed} records")
    
    def record(self, symbol: str, oi_value: float, timestamp: Optional[int] = None):
        """
        Record an OI data point
        
        Args:
            symbol: Trading pair
            oi_value: OI value
            timestamp: Timestamp (milliseconds), defaults to current time
        """
        if timestamp is None:
            timestamp = int(datetime.now().timestamp() * 1000)
        
        # Avoid duplicate records within short time (at least 5 minute interval)
        if self.history[symbol]:
            last_ts = self.history[symbol][-1].get('ts', 0)
            if timestamp - last_ts < 300000:  # 5 minutes
                return
        
        self.history[symbol].append({
            'ts': timestamp,
            'oi': oi_value
        })
        
        # Periodic cleanup and save
        self._cleanup_old_data(symbol)
        self._save_history(symbol)
    
    def get_change_pct(self, symbol: str, hours: int = 24) -> float:
        """
        Calculate OI change percentage for specified time period
        
        Args:
            symbol: Trading pair
            hours: Lookback time (hours)
            
        Returns:
            Change percentage (e.g., 5.2 means up 5.2%)
        """
        if symbol not in self.history or len(self.history[symbol]) < 2:
            return 0.0
        
        now_ts = datetime.now().timestamp() * 1000
        target_ts = now_ts - (hours * 3600 * 1000)
        
        # Get current OI
        current_oi = self.history[symbol][-1]['oi']
        
        # Find the record closest to target_ts
        past_oi = None
        for record in self.history[symbol]:
            if record['ts'] <= target_ts:
                past_oi = record['oi']
            else:
                break
        
        # If not enough historical data, use the earliest record
        if past_oi is None and self.history[symbol]:
            past_oi = self.history[symbol][0]['oi']
        
        if past_oi is None or past_oi == 0:
            return 0.0
        
        change_pct = ((current_oi - past_oi) / past_oi) * 100
        return round(change_pct, 2)
    
    def get_current_oi(self, symbol: str) -> float:
        """Get current OI value"""
        if symbol in self.history and self.history[symbol]:
            return self.history[symbol][-1]['oi']
        return 0.0
    
    def get_stats(self, symbol: str) -> Dict:
        """Get OI statistics"""
        if symbol not in self.history or not self.history[symbol]:
            return {
                'current': 0,
                'change_1h': 0.0,
                'change_24h': 0.0,
                'records': 0
            }
        
        return {
            'current': self.get_current_oi(symbol),
            'change_1h': self.get_change_pct(symbol, hours=1),
            'change_24h': self.get_change_pct(symbol, hours=24),
            'records': len(self.history[symbol])
        }


# Global singleton
oi_tracker = OITracker()
