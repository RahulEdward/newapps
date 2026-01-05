"""
WebSocket Manager for AngelOne
Handles real-time market data streaming via WebSocket

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
"""

import json
import threading
import time
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from loguru import logger

try:
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
    HAS_SMARTAPI = True
except ImportError:
    HAS_SMARTAPI = False
    SmartWebSocketV2 = None


class SubscriptionMode(Enum):
    """WebSocket subscription modes"""
    LTP = 1      # Last Traded Price only
    QUOTE = 2    # Quote data (bid/ask)
    SNAP_QUOTE = 3  # Full market depth


class ConnectionState(Enum):
    """WebSocket connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class TickData:
    """Real-time tick data"""
    token: str
    symbol: str
    exchange: str
    ltp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: int


class WebSocketManager:
    """
    Manages WebSocket connection for real-time market data
    
    Features:
    - Connect to AngelOne WebSocket
    - Subscribe to symbols for live data
    - Handle price updates and notify callbacks
    - Auto-reconnect on disconnect
    - Graceful disconnect at market close
    """
    
    # Exchange codes for WebSocket
    EXCHANGE_CODES = {
        'NSE': 1,
        'NFO': 2,
        'BSE': 3,
        'MCX': 5,
        'CDS': 13,
        'BFO': 6
    }
    
    def __init__(
        self,
        auth_token: str,
        api_key: str,
        client_code: str,
        feed_token: str,
        on_tick: Callable[[TickData], None] = None,
        on_connect: Callable[[], None] = None,
        on_disconnect: Callable[[], None] = None,
        on_error: Callable[[Exception], None] = None,
        auto_reconnect: bool = True,
        reconnect_interval: int = 5,
        max_reconnect_attempts: int = 10
    ):
        """
        Initialize WebSocket Manager
        
        Args:
            auth_token: JWT token from authentication
            api_key: AngelOne API key
            client_code: Trading account client code
            feed_token: Feed token from authentication
            on_tick: Callback for tick data
            on_connect: Callback on connection
            on_disconnect: Callback on disconnection
            on_error: Callback on error
            auto_reconnect: Enable auto-reconnect
            reconnect_interval: Seconds between reconnect attempts
            max_reconnect_attempts: Maximum reconnect attempts
        """
        self.auth_token = auth_token
        self.api_key = api_key
        self.client_code = client_code
        self.feed_token = feed_token
        
        # Callbacks
        self._on_tick = on_tick
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_error = on_error
        
        # Reconnection settings
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        
        # State
        self._state = ConnectionState.DISCONNECTED
        self._ws = None
        self._subscriptions: Dict[str, Dict] = {}  # token -> {symbol, exchange, mode}
        self._reconnect_count = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_heartbeat = 0
        
        # Symbol mapping (token -> symbol name)
        self._token_to_symbol: Dict[str, str] = {}
        
        logger.info(f"WebSocketManager initialized for {client_code}")
    
    @property
    def state(self) -> ConnectionState:
        """Get current connection state"""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        return self._state == ConnectionState.CONNECTED
    
    def connect(self, ws_class=None) -> bool:
        """
        Connect to WebSocket
        
        Args:
            ws_class: Optional WebSocket class for testing
        
        Returns:
            True if connection initiated
        """
        if self._state == ConnectionState.CONNECTED:
            logger.warning("Already connected")
            return True
        
        self._state = ConnectionState.CONNECTING
        logger.info("Connecting to AngelOne WebSocket...")
        
        try:
            # Use provided class or SmartWebSocketV2
            ws_class = ws_class or SmartWebSocketV2
            
            if ws_class is None:
                raise ImportError("SmartApi WebSocket not available")
            
            self._ws = ws_class(
                self.auth_token,
                self.api_key,
                self.client_code,
                self.feed_token
            )
            
            # Set callbacks
            self._ws.on_open = self._handle_open
            self._ws.on_data = self._handle_data
            self._ws.on_error = self._handle_error
            self._ws.on_close = self._handle_close
            
            # Start connection in background thread
            self._running = True
            self._thread = threading.Thread(target=self._run_websocket, daemon=True)
            self._thread.start()
            
            return True
            
        except Exception as e:
            self._state = ConnectionState.ERROR
            logger.error(f"WebSocket connection failed: {str(e)}")
            if self._on_error:
                self._on_error(e)
            return False
    
    def _run_websocket(self):
        """Run WebSocket in background thread"""
        try:
            self._ws.connect()
        except Exception as e:
            logger.error(f"WebSocket run error: {str(e)}")
            self._handle_error(None, e)
    
    def _handle_open(self, ws):
        """Handle WebSocket connection open"""
        self._state = ConnectionState.CONNECTED
        self._reconnect_count = 0
        self._last_heartbeat = time.time()
        
        logger.info("WebSocket connected")
        
        # Resubscribe to all symbols
        if self._subscriptions:
            self._resubscribe_all()
        
        if self._on_connect:
            self._on_connect()
    
    def _handle_data(self, ws, message):
        """Handle incoming WebSocket data"""
        try:
            self._last_heartbeat = time.time()
            
            # Parse message
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message
            
            # Handle different message types
            if isinstance(data, dict):
                if 'token' in data:
                    self._process_tick(data)
                elif 'type' in data and data['type'] == 'heartbeat':
                    logger.debug("Heartbeat received")
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'token' in item:
                        self._process_tick(item)
                        
        except Exception as e:
            logger.error(f"Error processing WebSocket data: {str(e)}")
    
    def _process_tick(self, data: Dict):
        """Process tick data and notify callback"""
        try:
            token = str(data.get('token', ''))
            symbol = self._token_to_symbol.get(token, token)
            
            # Get exchange from subscription
            sub_info = self._subscriptions.get(token, {})
            exchange = sub_info.get('exchange', 'NSE')
            
            tick = TickData(
                token=token,
                symbol=symbol,
                exchange=exchange,
                ltp=float(data.get('ltp', 0) or 0) / 100,  # AngelOne sends in paise
                open=float(data.get('open', 0) or 0) / 100,
                high=float(data.get('high', 0) or 0) / 100,
                low=float(data.get('low', 0) or 0) / 100,
                close=float(data.get('close', 0) or 0) / 100,
                volume=int(data.get('volume', 0) or 0),
                timestamp=int(time.time() * 1000)
            )
            
            if self._on_tick:
                self._on_tick(tick)
                
        except Exception as e:
            logger.error(f"Error processing tick: {str(e)}")
    
    def _handle_error(self, ws, error):
        """Handle WebSocket error"""
        self._state = ConnectionState.ERROR
        logger.error(f"WebSocket error: {str(error)}")
        
        if self._on_error:
            self._on_error(error)
        
        # Attempt reconnection
        if self.auto_reconnect:
            self._attempt_reconnect()
    
    def _handle_close(self, ws, close_status_code=None, close_msg=None):
        """Handle WebSocket close"""
        prev_state = self._state
        self._state = ConnectionState.DISCONNECTED
        
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        
        if self._on_disconnect:
            self._on_disconnect()
        
        # Attempt reconnection if not intentionally closed
        if self.auto_reconnect and self._running and prev_state == ConnectionState.CONNECTED:
            self._attempt_reconnect()
    
    def _attempt_reconnect(self):
        """Attempt to reconnect"""
        if not self.auto_reconnect or not self._running:
            return
        
        if self._reconnect_count >= self.max_reconnect_attempts:
            logger.error(f"Max reconnect attempts ({self.max_reconnect_attempts}) reached")
            self._state = ConnectionState.ERROR
            return
        
        self._reconnect_count += 1
        self._state = ConnectionState.RECONNECTING
        
        logger.info(f"Reconnecting in {self.reconnect_interval}s (attempt {self._reconnect_count}/{self.max_reconnect_attempts})")
        
        time.sleep(self.reconnect_interval)
        
        if self._running:
            self.connect()
    
    def _resubscribe_all(self):
        """Resubscribe to all symbols after reconnection"""
        if not self._subscriptions:
            return
        
        logger.info(f"Resubscribing to {len(self._subscriptions)} symbols")
        
        # Group by exchange and mode
        by_exchange_mode: Dict[tuple, List[str]] = {}
        for token, info in self._subscriptions.items():
            key = (info['exchange'], info['mode'])
            if key not in by_exchange_mode:
                by_exchange_mode[key] = []
            by_exchange_mode[key].append(token)
        
        # Subscribe each group
        for (exchange, mode), tokens in by_exchange_mode.items():
            self._send_subscribe(tokens, exchange, mode)
    
    def subscribe(
        self,
        tokens: List[str],
        exchange: str = 'NSE',
        mode: SubscriptionMode = SubscriptionMode.LTP,
        symbols: List[str] = None
    ) -> bool:
        """
        Subscribe to symbols for live data
        
        Args:
            tokens: List of symbol tokens
            exchange: Exchange code
            mode: Subscription mode (LTP, QUOTE, SNAP_QUOTE)
            symbols: Optional symbol names for mapping
        
        Returns:
            True if subscription sent
        """
        if not self.is_connected:
            logger.warning("Not connected, storing subscription for later")
        
        # Store subscriptions
        for i, token in enumerate(tokens):
            self._subscriptions[token] = {
                'exchange': exchange,
                'mode': mode.value if isinstance(mode, SubscriptionMode) else mode
            }
            if symbols and i < len(symbols):
                self._token_to_symbol[token] = symbols[i]
        
        if self.is_connected:
            return self._send_subscribe(tokens, exchange, mode)
        
        return True
    
    def _send_subscribe(
        self,
        tokens: List[str],
        exchange: str,
        mode: SubscriptionMode
    ) -> bool:
        """Send subscription request"""
        try:
            exchange_code = self.EXCHANGE_CODES.get(exchange.upper(), 1)
            mode_value = mode.value if isinstance(mode, SubscriptionMode) else mode
            
            # Format: [[exchange_code, token1], [exchange_code, token2], ...]
            token_list = [[exchange_code, token] for token in tokens]
            
            self._ws.subscribe(self.client_code, mode_value, token_list)
            
            logger.info(f"Subscribed to {len(tokens)} symbols on {exchange}")
            return True
            
        except Exception as e:
            logger.error(f"Subscribe error: {str(e)}")
            return False
    
    def unsubscribe(self, tokens: List[str], exchange: str = 'NSE') -> bool:
        """
        Unsubscribe from symbols
        
        Args:
            tokens: List of symbol tokens
            exchange: Exchange code
        
        Returns:
            True if unsubscription sent
        """
        try:
            # Remove from subscriptions
            for token in tokens:
                self._subscriptions.pop(token, None)
                self._token_to_symbol.pop(token, None)
            
            if self.is_connected:
                exchange_code = self.EXCHANGE_CODES.get(exchange.upper(), 1)
                token_list = [[exchange_code, token] for token in tokens]
                
                # Get mode from first subscription (default to LTP)
                mode = SubscriptionMode.LTP.value
                
                self._ws.unsubscribe(self.client_code, mode, token_list)
                
                logger.info(f"Unsubscribed from {len(tokens)} symbols")
            
            return True
            
        except Exception as e:
            logger.error(f"Unsubscribe error: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from WebSocket"""
        logger.info("Disconnecting WebSocket...")
        
        self._running = False
        self._state = ConnectionState.DISCONNECTED
        
        try:
            if self._ws:
                self._ws.close_connection()
        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}")
        
        self._ws = None
        self._subscriptions.clear()
        self._token_to_symbol.clear()
        
        logger.info("WebSocket disconnected")
    
    def get_subscriptions(self) -> Dict[str, Dict]:
        """Get current subscriptions"""
        return self._subscriptions.copy()
    
    def get_subscription_count(self) -> int:
        """Get number of active subscriptions"""
        return len(self._subscriptions)
