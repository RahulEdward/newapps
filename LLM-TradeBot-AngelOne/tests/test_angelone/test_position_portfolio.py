"""
Tests for Position and Portfolio Management (Task 9)
Tests position fetching, holdings, margin, and P&L calculation

Requirements: 5.1, 5.2, 5.3, 5.4, 5.6
Property Tests: 12, 13
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.api.angelone.angelone_client import AngelOneClient
from src.api.angelone.data_converter import DataConverter


class TestPositionPortfolio:
    """Test position and portfolio management functionality"""
    
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
        
        mock_class = Mock(return_value=mock_smart_api)
        client.connect_sync(smart_api_class=mock_class)
        
        from src.api.angelone.symbol_mapper import SymbolInfo
        client.symbol_mapper._instruments = {
            'NSE': {
                'RELIANCE-EQ': SymbolInfo(
                    symbol='RELIANCE-EQ', token='2885', exchange='NSE',
                    name='RELIANCE-EQ', lot_size=1, tick_size=0.05, instrument_type='EQ'
                )
            },
            'BSE': {}, 'NFO': {}, 'MCX': {}, 'CDS': {}, 'BFO': {}
        }
        client.symbol_mapper._loaded = True
        
        return client, mock_smart_api
    
    # ==================== Position Tests ====================
    
    def test_get_positions_success(self, connected_client):
        """Test fetching positions"""
        client, mock_api = connected_client
        
        mock_api.position.return_value = {
            'status': True,
            'data': [
                {
                    'tradingsymbol': 'RELIANCE-EQ',
                    'netqty': 10,
                    'avgnetprice': 2500.0,
                    'ltp': 2550.0,
                    'unrealised': 500.0,
                    'exchange': 'NSE'
                },
                {
                    'tradingsymbol': 'TCS-EQ',
                    'netqty': -5,
                    'avgnetprice': 3500.0,
                    'ltp': 3450.0,
                    'unrealised': 250.0,
                    'exchange': 'NSE'
                }
            ]
        }
        
        positions = client.get_positions()
        
        assert len(positions) == 2
        assert positions[0]['symbol'] == 'RELIANCE-EQ'
        assert positions[0]['positionAmt'] == 10
        assert positions[0]['entryPrice'] == 2500.0
        assert positions[0]['markPrice'] == 2550.0
        assert positions[0]['unRealizedProfit'] == 500.0
    
    def test_get_positions_empty(self, connected_client):
        """Test empty positions"""
        client, mock_api = connected_client
        
        mock_api.position.return_value = {
            'status': True,
            'data': None
        }
        
        positions = client.get_positions()
        assert positions == []
    
    def test_get_positions_with_short_position(self, connected_client):
        """Test positions with short (negative) quantity"""
        client, mock_api = connected_client
        
        mock_api.position.return_value = {
            'status': True,
            'data': [
                {
                    'tradingsymbol': 'NIFTY-FUT',
                    'netqty': -50,
                    'avgnetprice': 22000.0,
                    'ltp': 21900.0,
                    'unrealised': 5000.0,
                    'exchange': 'NFO'
                }
            ]
        }
        
        positions = client.get_positions()
        
        assert len(positions) == 1
        assert positions[0]['positionAmt'] == -50  # Short position
        assert positions[0]['unRealizedProfit'] == 5000.0
    
    # ==================== Holdings Tests ====================
    
    def test_get_holdings_success(self, connected_client):
        """Test fetching holdings"""
        client, mock_api = connected_client
        
        mock_api.holding.return_value = {
            'status': True,
            'data': [
                {
                    'tradingsymbol': 'RELIANCE-EQ',
                    'quantity': 100,
                    'averageprice': 2400.0,
                    'ltp': 2550.0,
                    'profitandloss': 15000.0
                },
                {
                    'tradingsymbol': 'INFY-EQ',
                    'quantity': 50,
                    'averageprice': 1500.0,
                    'ltp': 1600.0,
                    'profitandloss': 5000.0
                }
            ]
        }
        
        holdings = client.get_holdings()
        
        assert len(holdings) == 2
        assert holdings[0]['tradingsymbol'] == 'RELIANCE-EQ'
        assert holdings[0]['quantity'] == 100
    
    def test_get_holdings_empty(self, connected_client):
        """Test empty holdings"""
        client, mock_api = connected_client
        
        mock_api.holding.return_value = {
            'status': True,
            'data': None
        }
        
        holdings = client.get_holdings()
        assert holdings == []
    
    # ==================== Account/Margin Tests ====================
    
    def test_get_account_success(self, connected_client):
        """Test fetching account info"""
        client, mock_api = connected_client
        
        mock_api.rmsLimit.return_value = {
            'status': True,
            'data': {
                'net': 500000.0,
                'availablecash': 250000.0,
                'utiliseddebits': 250000.0,
                'm2munrealized': 5000.0
            }
        }
        
        account = client.get_account()
        
        assert account['totalBalance'] == 500000.0
        assert account['availableBalance'] == 250000.0
        assert account['totalUnrealizedProfit'] == 5000.0
    
    def test_get_account_empty(self, connected_client):
        """Test empty account response"""
        client, mock_api = connected_client
        
        mock_api.rmsLimit.return_value = {
            'status': True,
            'data': None
        }
        
        account = client.get_account()
        
        assert account['totalBalance'] == 0.0
        assert account['availableBalance'] == 0.0


class TestPnLCalculationProperty:
    """
    Property Test 12: P&L Calculation
    Validates: Requirements 5.3
    
    P&L must be calculated correctly from entry and current price
    """
    
    @pytest.fixture
    def converter(self):
        return DataConverter()
    
    def test_long_position_profit(self, converter):
        """Test P&L for profitable long position"""
        position = {
            'tradingsymbol': 'TEST',
            'netqty': 10,
            'avgnetprice': 100.0,
            'ltp': 110.0,
            'unrealised': 100.0  # 10 * (110 - 100) = 100
        }
        
        result = converter.convert_position(position)
        
        assert result['positionAmt'] == 10
        assert result['entryPrice'] == 100.0
        assert result['markPrice'] == 110.0
        assert result['unRealizedProfit'] == 100.0
        # Percentage: (110 - 100) / 100 * 100 = 10%
        assert abs(result['percentage'] - 10.0) < 0.01
    
    def test_long_position_loss(self, converter):
        """Test P&L for losing long position"""
        position = {
            'tradingsymbol': 'TEST',
            'netqty': 10,
            'avgnetprice': 100.0,
            'ltp': 90.0,
            'unrealised': -100.0  # 10 * (90 - 100) = -100
        }
        
        result = converter.convert_position(position)
        
        assert result['unRealizedProfit'] == -100.0
        # Percentage: (90 - 100) / 100 * 100 = -10%
        assert abs(result['percentage'] - (-10.0)) < 0.01
    
    def test_short_position_profit(self, converter):
        """Test P&L for profitable short position"""
        position = {
            'tradingsymbol': 'TEST',
            'netqty': -10,
            'avgnetprice': 100.0,
            'ltp': 90.0,
            'unrealised': 100.0  # Short profit when price goes down
        }
        
        result = converter.convert_position(position)
        
        assert result['positionAmt'] == -10
        assert result['unRealizedProfit'] == 100.0
    
    def test_zero_quantity_position(self, converter):
        """Test P&L for zero quantity (closed) position"""
        position = {
            'tradingsymbol': 'TEST',
            'netqty': 0,
            'avgnetprice': 100.0,
            'ltp': 110.0,
            'unrealised': 0.0
        }
        
        result = converter.convert_position(position)
        
        assert result['positionAmt'] == 0
        assert result['percentage'] == 0.0  # No percentage for zero position


class TestPositionDataConversionProperty:
    """
    Property Test 13: Position Data Conversion
    Validates: Requirements 5.6
    
    Position data must be converted to Binance-compatible format
    """
    
    @pytest.fixture
    def converter(self):
        return DataConverter()
    
    def test_position_has_required_fields(self, converter):
        """Test that converted position has all required fields"""
        position = {
            'tradingsymbol': 'RELIANCE-EQ',
            'netqty': 10,
            'avgnetprice': 2500.0,
            'ltp': 2550.0,
            'unrealised': 500.0
        }
        
        result = converter.convert_position(position)
        
        required_fields = ['symbol', 'positionAmt', 'entryPrice', 'markPrice', 'unRealizedProfit', 'percentage']
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
    
    def test_position_field_types(self, converter):
        """Test that converted position fields have correct types"""
        position = {
            'tradingsymbol': 'RELIANCE-EQ',
            'netqty': 10,
            'avgnetprice': 2500.0,
            'ltp': 2550.0,
            'unrealised': 500.0
        }
        
        result = converter.convert_position(position)
        
        assert isinstance(result['symbol'], str)
        assert isinstance(result['positionAmt'], (int, float))
        assert isinstance(result['entryPrice'], float)
        assert isinstance(result['markPrice'], float)
        assert isinstance(result['unRealizedProfit'], float)
        assert isinstance(result['percentage'], float)
    
    def test_multiple_positions_conversion(self, converter):
        """Test converting multiple positions"""
        positions = [
            {
                'tradingsymbol': 'RELIANCE-EQ',
                'netqty': 10,
                'avgnetprice': 2500.0,
                'ltp': 2550.0,
                'unrealised': 500.0
            },
            {
                'tradingsymbol': 'TCS-EQ',
                'netqty': 5,
                'avgnetprice': 3500.0,
                'ltp': 3600.0,
                'unrealised': 500.0
            }
        ]
        
        results = converter.convert_positions(positions)
        
        assert len(results) == 2
        assert results[0]['symbol'] == 'RELIANCE-EQ'
        assert results[1]['symbol'] == 'TCS-EQ'
    
    def test_position_with_missing_fields(self, converter):
        """Test position conversion with missing optional fields"""
        position = {
            'tradingsymbol': 'TEST',
            'netqty': 10
            # Missing avgnetprice, ltp, unrealised
        }
        
        result = converter.convert_position(position)
        
        # Should use defaults for missing fields
        assert result['symbol'] == 'TEST'
        assert result['positionAmt'] == 10
        assert result['entryPrice'] == 0.0
        assert result['markPrice'] == 0.0
        assert result['unRealizedProfit'] == 0.0


class TestAccountConversion:
    """Test account/margin data conversion"""
    
    @pytest.fixture
    def converter(self):
        return DataConverter()
    
    def test_account_has_required_fields(self, converter):
        """Test that converted account has all required fields"""
        account = {
            'net': 500000.0,
            'availablecash': 250000.0,
            'm2munrealized': 5000.0
        }
        
        result = converter.convert_account(account)
        
        required_fields = ['totalBalance', 'availableBalance', 'totalUnrealizedProfit']
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
    
    def test_account_with_alternative_field_names(self, converter):
        """Test account conversion with alternative field names"""
        account = {
            'total': 500000.0,
            'available': 250000.0,
            'unrealised': 5000.0
        }
        
        result = converter.convert_account(account)
        
        assert result['totalBalance'] == 500000.0
        assert result['availableBalance'] == 250000.0
    
    def test_account_with_missing_fields(self, converter):
        """Test account conversion with missing fields"""
        account = {}
        
        result = converter.convert_account(account)
        
        assert result['totalBalance'] == 0.0
        assert result['availableBalance'] == 0.0
        assert result['totalUnrealizedProfit'] == 0.0
