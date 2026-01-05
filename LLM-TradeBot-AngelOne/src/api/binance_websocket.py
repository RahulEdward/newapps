"""
Binance WebSocket Manager
Manages WebSocket connections and maintains real-time K-line cache
"""
import threading
import time
from collections import deque
from typing import Dict, List, Callable, Optional
from binance import ThreadedWebsocketManager
from src.utils.logger import log


class BinanceWebSocketManager:
    """
    Binance WebSocket Manager
    
    Features:
    1. Subscribe to multiple timeframe K-line streams (5m, 15m, 1h)
    2. Maintain thread-safe K-line cache
    3. Auto-reconnect
    """
    
    def __init__(self, symbol: str, timeframes: List[str], cache_size: int = 500):
        """
        Initialize WebSocket Manager
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframes: List of timeframes (e.g., ['5m', '15m', '1h'])
            cache_size: Number of K-lines to cache per timeframe
        """
        self.symbol = symbol.upper()
        self.timeframes = timeframes
        self.cache_size = cache_size
        
        # K-line cache: {timeframe: deque([kline_dict, ...])}
        self.kline_cache: Dict[str, deque] = {
            tf: deque(maxlen=cache_size) for tf in timeframes
        }
        
        # Thread lock for safe cache access
        self._cache_lock = threading.Lock()
        
        # WebSocket manager
        self.ws_manager: Optional[ThreadedWebsocketManager] = None
        self._is_running = False
        
        log.info(f"WebSocket Manager initialized: {symbol} | Timeframes: {timeframes}")
    
    def start(self):
        """Start WebSocket connection"""
        if self._is_running:
            log.warning("WebSocket is already running")
            return
        
        try:
            self.ws_manager = ThreadedWebsocketManager()
            self.ws_manager.start()
            
            # Subscribe to K-line streams for each timeframe
            for timeframe in self.timeframes:
                stream_name = f"{self.symbol.lower()}@kline_{timeframe}"
                
                self.ws_manager.start_kline_socket(
                    callback=self._handle_kline_message,
                    symbol=self.symbol,
                    interval=timeframe
                )
                
                log.info(f"✅ Subscribed to WebSocket stream: {stream_name}")
            
            self._is_running = True
            log.info(f"🚀 WebSocket Manager started successfully: {self.symbol}")
            
        except Exception as e:
            log.error(f"❌ WebSocket startup failed: {e}")
            self.stop()
    
    def _handle_kline_message(self, msg: dict):
        """
        Handle WebSocket K-line message
        
        Message format:
        {
            'e': 'kline',
            'E': 1640000000000,
            's': 'BTCUSDT',
            'k': {
                't': 1640000000000,  # Open time
                'T': 1640000300000,  # Close time
                's': 'BTCUSDT',
                'i': '5m',           # Timeframe
                'o': '50000.00',     # Open price
                'c': '50100.00',     # Close price
                'h': '50200.00',     # High price
                'l': '49900.00',     # Low price
                'v': '100.5',        # Volume
                'x': False           # Is closed
            }
        }
        """
        try:
            if msg.get('e') != 'kline':
                return
            
            kline = msg['k']
            timeframe = kline['i']
            is_closed = kline['x']  # Is K-line closed
            
            # Convert to standard format (consistent with REST API)
            kline_data = {
                'timestamp': kline['t'],     # Open time (millisecond timestamp)
                'open_time': kline['t'],     # Maintain compatibility with old code
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v']),
                'close_time': kline['T'],
                'is_closed': is_closed
            }
            
            # Update cache (thread-safe)
            with self._cache_lock:
                cache = self.kline_cache[timeframe]
                
                if cache and cache[-1]['timestamp'] == kline_data['timestamp']:
                    # If timestamp is the same, update directly (overwrite old data or update incomplete data)
                    cache[-1] = kline_data
                    if is_closed:
                        log.debug(f"📊 K-line closed: {self.symbol} {timeframe} | Close: {kline_data['close']}")
                else:
                    # If new timestamp, append to cache
                    cache.append(kline_data)
                    if is_closed:
                        log.debug(f"📊 New K-line opened and closed: {self.symbol} {timeframe}")
                        
        except Exception as e:
            log.error(f"Failed to process WebSocket message: {e}")
    
    def get_klines(self, timeframe: str, limit: int = 300) -> List[Dict]:
        """
        Get cached K-line data
        
        Args:
            timeframe: Timeframe ('5m', '15m', '1h')
            limit: Number of K-lines to return
            
        Returns:
            List of K-line data (sorted by time ascending)
        """
        with self._cache_lock:
            cache = self.kline_cache.get(timeframe, deque())
            # Return the most recent N K-lines
            return list(cache)[-limit:] if cache else []
    
    def get_cache_size(self, timeframe: str) -> int:
        """Get cache size for specified timeframe"""
        with self._cache_lock:
            return len(self.kline_cache.get(timeframe, deque()))
    
    def is_ready(self, timeframe: str, min_klines: int = 100) -> bool:
        """
        Check if cache is ready
        
        Args:
            timeframe: Timeframe
            min_klines: Minimum number of K-lines
            
        Returns:
            True if cache has enough data
        """
        return self.get_cache_size(timeframe) >= min_klines
    
    def stop(self):
        """Stop WebSocket connection"""
        if not self._is_running:
            return
        
        try:
            if self.ws_manager:
                self.ws_manager.stop()
                log.info("🛑 WebSocket Manager stopped")
            
            self._is_running = False
            
        except Exception as e:
            log.error(f"Failed to stop WebSocket: {e}")
    
    def __del__(self):
        """Destructor to ensure resource cleanup"""
        self.stop()


# Test code
if __name__ == "__main__":
    import time
    
    # Create WebSocket manager
    ws_manager = BinanceWebSocketManager(
        symbol="BTCUSDT",
        timeframes=['5m', '15m', '1h']
    )
    
    # Start
    ws_manager.start()
    
    # Wait for data accumulation
    print("Waiting for WebSocket data...")
    time.sleep(10)
    
    # Check cache
    for tf in ['5m', '15m', '1h']:
        klines = ws_manager.get_klines(tf, limit=5)
        print(f"\n{tf} K-line cache: {len(klines)} candles")
        if klines:
            latest = klines[-1]
            print(f"Latest price: {latest['close']}")
    
    # Stop
    ws_manager.stop()
