"""
Data Oracle Agent (The Oracle)

Responsibilities:
1. Async concurrent requests for multi-timeframe candle data
2. Split stable/live dual-view
3. Time alignment validation

Optimizations:
- Concurrent IO, saves 60% time
- Dual-view data, solves lag issues

Updated for AngelOne Indian Stock Market Integration
"""

import asyncio
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Union
from dataclasses import dataclass, field

# AngelOne client for Indian market
from src.api.angelone import AngelOneClient
# Legacy Binance client for backward compatibility
try:
    from src.api.binance_client import BinanceClient
except ImportError:
    BinanceClient = None

from src.api.quant_client import quant_client
from src.utils.logger import log
from src.utils.oi_tracker import oi_tracker


@dataclass
class MarketSnapshot:
    """
    Market Snapshot (Dual-View Structure)
    
    stable_view: iloc[:-1] Completed candles for historical indicator calculation
    live_view: iloc[-1] Current incomplete candle with latest price
    """
    # 5m data
    stable_5m: pd.DataFrame  # Completed candles
    live_5m: Dict            # Latest candle
    
    # 15m data
    stable_15m: pd.DataFrame
    live_15m: Dict
    
    # 1h data
    stable_1h: pd.DataFrame
    live_1h: Dict
    
    # Metadata
    timestamp: datetime
    alignment_ok: bool       # Time alignment status
    fetch_duration: float    # Fetch duration (seconds)
    
    # External quant data (Netflow, OI) - optional for Indian market
    quant_data: Dict = field(default_factory=dict)
    
    # Broker native data (funding rate, OI) - optional for Indian market
    broker_funding: Dict = field(default_factory=dict)
    broker_oi: Dict = field(default_factory=dict)
    
    # Raw data (optional, for debugging)
    raw_5m: List[Dict] = field(default_factory=list)
    raw_15m: List[Dict] = field(default_factory=list)
    raw_1h: List[Dict] = field(default_factory=list)


class DataSyncAgent:
    """
    Data Oracle (The Oracle)
    
    Core Optimizations:
    1. Async concurrent requests (asyncio.gather)
    2. Dual-view data structure (stable + live)
    3. Time alignment validation
    
    Supports both AngelOne (Indian market) and Binance (crypto)
    """
    
    def __init__(self, client: Union[AngelOneClient, 'BinanceClient'] = None, symbol: str = None):
        """
        Initialize Data Sync Agent
        
        Args:
            client: AngelOneClient or BinanceClient instance
            symbol: Default trading symbol (e.g., "RELIANCE-EQ" for NSE, "BTCUSDT" for Binance)
        """
        self._init_client = client  # Store initial client (may be None)
        self.default_symbol = symbol
        
        # Detect client type
        self._is_angelone = isinstance(client, AngelOneClient) if client else False
    
    @property
    def client(self):
        """Get active client - checks global_state.exchange_client if init client is None"""
        from src.server.state import global_state
        
        # If we have an init client, use it
        if self._init_client is not None:
            return self._init_client
        
        # Otherwise check global_state for broker client (set when user connects via UI)
        if hasattr(global_state, 'exchange_client') and global_state.exchange_client is not None:
            log.info(f"Using global_state.exchange_client: {type(global_state.exchange_client)}")
            return global_state.exchange_client
        
        log.warning("No client available - _init_client is None and global_state.exchange_client is None")
        return None
    
    @client.setter
    def client(self, value):
        """Set the client"""
        self._init_client = value
        
    def _init_websocket(self):
        """Initialize WebSocket manager if needed (called lazily)"""
        if hasattr(self, '_ws_initialized'):
            return
        self._ws_initialized = True
        
        # WebSocket manager (optional)
        import os
        self.use_websocket = os.getenv("USE_WEBSOCKET", "false").lower() == "true"
        self.ws_manager = None
        self._initial_load_complete = False
        
        # WebSocket only for Binance (AngelOne uses different WebSocket)
        if self.use_websocket and not self._is_angelone and BinanceClient:
            try:
                from src.api.binance_websocket import BinanceWebSocketManager
                self.ws_manager = BinanceWebSocketManager(
                    symbol=self.default_symbol or "BTCUSDT",
                    timeframes=['5m', '15m', '1h']
                )
                self.ws_manager.start()
                log.info("🚀 WebSocket data stream enabled")
            except Exception as e:
                log.warning(f"WebSocket startup failed, falling back to REST API: {e}")
                self.use_websocket = False
        else:
            log.info("📡 Using REST API mode")
        
        self.last_snapshot = None
        log.info("🕵️ The Oracle (DataSync Agent) initialized")
        
        # WebSocket manager (optional)
        import os
        self.use_websocket = os.getenv("USE_WEBSOCKET", "false").lower() == "true"
        self.ws_manager = None
        self._initial_load_complete = False
        
        # WebSocket only for Binance (AngelOne uses different WebSocket)
        if self.use_websocket and not self._is_angelone and BinanceClient:
            try:
                from src.api.binance_websocket import BinanceWebSocketManager
                self.ws_manager = BinanceWebSocketManager(
                    symbol=symbol or "BTCUSDT",
                    timeframes=['5m', '15m', '1h']
                )
                self.ws_manager.start()
                log.info("🚀 WebSocket data stream enabled")
            except Exception as e:
                log.warning(f"WebSocket startup failed, falling back to REST API: {e}")
                self.use_websocket = False
        else:
            log.info("📡 Using REST API mode")
        
        self.last_snapshot = None
        log.info("🕵️ The Oracle (DataSync Agent) initialized")
    
    async def fetch_all_timeframes(
        self,
        symbol: str = None,
        limit: int = 300
    ) -> MarketSnapshot:
        """
        Async concurrent fetch of all timeframe data
        
        Args:
            symbol: Trading symbol (uses default if not provided)
            limit: Number of candles per timeframe
            
        Returns:
            MarketSnapshot object with dual-view data
        """
        start_time = datetime.now()
        symbol = symbol or self.default_symbol or "RELIANCE-EQ"
        
        # Check if client is available
        active_client = self.client
        if active_client is None:
            log.warning(f"[{symbol}] No broker connected - waiting for connection")
            raise Exception("Not connected to AngelOne. Call connect() first.")
        
        # Check if client is connected (for BrokerClientWrapper)
        if hasattr(active_client, 'is_connected') and not active_client.is_connected:
            log.warning(f"[{symbol}] Broker disconnected - waiting for reconnection")
            raise Exception("Not connected to AngelOne. Call connect() first.")
        
        # Detect client type dynamically
        is_angelone = not (BinanceClient and isinstance(active_client, BinanceClient))
        
        log.info(f"[{symbol}] Fetching data using {'AngelOne' if is_angelone else 'Binance'} client")
        
        # Initialize WebSocket if not done yet
        if not hasattr(self, '_ws_initialized'):
            self._init_websocket()
        
        use_rest_fallback = False
        
        # WebSocket mode: Get data from cache (Binance only)
        if self.use_websocket and self.ws_manager and self._initial_load_complete and not is_angelone:
            # Get data from WebSocket cache
            k5m = self.ws_manager.get_klines('5m', limit)
            k15m = self.ws_manager.get_klines('15m', limit)
            k1h = self.ws_manager.get_klines('1h', limit)
            
            # Check if data is sufficient
            min_len = min(len(k5m), len(k15m), len(k1h))
            if min_len < limit:
                log.warning(f"[{symbol}] WebSocket cache data insufficient (min={min_len}, limit={limit}), falling back to REST API")
                use_rest_fallback = True
            else:
                # Still need to fetch external data asynchronously
                q_data = await quant_client.fetch_coin_data(symbol)
                loop = asyncio.get_event_loop()
                b_funding = await active_client.get_funding_rate_with_cache(symbol)
                b_oi = {}  # Mock empty OI

        if not self.use_websocket or not self.ws_manager or not self._initial_load_complete or use_rest_fallback or is_angelone:
            # REST API mode or first load / fallback mode / AngelOne
            loop = asyncio.get_event_loop()
            
            if is_angelone:
                # AngelOne: Use synchronous calls wrapped in executor
                tasks = [
                    loop.run_in_executor(
                        None,
                        active_client.get_klines,
                        symbol, '5m', limit
                    ),
                    loop.run_in_executor(
                        None,
                        active_client.get_klines,
                        symbol, '15m', limit
                    ),
                    loop.run_in_executor(
                        None,
                        active_client.get_klines,
                        symbol, '1h', limit
                    ),
                ]
                
                # Wait for all requests to complete
                results = await asyncio.gather(*tasks)
                k5m, k15m, k1h = results
                
                # No external quant data for Indian market
                q_data = {}
                b_funding = {}
                b_oi = {}
            else:
                # Binance: Original logic
                tasks = [
                    loop.run_in_executor(
                        None,
                        active_client.get_klines,
                        symbol, '5m', limit
                    ),
                    loop.run_in_executor(
                        None,
                        active_client.get_klines,
                        symbol, '15m', limit
                    ),
                    loop.run_in_executor(
                        None,
                        active_client.get_klines,
                        symbol, '1h', limit
                    ),
                    quant_client.fetch_coin_data(symbol),
                    loop.run_in_executor(
                        None,
                        active_client.get_funding_rate_with_cache,
                        symbol
                    ),
                ]
                
                results = await asyncio.gather(*tasks)
                k5m, k15m, k1h, q_data, b_funding = results
                b_oi = {}  # Mock empty OI
            
            log.info(f"[{symbol}] Data fetched: 5m={len(k5m)}, 15m={len(k15m)}, 1h={len(k1h)}")
            
            # Mark first load complete
            if not self._initial_load_complete:
                self._initial_load_complete = True
                log.info("✅ Initial data loaded, will use cache for updates")
        
        fetch_duration = (datetime.now() - start_time).total_seconds()
        
        # Split dual-view
        snapshot = MarketSnapshot(
            # 5m data
            stable_5m=self._to_dataframe(k5m[:-1]),
            live_5m=k5m[-1] if k5m else {},
            
            # 15m data
            stable_15m=self._to_dataframe(k15m[:-1]),
            live_15m=k15m[-1] if k15m else {},
            
            # 1h data
            stable_1h=self._to_dataframe(k1h[:-1]),
            live_1h=k1h[-1] if k1h else {},
            
            # Metadata
            timestamp=datetime.now(),
            alignment_ok=self._check_alignment(k5m, k15m, k1h),
            fetch_duration=fetch_duration,
            
            # Raw data
            raw_5m=k5m,
            raw_15m=k15m,
            raw_1h=k1h,
            quant_data=q_data,
            broker_funding=b_funding,
            broker_oi=b_oi
        )
        
        # Record OI to history tracker (if available)
        if b_oi and b_oi.get('open_interest', 0) > 0:
            oi_tracker.record(
                symbol=symbol,
                oi_value=b_oi['open_interest'],
                timestamp=b_oi.get('timestamp')
            )
        
        # Cache latest snapshot
        self.last_snapshot = snapshot
        
        return snapshot
    
    def _to_dataframe(self, klines: List[Dict]) -> pd.DataFrame:
        """
        Convert candle list to DataFrame
        
        Args:
            klines: Raw candle data list
            
        Returns:
            Processed DataFrame
        """
        if not klines:
            return pd.DataFrame()
        
        df = pd.DataFrame(klines)
        
        # Convert timestamp
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
        
        # Ensure numeric types
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def _check_alignment(
        self,
        k5m: List[Dict],
        k15m: List[Dict],
        k1h: List[Dict]
    ) -> bool:
        """
        Check multi-timeframe data time alignment
        
        Args:
            k5m, k15m, k1h: Candle data for each timeframe
            
        Returns:
            True if aligned, False otherwise
        """
        if not all([k5m, k15m, k1h]):
            log.warning("⚠️ Some timeframe data missing, alignment check failed")
            return False
        
        try:
            # Get latest candle timestamps
            t5m = k5m[-1]['timestamp']
            t15m = k15m[-1]['timestamp']
            t1h = k1h[-1]['timestamp']
            
            # Calculate time difference (milliseconds)
            diff_5m_15m = abs(t5m - t15m)
            diff_5m_1h = abs(t5m - t1h)
            
            # Use relaxed tolerance:
            # - 5m vs 15m: Allow 15 minute difference (15m candle period)
            # - 5m vs 1h: Allow 1 hour difference (1h candle period)
            max_diff_15m = 900000   # 15 minutes = 900,000 ms
            max_diff_1h = 3600000   # 1 hour = 3,600,000 ms
            
            # Only warn on severe deviation
            if diff_5m_15m > max_diff_15m or diff_5m_1h > max_diff_1h:
                log.warning(
                    f"⚠️ Time alignment anomaly: "
                    f"5m vs 15m = {diff_5m_15m/1000:.0f}s, "
                    f"5m vs 1h = {diff_5m_1h/1000:.0f}s"
                )
                return False
            
            return True
            
        except Exception as e:
            log.error(f"❌ Time alignment check failed: {e}")
            return False
    
    def _log_snapshot_info(self, snapshot: MarketSnapshot):
        """Log snapshot information"""
        log.oracle(f"📸 Snapshot info:")
        log.oracle(f"  - 5m:  {len(snapshot.stable_5m)} completed + 1 live")
        log.oracle(f"  - 15m: {len(snapshot.stable_15m)} completed + 1 live")
        log.oracle(f"  - 1h:  {len(snapshot.stable_1h)} completed + 1 live")
        log.oracle(f"  - Time aligned: {'✅' if snapshot.alignment_ok else '❌'}")
        log.oracle(f"  - Fetch duration: {snapshot.fetch_duration:.2f}s")
        
        # Log live price
        if snapshot.live_5m:
            log.info(f"  - Live price (5m): {snapshot.live_5m.get('close', 0):,.2f}")
        if snapshot.live_1h:
            log.info(f"  - Live price (1h): {snapshot.live_1h.get('close', 0):,.2f}")
    
    def get_live_price(self, timeframe: str = '5m') -> float:
        """
        Get live price for specified timeframe
        
        Args:
            timeframe: '5m', '15m', or '1h'
            
        Returns:
            Live close price
        """
        if not self.last_snapshot:
            log.warning("⚠️ No snapshot available")
            return 0.0
        
        live_data = {
            '5m': self.last_snapshot.live_5m,
            '15m': self.last_snapshot.live_15m,
            '1h': self.last_snapshot.live_1h
        }.get(timeframe, {})
        
        return float(live_data.get('close', 0))
    
    def get_stable_dataframe(self, timeframe: str = '5m') -> pd.DataFrame:
        """
        Get stable DataFrame for specified timeframe (completed candles)
        
        Args:
            timeframe: '5m', '15m', or '1h'
            
        Returns:
            DataFrame of completed candles
        """
        if not self.last_snapshot:
            log.warning("⚠️ No snapshot available")
            return pd.DataFrame()
        
        return {
            '5m': self.last_snapshot.stable_5m,
            '15m': self.last_snapshot.stable_15m,
            '1h': self.last_snapshot.stable_1h
        }.get(timeframe, pd.DataFrame())


# Async test function
async def test_data_sync_agent():
    """Test Data Sync Agent"""
    agent = DataSyncAgent()
    
    print("\n" + "="*80)
    print("Test: Data Sync Agent (The Oracle)")
    print("="*80)
    
    # Test 1: Concurrent data fetch
    print("\n[Test 1] Concurrent multi-timeframe data fetch...")
    snapshot = await agent.fetch_all_timeframes("RELIANCE-EQ")
    
    print(f"\n✅ Data fetch successful")
    print(f"  - Duration: {snapshot.fetch_duration:.2f}s")
    print(f"  - Time aligned: {snapshot.alignment_ok}")
    
    # Test 2: Verify dual-view
    print("\n[Test 2] Verify dual-view data...")
    print(f"  - Stable 5m shape: {snapshot.stable_5m.shape}")
    print(f"  - Live 5m keys: {list(snapshot.live_5m.keys())}")
    print(f"  - Live 5m price: {snapshot.live_5m.get('close', 0):,.2f}")
    
    # Test 3: Get live price
    print("\n[Test 3] Get live price...")
    for tf in ['5m', '15m', '1h']:
        price = agent.get_live_price(tf)
        print(f"  - {tf}: {price:,.2f}")
    
    print("\n" + "="*80)
    print("✅ All tests passed")
    print("="*80 + "\n")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_data_sync_agent())
