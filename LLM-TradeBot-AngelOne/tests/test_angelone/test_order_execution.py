"""
Tests for Order Execution (Task 8)
Tests order placement, modification, cancellation, and response handling

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
Property Tests: 10, 11
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.api.angelone.angelone_client import AngelOneClient


class TestOrderExecution:
    """Test order execution functionality"""
    
    @pytest.fixture
    def mock_smart_api(self):
        """Create mock SmartConnect"""
        mock = MagicMock()
        mock.generateSession.return_value = {
            'status': True,
            'data': {
                'jwtToken': 'test_jwt',
                'refreshToken': 'test_refresh',
                'feedToken': 'test_feed'
            }
        }
        mock.getProfile.return_value = {
            'status': True,
            'data': {'clientcode': 'TEST123'}
        }
        return mock
    
    @pytest.fixture
    def connected_client(self, mock_smart_api):
        """Create connected client for testing"""
        client = AngelOneClient(
            api_key='test_api_key',
            client_code='TEST123',
            password='test_password',
            totp_secret='JBSWY3DPEHPK3PXP'
        )
        
        # Mock SmartConnect class
        mock_class = Mock(return_value=mock_smart_api)
        client.connect_sync(smart_api_class=mock_class)
        
        # Add mock symbol to mapper using correct SymbolInfo fields
        from src.api.angelone.symbol_mapper import SymbolInfo
        client.symbol_mapper._instruments = {
            'NSE': {
                'RELIANCE-EQ': SymbolInfo(
                    symbol='RELIANCE-EQ',
                    token='2885',
                    exchange='NSE',
                    name='RELIANCE-EQ',
                    lot_size=1,
                    tick_size=0.05,
                    instrument_type='EQ'
                ),
                'NIFTY': SymbolInfo(
                    symbol='NIFTY',
                    token='26000',
                    exchange='NSE',
                    name='NIFTY',
                    lot_size=50,
                    tick_size=0.05,
                    instrument_type='INDEX'
                )
            },
            'BSE': {},
            'NFO': {},
            'MCX': {},
            'CDS': {},
            'BFO': {}
        }
        client.symbol_mapper._loaded = True
        
        return client, mock_smart_api
    
    # ==================== Order Placement Tests ====================
    
    def test_create_market_order_buy(self, connected_client):
        """Test placing a market buy order"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': True,
            'data': {'orderid': '123456789'}
        }
        
        result = client.create_order(
            symbol='RELIANCE-EQ',
            side='BUY',
            order_type='MARKET',
            quantity=10,
            exchange='NSE'
        )
        
        assert result['orderId'] == '123456789'
        assert result['status'] == 'PLACED'
        assert result['side'] == 'BUY'
        assert result['type'] == 'MARKET'
        assert result['quantity'] == 10
        mock_api.placeOrder.assert_called_once()
    
    def test_create_market_order_sell(self, connected_client):
        """Test placing a market sell order"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': True,
            'data': {'orderid': '987654321'}
        }
        
        result = client.create_order(
            symbol='RELIANCE-EQ',
            side='SELL',
            order_type='MARKET',
            quantity=5,
            exchange='NSE'
        )
        
        assert result['orderId'] == '987654321'
        assert result['status'] == 'PLACED'
        assert result['side'] == 'SELL'
    
    def test_create_limit_order(self, connected_client):
        """Test placing a limit order"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': True,
            'data': {'orderid': '111222333'}
        }
        
        result = client.create_order(
            symbol='RELIANCE-EQ',
            side='BUY',
            order_type='LIMIT',
            quantity=10,
            price=2500.0,
            exchange='NSE'
        )
        
        assert result['orderId'] == '111222333'
        assert result['status'] == 'PLACED'
        assert result['type'] == 'LIMIT'
        assert result['price'] == 2500.0
    
    def test_create_stoploss_limit_order(self, connected_client):
        """Test placing a stoploss limit order"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': True,
            'data': {'orderid': '444555666'}
        }
        
        result = client.create_order(
            symbol='RELIANCE-EQ',
            side='SELL',
            order_type='STOPLOSS_LIMIT',
            quantity=10,
            price=2400.0,
            trigger_price=2450.0,
            exchange='NSE'
        )
        
        assert result['orderId'] == '444555666'
        assert result['status'] == 'PLACED'
        assert result['type'] == 'STOPLOSS_LIMIT'
    
    def test_create_stoploss_market_order(self, connected_client):
        """Test placing a stoploss market order"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': True,
            'data': {'orderid': '777888999'}
        }
        
        result = client.create_order(
            symbol='RELIANCE-EQ',
            side='SELL',
            order_type='STOPLOSS_MARKET',
            quantity=10,
            trigger_price=2450.0,
            exchange='NSE'
        )
        
        assert result['orderId'] == '777888999'
        assert result['status'] == 'PLACED'
        assert result['type'] == 'STOPLOSS_MARKET'
    
    # ==================== Product Type Tests ====================
    
    def test_intraday_order(self, connected_client):
        """Test intraday product type"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': True,
            'data': {'orderid': '123'}
        }
        
        result = client.create_order(
            symbol='RELIANCE-EQ',
            side='BUY',
            order_type='MARKET',
            quantity=10,
            product_type='INTRADAY'
        )
        
        assert result['status'] == 'PLACED'
        # Verify product type was passed
        call_args = mock_api.placeOrder.call_args[0][0]
        assert call_args['producttype'] == 'INTRADAY'
    
    def test_delivery_order(self, connected_client):
        """Test delivery product type"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': True,
            'data': {'orderid': '456'}
        }
        
        result = client.create_order(
            symbol='RELIANCE-EQ',
            side='BUY',
            order_type='MARKET',
            quantity=10,
            product_type='DELIVERY'
        )
        
        assert result['status'] == 'PLACED'
        call_args = mock_api.placeOrder.call_args[0][0]
        assert call_args['producttype'] == 'DELIVERY'
    
    def test_carryforward_order(self, connected_client):
        """Test carryforward product type"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': True,
            'data': {'orderid': '789'}
        }
        
        result = client.create_order(
            symbol='RELIANCE-EQ',
            side='BUY',
            order_type='MARKET',
            quantity=10,
            product_type='CARRYFORWARD'
        )
        
        assert result['status'] == 'PLACED'
        call_args = mock_api.placeOrder.call_args[0][0]
        assert call_args['producttype'] == 'CARRYFORWARD'
    
    # ==================== Validation Tests ====================
    
    def test_invalid_side_raises_error(self, connected_client):
        """Test that invalid side raises ValueError"""
        client, mock_api = connected_client
        
        with pytest.raises(ValueError, match="Invalid side"):
            client.create_order(
                symbol='RELIANCE-EQ',
                side='INVALID',
                order_type='MARKET',
                quantity=10
            )
    
    def test_invalid_order_type_raises_error(self, connected_client):
        """Test that invalid order type raises ValueError"""
        client, mock_api = connected_client
        
        with pytest.raises(ValueError, match="Invalid order_type"):
            client.create_order(
                symbol='RELIANCE-EQ',
                side='BUY',
                order_type='INVALID',
                quantity=10
            )
    
    def test_invalid_product_type_raises_error(self, connected_client):
        """Test that invalid product type raises ValueError"""
        client, mock_api = connected_client
        
        with pytest.raises(ValueError, match="Invalid product_type"):
            client.create_order(
                symbol='RELIANCE-EQ',
                side='BUY',
                order_type='MARKET',
                quantity=10,
                product_type='INVALID'
            )
    
    def test_limit_order_requires_price(self, connected_client):
        """Test that limit order requires price"""
        client, mock_api = connected_client
        
        with pytest.raises(ValueError, match="Price required"):
            client.create_order(
                symbol='RELIANCE-EQ',
                side='BUY',
                order_type='LIMIT',
                quantity=10,
                price=0  # Invalid price
            )
    
    def test_stoploss_order_requires_trigger_price(self, connected_client):
        """Test that stoploss order requires trigger price"""
        client, mock_api = connected_client
        
        with pytest.raises(ValueError, match="Trigger price required"):
            client.create_order(
                symbol='RELIANCE-EQ',
                side='BUY',
                order_type='STOPLOSS_LIMIT',
                quantity=10,
                price=2500.0,
                trigger_price=0  # Invalid trigger price
            )
    
    # ==================== Order Rejection Tests ====================
    
    def test_order_rejection_handling(self, connected_client):
        """Test handling of order rejection"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': False,
            'message': 'Insufficient margin'
        }
        
        result = client.create_order(
            symbol='RELIANCE-EQ',
            side='BUY',
            order_type='MARKET',
            quantity=10
        )
        
        assert result['status'] == 'REJECTED'
        assert result['error'] == 'Insufficient margin'
        assert result['orderId'] == ''
    
    # ==================== Order Modification Tests ====================
    
    def test_modify_order_quantity(self, connected_client):
        """Test modifying order quantity"""
        client, mock_api = connected_client
        
        mock_api.modifyOrder.return_value = {
            'status': True,
            'message': 'Order modified successfully'
        }
        
        result = client.modify_order(
            order_id='123456789',
            quantity=20
        )
        
        assert result['orderId'] == '123456789'
        assert result['status'] == 'MODIFIED'
        mock_api.modifyOrder.assert_called_once()
    
    def test_modify_order_price(self, connected_client):
        """Test modifying order price"""
        client, mock_api = connected_client
        
        mock_api.modifyOrder.return_value = {
            'status': True,
            'message': 'Order modified successfully'
        }
        
        result = client.modify_order(
            order_id='123456789',
            price=2600.0
        )
        
        assert result['status'] == 'MODIFIED'
        call_args = mock_api.modifyOrder.call_args[0][0]
        assert call_args['price'] == '2600.0'
    
    def test_modify_order_trigger_price(self, connected_client):
        """Test modifying order trigger price"""
        client, mock_api = connected_client
        
        mock_api.modifyOrder.return_value = {
            'status': True,
            'message': 'Order modified successfully'
        }
        
        result = client.modify_order(
            order_id='123456789',
            trigger_price=2550.0
        )
        
        assert result['status'] == 'MODIFIED'
        call_args = mock_api.modifyOrder.call_args[0][0]
        assert call_args['triggerprice'] == '2550.0'
    
    def test_modify_order_requires_order_id(self, connected_client):
        """Test that modify requires order_id"""
        client, mock_api = connected_client
        
        with pytest.raises(ValueError, match="order_id is required"):
            client.modify_order(order_id='', quantity=20)
    
    def test_modify_order_failure(self, connected_client):
        """Test handling of modification failure"""
        client, mock_api = connected_client
        
        mock_api.modifyOrder.return_value = {
            'status': False,
            'message': 'Order not found'
        }
        
        result = client.modify_order(
            order_id='123456789',
            quantity=20
        )
        
        assert result['status'] == 'FAILED'
        assert result['error'] == 'Order not found'
    
    # ==================== Order Cancellation Tests ====================
    
    def test_cancel_order_success(self, connected_client):
        """Test successful order cancellation"""
        client, mock_api = connected_client
        
        mock_api.cancelOrder.return_value = {
            'status': True,
            'message': 'Order cancelled successfully'
        }
        
        result = client.cancel_order(order_id='123456789')
        
        assert result['orderId'] == '123456789'
        assert result['status'] == 'CANCELLED'
        mock_api.cancelOrder.assert_called_once()
    
    def test_cancel_order_requires_order_id(self, connected_client):
        """Test that cancel requires order_id"""
        client, mock_api = connected_client
        
        with pytest.raises(ValueError, match="order_id is required"):
            client.cancel_order(order_id='')
    
    def test_cancel_order_failure(self, connected_client):
        """Test handling of cancellation failure"""
        client, mock_api = connected_client
        
        mock_api.cancelOrder.return_value = {
            'status': False,
            'message': 'Order already executed'
        }
        
        result = client.cancel_order(order_id='123456789')
        
        assert result['status'] == 'FAILED'
        assert result['error'] == 'Order already executed'
    
    # ==================== Order Book Tests ====================
    
    def test_get_order_book(self, connected_client):
        """Test fetching order book"""
        client, mock_api = connected_client
        
        mock_api.orderBook.return_value = {
            'status': True,
            'data': [
                {
                    'orderid': '123',
                    'tradingsymbol': 'RELIANCE-EQ',
                    'orderstatus': 'complete',
                    'transactiontype': 'BUY',
                    'ordertype': 'MARKET',
                    'quantity': 10,
                    'filledshares': 10,
                    'price': 0,
                    'averageprice': 2500.0
                },
                {
                    'orderid': '456',
                    'tradingsymbol': 'TCS-EQ',
                    'orderstatus': 'open',
                    'transactiontype': 'SELL',
                    'ordertype': 'LIMIT',
                    'quantity': 5,
                    'filledshares': 0,
                    'price': 3500.0,
                    'averageprice': 0
                }
            ]
        }
        
        orders = client.get_order_book()
        
        assert len(orders) == 2
        assert orders[0]['orderId'] == '123'
        assert orders[0]['status'] == 'FILLED'
        assert orders[1]['orderId'] == '456'
        assert orders[1]['status'] == 'NEW'
    
    def test_get_order_book_empty(self, connected_client):
        """Test empty order book"""
        client, mock_api = connected_client
        
        mock_api.orderBook.return_value = {
            'status': True,
            'data': None
        }
        
        orders = client.get_order_book()
        assert orders == []
    
    # ==================== Order Status Tests ====================
    
    def test_get_order_status_found(self, connected_client):
        """Test getting status of existing order"""
        client, mock_api = connected_client
        
        mock_api.orderBook.return_value = {
            'status': True,
            'data': [
                {
                    'orderid': '123456789',
                    'tradingsymbol': 'RELIANCE-EQ',
                    'orderstatus': 'complete',
                    'transactiontype': 'BUY',
                    'ordertype': 'MARKET',
                    'quantity': 10,
                    'filledshares': 10,
                    'price': 0,
                    'averageprice': 2500.0
                }
            ]
        }
        
        result = client.get_order_status('123456789')
        
        assert result['orderId'] == '123456789'
        assert result['status'] == 'FILLED'
    
    def test_get_order_status_not_found(self, connected_client):
        """Test getting status of non-existent order"""
        client, mock_api = connected_client
        
        mock_api.orderBook.return_value = {
            'status': True,
            'data': []
        }
        
        result = client.get_order_status('999999999')
        
        assert result['status'] == 'NOT_FOUND'
        assert 'error' in result
    
    # ==================== Trade Book Tests ====================
    
    def test_get_trade_book(self, connected_client):
        """Test fetching trade book"""
        client, mock_api = connected_client
        
        mock_api.tradeBook.return_value = {
            'status': True,
            'data': [
                {
                    'tradeid': 'T123',
                    'orderid': '123',
                    'tradingsymbol': 'RELIANCE-EQ',
                    'transactiontype': 'BUY',
                    'quantity': 10,
                    'price': 2500.0
                }
            ]
        }
        
        trades = client.get_trade_book()
        
        assert len(trades) == 1
        assert trades[0]['tradeId'] == 'T123'
        assert trades[0]['orderId'] == '123'
        assert trades[0]['side'] == 'BUY'
    
    def test_get_trade_book_empty(self, connected_client):
        """Test empty trade book"""
        client, mock_api = connected_client
        
        mock_api.tradeBook.return_value = {
            'status': True,
            'data': None
        }
        
        trades = client.get_trade_book()
        assert trades == []


class TestOrderTypeProperty:
    """
    Property Test 10: Order Type Support
    Validates: Requirements 4.3
    
    All valid order types must be accepted
    """
    
    @pytest.fixture
    def mock_smart_api(self):
        mock = MagicMock()
        mock.generateSession.return_value = {
            'status': True,
            'data': {'jwtToken': 'test', 'refreshToken': 'test', 'feedToken': 'test'}
        }
        mock.placeOrder.return_value = {'status': True, 'data': {'orderid': '123'}}
        return mock
    
    @pytest.fixture
    def connected_client(self, mock_smart_api):
        client = AngelOneClient(
            api_key='test', client_code='TEST', password='test', totp_secret='JBSWY3DPEHPK3PXP'
        )
        mock_class = Mock(return_value=mock_smart_api)
        client.connect_sync(smart_api_class=mock_class)
        
        from src.api.angelone.symbol_mapper import SymbolInfo
        client.symbol_mapper._instruments = {
            'NSE': {
                'TEST': SymbolInfo(
                    symbol='TEST', token='123', exchange='NSE', name='TEST',
                    lot_size=1, tick_size=0.05, instrument_type='EQ'
                )
            },
            'BSE': {}, 'NFO': {}, 'MCX': {}, 'CDS': {}, 'BFO': {}
        }
        client.symbol_mapper._loaded = True
        return client, mock_smart_api
    
    @pytest.mark.parametrize("order_type", ['MARKET', 'LIMIT', 'STOPLOSS_LIMIT', 'STOPLOSS_MARKET'])
    def test_all_order_types_accepted(self, connected_client, order_type):
        """Property: All valid order types must be accepted"""
        client, mock_api = connected_client
        
        # Set appropriate prices for order types
        price = 100.0 if order_type in ['LIMIT', 'STOPLOSS_LIMIT'] else 0
        trigger = 95.0 if order_type in ['STOPLOSS_LIMIT', 'STOPLOSS_MARKET'] else 0
        
        result = client.create_order(
            symbol='TEST',
            side='BUY',
            order_type=order_type,
            quantity=1,
            price=price,
            trigger_price=trigger
        )
        
        assert result['status'] == 'PLACED'
        assert result['type'] == order_type


class TestOrderResponseProperty:
    """
    Property Test 11: Order Response Format
    Validates: Requirements 4.5
    
    All order responses must contain required fields
    """
    
    @pytest.fixture
    def mock_smart_api(self):
        mock = MagicMock()
        mock.generateSession.return_value = {
            'status': True,
            'data': {'jwtToken': 'test', 'refreshToken': 'test', 'feedToken': 'test'}
        }
        return mock
    
    @pytest.fixture
    def connected_client(self, mock_smart_api):
        client = AngelOneClient(
            api_key='test', client_code='TEST', password='test', totp_secret='JBSWY3DPEHPK3PXP'
        )
        mock_class = Mock(return_value=mock_smart_api)
        client.connect_sync(smart_api_class=mock_class)
        
        from src.api.angelone.symbol_mapper import SymbolInfo
        client.symbol_mapper._instruments = {
            'NSE': {
                'TEST': SymbolInfo(
                    symbol='TEST', token='123', exchange='NSE', name='TEST',
                    lot_size=1, tick_size=0.05, instrument_type='EQ'
                )
            },
            'BSE': {}, 'NFO': {}, 'MCX': {}, 'CDS': {}, 'BFO': {}
        }
        client.symbol_mapper._loaded = True
        return client, mock_smart_api
    
    def test_successful_order_has_required_fields(self, connected_client):
        """Property: Successful order response has all required fields"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': True,
            'data': {'orderid': '123456'}
        }
        
        result = client.create_order(
            symbol='TEST', side='BUY', order_type='MARKET', quantity=1
        )
        
        required_fields = ['orderId', 'symbol', 'status', 'side', 'type', 'quantity', 'time']
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
    
    def test_rejected_order_has_error_field(self, connected_client):
        """Property: Rejected order response has error field"""
        client, mock_api = connected_client
        
        mock_api.placeOrder.return_value = {
            'status': False,
            'message': 'Test error'
        }
        
        result = client.create_order(
            symbol='TEST', side='BUY', order_type='MARKET', quantity=1
        )
        
        assert result['status'] == 'REJECTED'
        assert 'error' in result
        assert result['error'] == 'Test error'
