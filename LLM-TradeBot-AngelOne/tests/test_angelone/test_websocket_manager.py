"""
Tests for WebSocket Manager (Task 11)
Tests WebSocket connection, subscription, and message handling

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import time

from src.api.angelone.websocket_manager import (
    WebSocketManager, SubscriptionMode, ConnectionState, TickData
)


class TestWebSocketManager:
    """Test WebSocket manager functionality"""
    
    @pytest.fixture
    def ws_manager(self):
        """Create WebSocket manager for testing"""
        return WebSocketManager(
            auth_token='test_token',
            api_key='test_api_key',
            client_code='TEST123',
            feed_token='test_feed_token',
            auto_reconnect=False  # Disable for testing
        )
    
    @pytest.fixture
    def mock_ws_class(self):
        """Create mock WebSocket class"""
        mock_ws = MagicMock()
        mock_class = Mock(return_value=mock_ws)
        return mock_class, mock_ws
    
    # ==================== Initialization Tests ====================
    
    def test_initialization(self, ws_manager):
        """Test WebSocket manager initialization"""
        assert ws_manager.client_code == 'TEST123'
        assert ws_manager.state == ConnectionState.DISCONNECTED
        assert not ws_manager.is_connected
        assert ws_manager.get_subscription_count() == 0
    
    def test_initialization_with_callbacks(self):
        """Test initialization with callbacks"""
        on_tick = Mock()
        on_connect = Mock()
        on_disconnect = Mock()
        on_error = Mock()
        
        manager = WebSocketManager(
            auth_token='test',
            api_key='test',
            client_code='TEST',
            feed_token='test',
            on_tick=on_tick,
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            on_error=on_error
        )
        
        assert manager._on_tick == on_tick
        assert manager._on_connect == on_connect
        assert manager._on_disconnect == on_disconnect
        assert manager._on_error == on_error
    
    # ==================== Connection Tests ====================
    
    def test_connect_success(self, ws_manager, mock_ws_class):
        """Test successful connection"""
        mock_class, mock_ws = mock_ws_class
        
        result = ws_manager.connect(ws_class=mock_class)
        
        assert result is True
        assert ws_manager.state == ConnectionState.CONNECTING
        mock_class.assert_called_once()
    
    def test_connect_already_connected(self, ws_manager, mock_ws_class):
        """Test connecting when already connected"""
        mock_class, mock_ws = mock_ws_class
        
        # Simulate connected state
        ws_manager._state = ConnectionState.CONNECTED
        
        result = ws_manager.connect(ws_class=mock_class)
        
        assert result is True
        mock_class.assert_not_called()  # Should not create new connection
    
    def test_connect_failure(self, ws_manager):
        """Test connection failure"""
        on_error = Mock()
        ws_manager._on_error = on_error
        
        # Pass None to simulate missing WebSocket class
        result = ws_manager.connect(ws_class=None)
        
        assert result is False
        assert ws_manager.state == ConnectionState.ERROR
        on_error.assert_called_once()
    
    # ==================== Subscription Tests ====================
    
    def test_subscribe_when_disconnected(self, ws_manager):
        """Test subscribing when not connected"""
        result = ws_manager.subscribe(
            tokens=['2885', '3045'],
            exchange='NSE',
            mode=SubscriptionMode.LTP,
            symbols=['RELIANCE-EQ', 'SBIN-EQ']
        )
        
        assert result is True
        assert ws_manager.get_subscription_count() == 2
        
        subs = ws_manager.get_subscriptions()
        assert '2885' in subs
        assert '3045' in subs
        assert subs['2885']['exchange'] == 'NSE'
    
    def test_subscribe_with_symbol_mapping(self, ws_manager):
        """Test subscription with symbol name mapping"""
        ws_manager.subscribe(
            tokens=['2885'],
            exchange='NSE',
            symbols=['RELIANCE-EQ']
        )
        
        assert ws_manager._token_to_symbol['2885'] == 'RELIANCE-EQ'
    
    def test_unsubscribe(self, ws_manager):
        """Test unsubscribing from symbols"""
        # First subscribe
        ws_manager.subscribe(tokens=['2885', '3045'], exchange='NSE')
        assert ws_manager.get_subscription_count() == 2
        
        # Then unsubscribe
        result = ws_manager.unsubscribe(tokens=['2885'], exchange='NSE')
        
        assert result is True
        assert ws_manager.get_subscription_count() == 1
        assert '2885' not in ws_manager.get_subscriptions()
        assert '3045' in ws_manager.get_subscriptions()
    
    def test_subscription_modes(self, ws_manager):
        """Test different subscription modes"""
        ws_manager.subscribe(tokens=['1'], mode=SubscriptionMode.LTP)
        ws_manager.subscribe(tokens=['2'], mode=SubscriptionMode.QUOTE)
        ws_manager.subscribe(tokens=['3'], mode=SubscriptionMode.SNAP_QUOTE)
        
        subs = ws_manager.get_subscriptions()
        assert subs['1']['mode'] == 1  # LTP
        assert subs['2']['mode'] == 2  # QUOTE
        assert subs['3']['mode'] == 3  # SNAP_QUOTE
    
    # ==================== Message Handling Tests ====================
    
    def test_handle_open(self, ws_manager):
        """Test handling connection open"""
        on_connect = Mock()
        ws_manager._on_connect = on_connect
        
        ws_manager._handle_open(None)
        
        assert ws_manager.state == ConnectionState.CONNECTED
        assert ws_manager._reconnect_count == 0
        on_connect.assert_called_once()
    
    def test_handle_tick_data(self, ws_manager):
        """Test handling tick data"""
        received_ticks = []
        
        def on_tick(tick):
            received_ticks.append(tick)
        
        ws_manager._on_tick = on_tick
        ws_manager._token_to_symbol['2885'] = 'RELIANCE-EQ'
        ws_manager._subscriptions['2885'] = {'exchange': 'NSE', 'mode': 1}
        
        # Simulate tick data (AngelOne sends prices in paise)
        tick_data = {
            'token': '2885',
            'ltp': 250000,  # 2500.00 in paise
            'open': 248000,
            'high': 252000,
            'low': 247000,
            'close': 249000,
            'volume': 1000000
        }
        
        ws_manager._handle_data(None, tick_data)
        
        assert len(received_ticks) == 1
        tick = received_ticks[0]
        assert tick.symbol == 'RELIANCE-EQ'
        assert tick.ltp == 2500.0
        assert tick.exchange == 'NSE'
    
    def test_handle_tick_data_list(self, ws_manager):
        """Test handling list of tick data"""
        received_ticks = []
        ws_manager._on_tick = lambda t: received_ticks.append(t)
        ws_manager._subscriptions['2885'] = {'exchange': 'NSE', 'mode': 1}
        ws_manager._subscriptions['3045'] = {'exchange': 'NSE', 'mode': 1}
        
        tick_list = [
            {'token': '2885', 'ltp': 250000},
            {'token': '3045', 'ltp': 55000}
        ]
        
        ws_manager._handle_data(None, tick_list)
        
        assert len(received_ticks) == 2
    
    def test_handle_heartbeat(self, ws_manager):
        """Test handling heartbeat message"""
        initial_heartbeat = ws_manager._last_heartbeat
        
        ws_manager._handle_data(None, {'type': 'heartbeat'})
        
        assert ws_manager._last_heartbeat > initial_heartbeat
    
    def test_handle_error(self, ws_manager):
        """Test handling WebSocket error"""
        on_error = Mock()
        ws_manager._on_error = on_error
        
        error = Exception("Test error")
        ws_manager._handle_error(None, error)
        
        assert ws_manager.state == ConnectionState.ERROR
        on_error.assert_called_once_with(error)
    
    def test_handle_close(self, ws_manager):
        """Test handling WebSocket close"""
        on_disconnect = Mock()
        ws_manager._on_disconnect = on_disconnect
        ws_manager._state = ConnectionState.CONNECTED
        
        ws_manager._handle_close(None, 1000, "Normal close")
        
        assert ws_manager.state == ConnectionState.DISCONNECTED
        on_disconnect.assert_called_once()
    
    # ==================== Disconnect Tests ====================
    
    def test_disconnect(self, ws_manager, mock_ws_class):
        """Test disconnecting"""
        mock_class, mock_ws = mock_ws_class
        
        # Connect first
        ws_manager.connect(ws_class=mock_class)
        ws_manager._state = ConnectionState.CONNECTED
        ws_manager.subscribe(tokens=['2885'])
        
        # Disconnect
        ws_manager.disconnect()
        
        assert ws_manager.state == ConnectionState.DISCONNECTED
        assert ws_manager.get_subscription_count() == 0
        assert not ws_manager._running
    
    # ==================== Reconnection Tests ====================
    
    def test_reconnect_disabled(self, ws_manager):
        """Test that reconnection is disabled when auto_reconnect=False"""
        ws_manager.auto_reconnect = False
        ws_manager._running = True
        
        ws_manager._attempt_reconnect()
        
        # Should not change state
        assert ws_manager.state == ConnectionState.DISCONNECTED
    
    def test_max_reconnect_attempts(self):
        """Test max reconnect attempts limit"""
        manager = WebSocketManager(
            auth_token='test',
            api_key='test',
            client_code='TEST',
            feed_token='test',
            auto_reconnect=True,
            max_reconnect_attempts=3,
            reconnect_interval=0  # No delay for testing
        )
        
        manager._running = True
        manager._reconnect_count = 3  # Already at max
        
        manager._attempt_reconnect()
        
        assert manager.state == ConnectionState.ERROR
    
    # ==================== Exchange Code Tests ====================
    
    def test_exchange_codes(self, ws_manager):
        """Test exchange code mapping"""
        assert ws_manager.EXCHANGE_CODES['NSE'] == 1
        assert ws_manager.EXCHANGE_CODES['NFO'] == 2
        assert ws_manager.EXCHANGE_CODES['BSE'] == 3
        assert ws_manager.EXCHANGE_CODES['MCX'] == 5


class TestTickData:
    """Test TickData dataclass"""
    
    def test_tick_data_creation(self):
        """Test creating TickData"""
        tick = TickData(
            token='2885',
            symbol='RELIANCE-EQ',
            exchange='NSE',
            ltp=2500.0,
            open=2480.0,
            high=2520.0,
            low=2470.0,
            close=2490.0,
            volume=1000000,
            timestamp=1704067200000
        )
        
        assert tick.token == '2885'
        assert tick.symbol == 'RELIANCE-EQ'
        assert tick.ltp == 2500.0
        assert tick.volume == 1000000


class TestSubscriptionMode:
    """Test SubscriptionMode enum"""
    
    def test_subscription_mode_values(self):
        """Test subscription mode values"""
        assert SubscriptionMode.LTP.value == 1
        assert SubscriptionMode.QUOTE.value == 2
        assert SubscriptionMode.SNAP_QUOTE.value == 3


class TestConnectionState:
    """Test ConnectionState enum"""
    
    def test_connection_state_values(self):
        """Test connection state values"""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.ERROR.value == "error"
