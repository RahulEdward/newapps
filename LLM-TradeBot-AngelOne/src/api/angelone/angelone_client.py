"""
AngelOne Client - Main Broker Interface
Provides same interface as original Binance client for compatibility
All AI agents work without modification using this client

Requirements: 1.1, 2.1, 2.3, 2.4, 2.5
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger

from .auth_manager import AuthManager, AuthenticationError
from .symbol_mapper import SymbolMapper, SymbolNotFoundError
from .market_hours import MarketHoursManager
from .data_converter import DataConverter


class AngelOneClient:
    """
    Main broker client - replaces Binance client
    Provides same interface as original for compatibility
    
    Features:
    - Authentication with TOTP
    - Historical data fetching (get_klines)
    - Current price fetching (get_ticker_price)
    - Order placement and management
    - Position and account info
    """
    
    # Interval mapping: Binance -> AngelOne
    INTERVAL_MAP = {
        '1m': 'ONE_MINUTE',
        '3m': 'THREE_MINUTE',
        '5m': 'FIVE_MINUTE',
        '10m': 'TEN_MINUTE',
        '15m': 'FIFTEEN_MINUTE',
        '30m': 'THIRTY_MINUTE',
        '1h': 'ONE_HOUR',
        '1d': 'ONE_DAY',
        # AngelOne native intervals
        'ONE_MINUTE': 'ONE_MINUTE',
        'THREE_MINUTE': 'THREE_MINUTE',
        'FIVE_MINUTE': 'FIVE_MINUTE',
        'TEN_MINUTE': 'TEN_MINUTE',
        'FIFTEEN_MINUTE': 'FIFTEEN_MINUTE',
        'THIRTY_MINUTE': 'THIRTY_MINUTE',
        'ONE_HOUR': 'ONE_HOUR',
        'ONE_DAY': 'ONE_DAY',
    }
    
    # Valid exchanges
    VALID_EXCHANGES = ['NSE', 'BSE', 'NFO', 'MCX', 'CDS', 'BFO']
    
    def __init__(
        self,
        api_key: str,
        client_code: str,
        password: str,
        totp_secret: str,
        default_exchange: str = 'NSE'
    ):
        """
        Initialize AngelOne Client
        
        Args:
            api_key: AngelOne API key
            client_code: Trading account client code
            password: Account password
            totp_secret: TOTP secret for 2FA
            default_exchange: Default exchange (NSE, BSE, NFO, MCX)
        """
        self.default_exchange = default_exchange.upper()
        
        # Initialize components
        self.auth_manager = AuthManager(api_key, client_code, password, totp_secret)
        self.symbol_mapper = SymbolMapper()
        self.market_hours = MarketHoursManager()
        self.data_converter = DataConverter()
        
        self._connected = False
        self._smart_api = None
        
        logger.info(f"AngelOneClient initialized for {client_code}")
    
    async def connect(self) -> bool:
        """
        Authenticate and connect to AngelOne
        
        Returns:
            True if connection successful
        """
        try:
            logger.info("Connecting to AngelOne...")
            
            # Login
            tokens = self.auth_manager.login()
            self._smart_api = self.auth_manager.smart_api
            
            # Load instruments
            logger.info("Loading instrument master...")
            self.symbol_mapper.load_instruments()
            
            self._connected = True
            logger.info("Connected to AngelOne successfully")
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            self._connected = False
            raise
    
    def connect_sync(self, smart_api_class=None) -> bool:
        """
        Synchronous connect method
        
        Args:
            smart_api_class: Optional SmartConnect class for testing
        """
        try:
            logger.info("Connecting to AngelOne...")
            
            # Login
            tokens = self.auth_manager.login(smart_api_class=smart_api_class)
            self._smart_api = self.auth_manager.smart_api
            
            self._connected = True
            logger.info("Connected to AngelOne successfully")
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            self._connected = False
            raise
    
    def _ensure_connected(self) -> None:
        """Ensure client is connected"""
        if not self._connected:
            raise ConnectionError("Not connected to AngelOne. Call connect() first.")
        
        # Refresh session if needed
        self.auth_manager.ensure_valid_session()
    
    def _get_angelone_interval(self, interval: str) -> str:
        """Convert interval to AngelOne format"""
        interval = interval.upper() if interval.upper() in self.INTERVAL_MAP else interval.lower()
        if interval not in self.INTERVAL_MAP:
            raise ValueError(f"Invalid interval: {interval}. Valid: {list(self.INTERVAL_MAP.keys())}")
        return self.INTERVAL_MAP[interval]
    
    def _validate_exchange(self, exchange: str) -> str:
        """Validate and normalize exchange"""
        exchange = exchange.upper()
        if exchange not in self.VALID_EXCHANGES:
            raise ValueError(f"Invalid exchange: {exchange}. Valid: {self.VALID_EXCHANGES}")
        return exchange
    
    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        exchange: str = None,
        from_date: datetime = None,
        to_date: datetime = None
    ) -> List[Dict]:
        """
        Get historical candles - SAME INTERFACE as Binance
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE-EQ", "NIFTY")
            interval: Candle interval (1m, 5m, 15m, 1h, 1d)
            limit: Number of candles to fetch
            exchange: Exchange (NSE, BSE, NFO, MCX)
            from_date: Start date (optional)
            to_date: End date (optional)
        
        Returns:
            List of candles in Binance-compatible format
        """
        self._ensure_connected()
        
        exchange = self._validate_exchange(exchange or self.default_exchange)
        angelone_interval = self._get_angelone_interval(interval)
        
        # Get symbol token
        try:
            symbol_info = self.symbol_mapper.get_symbol_info(symbol, exchange)
            token = symbol_info.token
        except SymbolNotFoundError:
            # Try loading instruments if not loaded
            if not self.symbol_mapper.is_loaded:
                self.symbol_mapper.load_instruments()
                symbol_info = self.symbol_mapper.get_symbol_info(symbol, exchange)
                token = symbol_info.token
            else:
                raise
        
        # Calculate date range
        if to_date is None:
            to_date = datetime.now()
        if from_date is None:
            # Calculate from_date based on interval and limit
            interval_minutes = self._get_interval_minutes(angelone_interval)
            from_date = to_date - timedelta(minutes=interval_minutes * limit)
        
        # Format dates for AngelOne
        from_str = from_date.strftime("%Y-%m-%d %H:%M")
        to_str = to_date.strftime("%Y-%m-%d %H:%M")
        
        # Fetch data from AngelOne
        params = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": angelone_interval,
            "fromdate": from_str,
            "todate": to_str
        }
        
        try:
            response = self._smart_api.getCandleData(params)
            
            if response and response.get('status') and response.get('data'):
                candles = response['data']
                # Convert to Binance format
                return self.data_converter.convert_candles(candles)
            else:
                logger.warning(f"No candle data returned: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch candles: {str(e)}")
            raise
    
    def _get_interval_minutes(self, interval: str) -> int:
        """Get interval duration in minutes"""
        interval_map = {
            'ONE_MINUTE': 1,
            'THREE_MINUTE': 3,
            'FIVE_MINUTE': 5,
            'TEN_MINUTE': 10,
            'FIFTEEN_MINUTE': 15,
            'THIRTY_MINUTE': 30,
            'ONE_HOUR': 60,
            'ONE_DAY': 1440,
        }
        return interval_map.get(interval, 5)
    
    def get_ticker_price(self, symbol: str, exchange: str = None) -> Dict:
        """
        Get current price - SAME INTERFACE as Binance
        
        Args:
            symbol: Trading symbol
            exchange: Exchange
        
        Returns:
            Dict with symbol and price
        """
        self._ensure_connected()
        
        exchange = self._validate_exchange(exchange or self.default_exchange)
        
        try:
            symbol_info = self.symbol_mapper.get_symbol_info(symbol, exchange)
            token = symbol_info.token
            
            # Get LTP from AngelOne
            response = self._smart_api.ltpData(exchange, symbol, token)
            
            if response and response.get('status') and response.get('data'):
                return self.data_converter.convert_ticker(response['data'], symbol)
            else:
                logger.warning(f"No ticker data returned: {response}")
                return {'symbol': symbol, 'price': 0.0, 'time': 0}
                
        except Exception as e:
            logger.error(f"Failed to fetch ticker: {str(e)}")
            raise
    
    def get_account(self) -> Dict:
        """
        Get account info - SAME INTERFACE as Binance
        
        Returns:
            Dict with account balance info
        """
        self._ensure_connected()
        
        try:
            response = self._smart_api.rmsLimit()
            
            if response and response.get('status') and response.get('data'):
                return self.data_converter.convert_account(response['data'])
            else:
                logger.warning(f"No account data returned: {response}")
                return {'totalBalance': 0.0, 'availableBalance': 0.0, 'totalUnrealizedProfit': 0.0}
                
        except Exception as e:
            logger.error(f"Failed to fetch account: {str(e)}")
            raise
    
    def get_positions(self) -> List[Dict]:
        """
        Get current positions
        
        Returns:
            List of positions in Binance-compatible format
        """
        self._ensure_connected()
        
        try:
            response = self._smart_api.position()
            
            if response and response.get('status') and response.get('data'):
                return self.data_converter.convert_positions(response['data'])
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch positions: {str(e)}")
            raise
    
    def get_holdings(self) -> List[Dict]:
        """
        Get current holdings (delivery positions)
        
        Returns:
            List of holdings
        """
        self._ensure_connected()
        
        try:
            response = self._smart_api.holding()
            
            if response and response.get('status') and response.get('data'):
                return response['data']
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch holdings: {str(e)}")
            raise
    
    # ==================== ORDER EXECUTION (Task 8) ====================
    
    # Valid order types
    VALID_ORDER_TYPES = ['MARKET', 'LIMIT', 'STOPLOSS_LIMIT', 'STOPLOSS_MARKET']
    
    # Valid product types
    VALID_PRODUCT_TYPES = ['INTRADAY', 'DELIVERY', 'CARRYFORWARD', 'MARGIN', 'BO', 'CO']
    
    # Valid transaction types
    VALID_TRANSACTION_TYPES = ['BUY', 'SELL']
    
    # Valid varieties
    VALID_VARIETIES = ['NORMAL', 'STOPLOSS', 'AMO', 'ROBO']
    
    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float = 0.0,
        trigger_price: float = 0.0,
        product_type: str = 'INTRADAY',
        exchange: str = None,
        variety: str = 'NORMAL',
        duration: str = 'DAY'
    ) -> Dict:
        """
        Place a new order - SAME INTERFACE as Binance
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE-EQ")
            side: BUY or SELL
            order_type: MARKET, LIMIT, STOPLOSS_LIMIT, STOPLOSS_MARKET
            quantity: Number of shares/lots
            price: Limit price (required for LIMIT orders)
            trigger_price: Trigger price (required for STOPLOSS orders)
            product_type: INTRADAY, DELIVERY, CARRYFORWARD, MARGIN
            exchange: Exchange (NSE, BSE, NFO, MCX)
            variety: NORMAL, STOPLOSS, AMO, ROBO
            duration: DAY or IOC
        
        Returns:
            Dict with orderId, status, and other details
        
        Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
        """
        self._ensure_connected()
        
        # Validate inputs
        side = side.upper()
        if side not in self.VALID_TRANSACTION_TYPES:
            raise ValueError(f"Invalid side: {side}. Valid: {self.VALID_TRANSACTION_TYPES}")
        
        order_type = order_type.upper()
        if order_type not in self.VALID_ORDER_TYPES:
            raise ValueError(f"Invalid order_type: {order_type}. Valid: {self.VALID_ORDER_TYPES}")
        
        product_type = product_type.upper()
        if product_type not in self.VALID_PRODUCT_TYPES:
            raise ValueError(f"Invalid product_type: {product_type}. Valid: {self.VALID_PRODUCT_TYPES}")
        
        variety = variety.upper()
        if variety not in self.VALID_VARIETIES:
            raise ValueError(f"Invalid variety: {variety}. Valid: {self.VALID_VARIETIES}")
        
        exchange = self._validate_exchange(exchange or self.default_exchange)
        
        # Get symbol token
        try:
            symbol_info = self.symbol_mapper.get_symbol_info(symbol, exchange)
            token = symbol_info.token
            trading_symbol = symbol_info.name  # Use name as trading symbol
        except SymbolNotFoundError:
            if not self.symbol_mapper.is_loaded:
                self.symbol_mapper.load_instruments()
                symbol_info = self.symbol_mapper.get_symbol_info(symbol, exchange)
                token = symbol_info.token
                trading_symbol = symbol_info.name
            else:
                raise
        
        # Build order params
        order_params = {
            "variety": variety,
            "tradingsymbol": trading_symbol,
            "symboltoken": token,
            "transactiontype": side,
            "exchange": exchange,
            "ordertype": order_type,
            "producttype": product_type,
            "duration": duration,
            "quantity": str(quantity),
        }
        
        # Add price for LIMIT orders
        if order_type in ['LIMIT', 'STOPLOSS_LIMIT']:
            if price <= 0:
                raise ValueError("Price required for LIMIT orders")
            order_params["price"] = str(price)
        else:
            order_params["price"] = "0"
        
        # Add trigger price for STOPLOSS orders
        if order_type in ['STOPLOSS_LIMIT', 'STOPLOSS_MARKET']:
            if trigger_price <= 0:
                raise ValueError("Trigger price required for STOPLOSS orders")
            order_params["triggerprice"] = str(trigger_price)
        else:
            order_params["triggerprice"] = "0"
        
        logger.info(f"Placing order: {side} {quantity} {symbol} @ {order_type}")
        
        try:
            response = self._smart_api.placeOrder(order_params)
            
            if response and response.get('status'):
                order_id = response.get('data', {}).get('orderid', response.get('data'))
                result = {
                    'orderId': str(order_id) if order_id else '',
                    'symbol': symbol,
                    'status': 'PLACED',
                    'side': side,
                    'type': order_type,
                    'quantity': quantity,
                    'price': price,
                    'executedQty': 0,
                    'time': int(datetime.now().timestamp() * 1000)
                }
                logger.info(f"Order placed successfully: {order_id}")
                return result
            else:
                error_msg = response.get('message', 'Order placement failed') if response else 'No response'
                logger.error(f"Order failed: {error_msg}")
                return {
                    'orderId': '',
                    'symbol': symbol,
                    'status': 'REJECTED',
                    'side': side,
                    'type': order_type,
                    'quantity': quantity,
                    'price': price,
                    'executedQty': 0,
                    'error': error_msg,
                    'time': int(datetime.now().timestamp() * 1000)
                }
                
        except Exception as e:
            logger.error(f"Order placement error: {str(e)}")
            raise
    
    def modify_order(
        self,
        order_id: str,
        quantity: int = None,
        price: float = None,
        trigger_price: float = None,
        order_type: str = None,
        variety: str = 'NORMAL'
    ) -> Dict:
        """
        Modify an existing order
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity (optional)
            price: New price (optional)
            trigger_price: New trigger price (optional)
            order_type: New order type (optional)
            variety: Order variety
        
        Returns:
            Dict with modification status
        
        Requirements: 4.6
        """
        self._ensure_connected()
        
        if not order_id:
            raise ValueError("order_id is required")
        
        # Build modify params
        modify_params = {
            "variety": variety.upper(),
            "orderid": order_id,
        }
        
        if quantity is not None:
            modify_params["quantity"] = str(quantity)
        
        if price is not None:
            modify_params["price"] = str(price)
        
        if trigger_price is not None:
            modify_params["triggerprice"] = str(trigger_price)
        
        if order_type is not None:
            order_type = order_type.upper()
            if order_type not in self.VALID_ORDER_TYPES:
                raise ValueError(f"Invalid order_type: {order_type}")
            modify_params["ordertype"] = order_type
        
        logger.info(f"Modifying order: {order_id}")
        
        try:
            response = self._smart_api.modifyOrder(modify_params)
            
            if response and response.get('status'):
                result = {
                    'orderId': order_id,
                    'status': 'MODIFIED',
                    'message': response.get('message', 'Order modified successfully'),
                    'time': int(datetime.now().timestamp() * 1000)
                }
                logger.info(f"Order modified successfully: {order_id}")
                return result
            else:
                error_msg = response.get('message', 'Order modification failed') if response else 'No response'
                logger.error(f"Order modification failed: {error_msg}")
                return {
                    'orderId': order_id,
                    'status': 'FAILED',
                    'error': error_msg,
                    'time': int(datetime.now().timestamp() * 1000)
                }
                
        except Exception as e:
            logger.error(f"Order modification error: {str(e)}")
            raise
    
    def cancel_order(self, order_id: str, variety: str = 'NORMAL') -> Dict:
        """
        Cancel an existing order
        
        Args:
            order_id: Order ID to cancel
            variety: Order variety
        
        Returns:
            Dict with cancellation status
        
        Requirements: 4.7
        """
        self._ensure_connected()
        
        if not order_id:
            raise ValueError("order_id is required")
        
        cancel_params = {
            "variety": variety.upper(),
            "orderid": order_id,
        }
        
        logger.info(f"Cancelling order: {order_id}")
        
        try:
            response = self._smart_api.cancelOrder(cancel_params)
            
            if response and response.get('status'):
                result = {
                    'orderId': order_id,
                    'status': 'CANCELLED',
                    'message': response.get('message', 'Order cancelled successfully'),
                    'time': int(datetime.now().timestamp() * 1000)
                }
                logger.info(f"Order cancelled successfully: {order_id}")
                return result
            else:
                error_msg = response.get('message', 'Order cancellation failed') if response else 'No response'
                logger.error(f"Order cancellation failed: {error_msg}")
                return {
                    'orderId': order_id,
                    'status': 'FAILED',
                    'error': error_msg,
                    'time': int(datetime.now().timestamp() * 1000)
                }
                
        except Exception as e:
            logger.error(f"Order cancellation error: {str(e)}")
            raise
    
    def get_order_book(self) -> List[Dict]:
        """
        Get all orders for the day
        
        Returns:
            List of orders in Binance-compatible format
        """
        self._ensure_connected()
        
        try:
            response = self._smart_api.orderBook()
            
            if response and response.get('status') and response.get('data'):
                return self.data_converter.convert_orders(response['data'])
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch order book: {str(e)}")
            raise
    
    def get_order_status(self, order_id: str) -> Dict:
        """
        Get status of a specific order
        
        Args:
            order_id: Order ID to check
        
        Returns:
            Dict with order details
        """
        self._ensure_connected()
        
        try:
            # Get all orders and find the specific one
            orders = self.get_order_book()
            for order in orders:
                if order.get('orderId') == order_id:
                    return order
            
            return {
                'orderId': order_id,
                'status': 'NOT_FOUND',
                'error': 'Order not found'
            }
                
        except Exception as e:
            logger.error(f"Failed to fetch order status: {str(e)}")
            raise
    
    def get_trade_book(self) -> List[Dict]:
        """
        Get all trades for the day
        
        Returns:
            List of executed trades
        """
        self._ensure_connected()
        
        try:
            response = self._smart_api.tradeBook()
            
            if response and response.get('status') and response.get('data'):
                return self.data_converter.convert_trades(response['data'])
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch trade book: {str(e)}")
            raise
    
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        return self.market_hours.is_market_open()
    
    def get_market_session(self) -> str:
        """Get current market session"""
        return self.market_hours.get_market_session()
    
    def disconnect(self) -> None:
        """Disconnect from AngelOne"""
        try:
            self.auth_manager.logout()
            self._connected = False
            self._smart_api = None
            logger.info("Disconnected from AngelOne")
        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        return self._connected
    
    @property
    def client_code(self) -> str:
        """Get client code"""
        return self.auth_manager.client_code
