"""
Data Converter for AngelOne
Converts AngelOne data format to Binance-compatible format
Ensures all AI agents receive data in expected format

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class BinanceCandle:
    """Binance-compatible candle format"""
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float
    trades: int
    taker_buy_base: float
    taker_buy_quote: float


@dataclass
class BinanceTicker:
    """Binance-compatible ticker format"""
    symbol: str
    price: float
    time: int


@dataclass
class BinanceOrder:
    """Binance-compatible order response format"""
    orderId: str
    symbol: str
    status: str
    side: str
    type: str
    price: float
    origQty: float
    executedQty: float
    avgPrice: float
    time: int


@dataclass
class BinancePosition:
    """Binance-compatible position format"""
    symbol: str
    positionAmt: float
    entryPrice: float
    markPrice: float
    unRealizedProfit: float
    percentage: float


@dataclass
class BinanceAccount:
    """Binance-compatible account format"""
    totalBalance: float
    availableBalance: float
    totalUnrealizedProfit: float


class DataConverter:
    """
    Converts AngelOne data format to Binance-compatible format
    
    Features:
    - Convert candle data
    - Convert ticker data
    - Convert order responses
    - Convert position data
    - Convert account info
    - Handle missing fields with defaults
    """
    
    # Default values for missing fields
    DEFAULTS = {
        'int': 0,
        'float': 0.0,
        'str': '',
        'list': [],
    }
    
    def __init__(self):
        """Initialize DataConverter"""
        logger.info("DataConverter initialized")
    
    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Safely convert value to float"""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Safely convert value to int"""
        if value is None:
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default
    
    def _safe_str(self, value: Any, default: str = '') -> str:
        """Safely convert value to string"""
        if value is None:
            return default
        return str(value)
    
    def _timestamp_to_ms(self, timestamp: Any) -> int:
        """Convert timestamp to milliseconds"""
        if timestamp is None:
            return int(datetime.now().timestamp() * 1000)
        
        if isinstance(timestamp, datetime):
            return int(timestamp.timestamp() * 1000)
        
        if isinstance(timestamp, str):
            try:
                # Try parsing ISO format
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return int(dt.timestamp() * 1000)
            except ValueError:
                try:
                    # Try parsing AngelOne format: "2025-01-06T09:15:00+05:30"
                    dt = datetime.strptime(timestamp[:19], "%Y-%m-%dT%H:%M:%S")
                    return int(dt.timestamp() * 1000)
                except ValueError:
                    return int(datetime.now().timestamp() * 1000)
        
        # Assume it's already a timestamp
        ts = self._safe_int(timestamp)
        # If it's in seconds, convert to milliseconds
        if ts < 10000000000:
            ts *= 1000
        return ts
    
    def convert_candle(self, angelone_candle: List) -> Dict:
        """
        Convert AngelOne candle to Binance format
        
        AngelOne format: [timestamp, open, high, low, close, volume]
        
        Returns:
            Dict in Binance candle format
        """
        if not angelone_candle or len(angelone_candle) < 6:
            logger.warning(f"Invalid candle data: {angelone_candle}")
            return self._empty_candle()
        
        timestamp = self._timestamp_to_ms(angelone_candle[0])
        open_price = self._safe_float(angelone_candle[1])
        high = self._safe_float(angelone_candle[2])
        low = self._safe_float(angelone_candle[3])
        close = self._safe_float(angelone_candle[4])
        volume = self._safe_float(angelone_candle[5])
        
        # Calculate quote volume (volume * average price)
        avg_price = (open_price + close) / 2 if (open_price + close) > 0 else 0
        quote_volume = volume * avg_price
        
        candle = BinanceCandle(
            open_time=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            close_time=timestamp + 60000,  # Assume 1 minute candle
            quote_volume=quote_volume,
            trades=0,  # Not available from AngelOne
            taker_buy_base=0.0,
            taker_buy_quote=0.0
        )
        
        return asdict(candle)
    
    def _empty_candle(self) -> Dict:
        """Return empty candle with default values"""
        now = int(datetime.now().timestamp() * 1000)
        return asdict(BinanceCandle(
            open_time=now,
            open=0.0,
            high=0.0,
            low=0.0,
            close=0.0,
            volume=0.0,
            close_time=now,
            quote_volume=0.0,
            trades=0,
            taker_buy_base=0.0,
            taker_buy_quote=0.0
        ))
    
    def convert_candles(self, angelone_candles: List[List]) -> List[Dict]:
        """Convert list of AngelOne candles to Binance format"""
        return [self.convert_candle(c) for c in angelone_candles]
    
    def convert_ticker(self, angelone_ticker: Dict, symbol: str = '') -> Dict:
        """
        Convert AngelOne ticker/LTP to Binance format
        
        AngelOne format: {'ltp': price, 'symbol': symbol, ...}
        
        Returns:
            Dict in Binance ticker format
        """
        price = self._safe_float(
            angelone_ticker.get('ltp') or 
            angelone_ticker.get('last_price') or
            angelone_ticker.get('close')
        )
        
        ticker_symbol = self._safe_str(
            symbol or 
            angelone_ticker.get('symbol') or
            angelone_ticker.get('tradingsymbol')
        )
        
        ticker = BinanceTicker(
            symbol=ticker_symbol,
            price=price,
            time=int(datetime.now().timestamp() * 1000)
        )
        
        return asdict(ticker)
    
    def convert_order_response(self, angelone_order: Dict) -> Dict:
        """
        Convert AngelOne order response to Binance format
        
        AngelOne format:
        {
            'orderid': '123456',
            'tradingsymbol': 'RELIANCE-EQ',
            'orderstatus': 'complete',
            'transactiontype': 'BUY',
            'ordertype': 'MARKET',
            'price': 2500.0,
            'quantity': 10,
            'filledshares': 10,
            'averageprice': 2500.0,
            ...
        }
        """
        # Map AngelOne status to Binance status
        status_map = {
            'complete': 'FILLED',
            'rejected': 'REJECTED',
            'cancelled': 'CANCELED',
            'open': 'NEW',
            'pending': 'NEW',
            'trigger pending': 'NEW',
            'open pending': 'NEW',
            'validation pending': 'NEW',
            'put order req received': 'NEW',
            'modify pending': 'PARTIALLY_FILLED',
            'modify validation pending': 'PARTIALLY_FILLED',
            'after market order req received': 'NEW',
        }
        
        angelone_status = self._safe_str(
            angelone_order.get('orderstatus') or
            angelone_order.get('status')
        ).lower()
        
        binance_status = status_map.get(angelone_status, 'NEW')
        
        # Map transaction type
        side = self._safe_str(
            angelone_order.get('transactiontype') or
            angelone_order.get('side')
        ).upper()
        
        # Map order type
        order_type = self._safe_str(
            angelone_order.get('ordertype') or
            angelone_order.get('type')
        ).upper()
        
        order = BinanceOrder(
            orderId=self._safe_str(
                angelone_order.get('orderid') or
                angelone_order.get('order_id') or
                angelone_order.get('uniqueorderid')
            ),
            symbol=self._safe_str(
                angelone_order.get('tradingsymbol') or
                angelone_order.get('symbol')
            ),
            status=binance_status,
            side=side,
            type=order_type,
            price=self._safe_float(angelone_order.get('price')),
            origQty=self._safe_float(
                angelone_order.get('quantity') or
                angelone_order.get('qty')
            ),
            executedQty=self._safe_float(
                angelone_order.get('filledshares') or
                angelone_order.get('filled_quantity')
            ),
            avgPrice=self._safe_float(
                angelone_order.get('averageprice') or
                angelone_order.get('average_price')
            ),
            time=int(datetime.now().timestamp() * 1000)
        )
        
        return asdict(order)
    
    def convert_position(self, angelone_position: Dict) -> Dict:
        """
        Convert AngelOne position to Binance format
        
        AngelOne format:
        {
            'tradingsymbol': 'RELIANCE-EQ',
            'netqty': 10,
            'avgnetprice': 2500.0,
            'ltp': 2550.0,
            'unrealised': 500.0,
            ...
        }
        """
        quantity = self._safe_float(
            angelone_position.get('netqty') or
            angelone_position.get('quantity') or
            angelone_position.get('buyqty', 0) - angelone_position.get('sellqty', 0)
        )
        
        entry_price = self._safe_float(
            angelone_position.get('avgnetprice') or
            angelone_position.get('averageprice') or
            angelone_position.get('buyavgprice')
        )
        
        current_price = self._safe_float(
            angelone_position.get('ltp') or
            angelone_position.get('lastprice')
        )
        
        unrealized_pnl = self._safe_float(
            angelone_position.get('unrealised') or
            angelone_position.get('pnl')
        )
        
        # Calculate percentage if not provided
        if entry_price > 0 and quantity != 0:
            percentage = ((current_price - entry_price) / entry_price) * 100
        else:
            percentage = 0.0
        
        position = BinancePosition(
            symbol=self._safe_str(
                angelone_position.get('tradingsymbol') or
                angelone_position.get('symbol')
            ),
            positionAmt=quantity,
            entryPrice=entry_price,
            markPrice=current_price,
            unRealizedProfit=unrealized_pnl,
            percentage=percentage
        )
        
        return asdict(position)
    
    def convert_positions(self, angelone_positions: List[Dict]) -> List[Dict]:
        """Convert list of AngelOne positions to Binance format"""
        return [self.convert_position(p) for p in angelone_positions]
    
    def convert_account(self, angelone_account: Dict) -> Dict:
        """
        Convert AngelOne account/margin info to Binance format
        
        AngelOne format:
        {
            'net': 100000.0,
            'availablecash': 50000.0,
            'utiliseddebits': 50000.0,
            ...
        }
        """
        total_balance = self._safe_float(
            angelone_account.get('net') or
            angelone_account.get('total')
        )
        
        available_balance = self._safe_float(
            angelone_account.get('availablecash') or
            angelone_account.get('available') or
            angelone_account.get('cash')
        )
        
        # Calculate unrealized profit from positions if available
        unrealized = self._safe_float(
            angelone_account.get('unrealised') or
            angelone_account.get('m2munrealized')
        )
        
        account = BinanceAccount(
            totalBalance=total_balance,
            availableBalance=available_balance,
            totalUnrealizedProfit=unrealized
        )
        
        return asdict(account)
    
    def convert_websocket_tick(self, angelone_tick: Dict, symbol: str = '') -> Dict:
        """
        Convert AngelOne WebSocket tick to Binance format
        
        AngelOne WebSocket format:
        {
            'token': '2885',
            'ltp': 2500.0,
            'open': 2480.0,
            'high': 2520.0,
            'low': 2470.0,
            'close': 2490.0,
            'volume': 1000000,
            ...
        }
        """
        return {
            'symbol': symbol or self._safe_str(angelone_tick.get('symbol')),
            'price': self._safe_float(angelone_tick.get('ltp')),
            'open': self._safe_float(angelone_tick.get('open')),
            'high': self._safe_float(angelone_tick.get('high')),
            'low': self._safe_float(angelone_tick.get('low')),
            'close': self._safe_float(angelone_tick.get('close')),
            'volume': self._safe_float(angelone_tick.get('volume')),
            'time': int(datetime.now().timestamp() * 1000)
        }
    
    def convert_orders(self, angelone_orders: List[Dict]) -> List[Dict]:
        """Convert list of AngelOne orders to Binance format"""
        return [self.convert_order_response(o) for o in angelone_orders]
    
    def convert_trade(self, angelone_trade: Dict) -> Dict:
        """
        Convert AngelOne trade to Binance format
        
        AngelOne trade format:
        {
            'tradeid': '123456',
            'orderid': '789012',
            'tradingsymbol': 'RELIANCE-EQ',
            'transactiontype': 'BUY',
            'quantity': 10,
            'price': 2500.0,
            'exchange': 'NSE',
            ...
        }
        """
        return {
            'tradeId': self._safe_str(
                angelone_trade.get('tradeid') or
                angelone_trade.get('trade_id')
            ),
            'orderId': self._safe_str(
                angelone_trade.get('orderid') or
                angelone_trade.get('order_id')
            ),
            'symbol': self._safe_str(
                angelone_trade.get('tradingsymbol') or
                angelone_trade.get('symbol')
            ),
            'side': self._safe_str(
                angelone_trade.get('transactiontype') or
                angelone_trade.get('side')
            ).upper(),
            'price': self._safe_float(
                angelone_trade.get('price') or
                angelone_trade.get('fillprice')
            ),
            'qty': self._safe_float(
                angelone_trade.get('quantity') or
                angelone_trade.get('fillsize')
            ),
            'commission': self._safe_float(angelone_trade.get('brokerage', 0)),
            'time': int(datetime.now().timestamp() * 1000)
        }
    
    def convert_trades(self, angelone_trades: List[Dict]) -> List[Dict]:
        """Convert list of AngelOne trades to Binance format"""
        return [self.convert_trade(t) for t in angelone_trades]
    
    def validate_candle(self, candle: Dict) -> bool:
        """Validate that candle has all required fields"""
        required_fields = ['open_time', 'open', 'high', 'low', 'close', 'volume']
        return all(field in candle for field in required_fields)
    
    def validate_order(self, order: Dict) -> bool:
        """Validate that order has all required fields"""
        required_fields = ['orderId', 'symbol', 'status', 'side']
        return all(field in order for field in required_fields)
    
    def validate_position(self, position: Dict) -> bool:
        """Validate that position has all required fields"""
        required_fields = ['symbol', 'positionAmt', 'entryPrice', 'markPrice']
        return all(field in position for field in required_fields)
