"""
Binance API Integration Layer
"""
from typing import Dict, List, Optional, Any
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance import ThreadedWebsocketManager
import asyncio
from datetime import datetime
from src.config import config
from src.utils.logger import log


class BinanceClient:
    """Binance API Client Wrapper"""
    
    def __init__(self):
        self.api_key = config.binance.get('api_key')
        self.api_secret = config.binance.get('api_secret')
        self.testnet = config.binance.get('testnet', True)
        
        # Initialize client
        if self.testnet:
            self.client = Client(
                self.api_key,
                self.api_secret,
                testnet=True
            )
        else:
            self.client = Client(self.api_key, self.api_secret)
        
        self.ws_manager: Optional[ThreadedWebsocketManager] = None
        
        # Cache layer
        self._funding_cache = {} # {symbol: (rate, timestamp)}
        self._cache_duration = 3600 # 1 hour cache
        
        log.info(f"Binance client initialized (testnet: {self.testnet})")
    
    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List[Dict]:
        """
        Get K-line (candlestick) data
        
        Args:
            symbol: Trading pair, e.g., 'BTCUSDT'
            interval: Time interval, e.g., '1m', '5m', '15m', '1h'
            limit: Quantity limit
            
        Returns:
            List of K-line data
        """
        try:
            # Debug log before call
            # log.debug(f"[API] Requesting klines: {symbol} {interval} limit={limit}")
            
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            # Critical debug for Railway issue
            if len(klines) < 10:
                log.warning(f"[API] Low kline count for {symbol} {interval}: requested={limit}, returned={len(klines)}")
            
            # Format data
            formatted_klines = []
            for k in klines:
                formatted_klines.append({
                    'timestamp': k[0],
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5]),
                    'close_time': k[6],
                    'quote_volume': float(k[7]),
                    'trades': int(k[8]),
                    'taker_buy_base': float(k[9]),
                    'taker_buy_quote': float(k[10])
                })
            
            return formatted_klines
            
        except BinanceAPIException as e:
            log.error(f"Failed to get klines: {e}")
            raise
    
    def get_ticker_price(self, symbol: str) -> Dict:
        """Get latest price"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return {
                'symbol': ticker['symbol'],
                'price': float(ticker['price']),
                'timestamp': datetime.now().timestamp() * 1000
            }
        except BinanceAPIException as e:
            log.error(f"Failed to get price: {e}")
            raise

    def get_all_tickers(self) -> List[Dict]:
        """
        Get 24hr statistics for all trading pairs (for volume ranking)
        Return List of dictionary:
        {
            'symbol': 'BTCUSDT',
            'priceChange': '-94.99999800',
            'priceChangePercent': '-95.960',
            'weightedAvgPrice': '0.29628482',
            'prevClosePrice': '0.10002000',
            'lastPrice': '4.00000200',
            'lastQty': '200.00000000',
            'bidPrice': '4.00000000',
            'askPrice': '4.00000200',
            'openPrice': '99.00000000',
            'highPrice': '100.00000000',
            'lowPrice': '0.10000000',
            'volume': '8913.30000000', 
            'quoteVolume': '15.30000000', ...
        }
        """
        try:
            # get_ticker without symbol returns all tickers
            tickers = self.client.get_ticker() 
            return tickers
        except BinanceAPIException as e:
            log.error(f"Failed to get all tickers: {e}")
            return []
    
    def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Get order book"""
        try:
            depth = self.client.get_order_book(symbol=symbol, limit=limit)
            return {
                'timestamp': datetime.now().timestamp() * 1000,
                'bids': [[float(p), float(q)] for p, q in depth['bids']],
                'asks': [[float(p), float(q)] for p, q in depth['asks']]
            }
        except BinanceAPIException as e:
            log.error(f"Failed to get order book: {e}")
            raise
    
    def get_account_info(self) -> Dict:
        """Get account information"""
        try:
            account = self.client.get_account()
            
            # Extract USDT balance
            usdt_balance = 0
            for balance in account['balances']:
                if balance['asset'] == 'USDT':
                    usdt_balance = float(balance['free']) + float(balance['locked'])
                    break
            
            return {
                'timestamp': account['updateTime'],
                'can_trade': account['canTrade'],
                'balances': account['balances'],
                'usdt_balance': usdt_balance
            }
        except BinanceAPIException as e:
            log.error(f"Failed to get account info: {e}")
            raise
    
    def get_futures_account(self) -> Dict:
        """Get futures account information"""
        try:
            account = self.client.futures_account()
            
            return {
                'timestamp': account['updateTime'],
                'total_wallet_balance': float(account['totalWalletBalance']),
                'total_unrealized_profit': float(account['totalUnrealizedProfit']),
                'total_margin_balance': float(account['totalMarginBalance']),
                'available_balance': float(account['availableBalance']),
                'max_withdraw_amount': float(account['maxWithdrawAmount']),
                'positions': account['positions']
            }
        except BinanceAPIException as e:
            log.error(f"Failed to get futures account: {e}")
            raise
    
    def get_futures_position(self, symbol: str) -> Optional[Dict]:
        """Get position information for a specific futures contract"""
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            
            if not positions:
                return None
            
            pos = positions[0]
            return {
                'symbol': pos['symbol'],
                'position_amt': float(pos['positionAmt']),
                'entry_price': float(pos['entryPrice']),
                'mark_price': float(pos['markPrice']),
                'unrealized_profit': float(pos['unRealizedProfit']),
                'liquidation_price': float(pos['liquidationPrice']),
                'leverage': int(pos['leverage']),
                'margin_type': pos['marginType'],
                'isolated_margin': float(pos['isolatedMargin']),
                'position_side': pos['positionSide']
            }
        except BinanceAPIException as e:
            log.error(f"Failed to get positions: {e}")
            raise
    
    def get_account_balance(self) -> float:
        """
        Get available balance for futures account
        
        Returns:
            float: Available balance (USDT)
        """
        try:
            account = self.get_futures_account()
            return account['available_balance']
        except BinanceAPIException as e:
            log.error(f"Failed to get account balance: {e}")
            raise
    
    def get_funding_rate(self, symbol: str) -> Dict:
        """Get funding rate (real-time - Premium Index)"""
        try:
            # User specified to use premiumIndex endpoint (futures_mark_price)
            funding = self.client.futures_mark_price(symbol=symbol)
            
            return {
                'symbol': funding['symbol'],
                'funding_rate': float(funding['lastFundingRate']),
                'funding_time': funding['nextFundingTime']
            }
        except BinanceAPIException as e:
            log.error(f"Failed to get funding rate: {e}")
            raise

    def get_funding_rate_with_cache(self, symbol: str) -> Dict:
        """Get funding rate with 1-hour cache"""
        now = datetime.now().timestamp()
        
        # Check cache
        if symbol in self._funding_cache:
            rate, ts = self._funding_cache[symbol]
            if now - ts < self._cache_duration:
                log.debug(f"Using cached funding rate: {symbol}")
                return {
                    'symbol': symbol,
                    'funding_rate': rate,
                    'is_cached': True
                }
        
        # Cache expired or doesn't exist, fetch new value
        try:
            data = self.get_funding_rate(symbol)
            self._funding_cache[symbol] = (data['funding_rate'], now)
            data['is_cached'] = False
            return data
        except Exception as e:
            log.error(f"Failed to refresh funding rate cache: {e}")
            # If old cache exists, return it as fallback
            if symbol in self._funding_cache:
                return {'symbol': symbol, 'funding_rate': self._funding_cache[symbol][0], 'is_cached': True, 'error': 'refresh_failed'}
            return {'symbol': symbol, 'funding_rate': 0, 'is_cached': False, 'error': str(e)}
    
    def get_open_interest(self, symbol: str) -> Dict:
        """Get open interest"""
        try:
            oi = self.client.futures_open_interest(symbol=symbol)
            return {
                'symbol': oi['symbol'],
                'open_interest': float(oi['openInterest']),
                'timestamp': oi['time']
            }
        except BinanceAPIException as e:
            log.error(f"Failed to get open interest: {e}")
            raise
    
    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool = False,
        position_side: str = 'BOTH'
    ) -> Dict:
        """
        Place market order
        
        Args:
            symbol: Trading pair
            side: BUY or SELL
            quantity: Quantity
            reduce_only: Reduce only
            position_side: Position side (BOTH/LONG/SHORT), use LONG/SHORT for hedge mode
        """
        try:
            # Build order parameters
            order_params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity,
                'positionSide': position_side
            }
            
            # Only add reduceOnly parameter when needed
            if reduce_only:
                order_params['reduceOnly'] = True
            
            order = self.client.futures_create_order(**order_params)
            
            log.info(f"Market order placed: {side} {quantity} {symbol} (positionSide={position_side})")
            return order
            
        except BinanceAPIException as e:
            log.error(f"Order failed: {e}")
            raise
    
    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        time_in_force: str = 'GTC'
    ) -> Dict:
        """Place limit order"""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='LIMIT',
                quantity=quantity,
                price=price,
                timeInForce=time_in_force
            )
            
            log.info(f"Limit order placed: {side} {quantity} {symbol} @ {price}")
            return order
            
        except BinanceAPIException as e:
            log.error(f"Order failed: {e}")
            raise
    
    def set_stop_loss_take_profit(
        self,
        symbol: str,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        position_side: str = 'LONG'  # New: explicitly specify position side
    ) -> List[Dict]:
        """
        Set stop loss and take profit
        
        Args:
            symbol: Trading pair
            stop_loss_price: Stop loss price
            take_profit_price: Take profit price
            position_side: Position side (LONG/SHORT)
        """
        orders = []
        
        try:
            # Get current position
            position = self.get_futures_position(symbol)
            if not position or position['position_amt'] == 0:
                log.warning("No position, cannot set SL/TP")
                return orders
            
            position_amt = abs(position['position_amt'])
            side = 'SELL' if position['position_amt'] > 0 else 'BUY'
            
            # Stop loss order
            if stop_loss_price:
                sl_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='STOP_MARKET',
                    stopPrice=stop_loss_price,
                    closePosition=True,
                    positionSide=position_side  # Add position side
                )
                orders.append(sl_order)
                log.info(f"Stop loss set: {stop_loss_price} (positionSide={position_side})")
            
            # Take profit order
            if take_profit_price:
                tp_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='TAKE_PROFIT_MARKET',
                    stopPrice=take_profit_price,
                    closePosition=True,
                    positionSide=position_side  # Add position side
                )
                orders.append(tp_order)
                log.info(f"Take profit set: {take_profit_price} (positionSide={position_side})")
            
            return orders
            
        except BinanceAPIException as e:
            log.error(f"Failed to set SL/TP: {e}")
            raise
    
    def cancel_all_orders(self, symbol: str) -> Dict:
        """Cancel all orders"""
        try:
            result = self.client.futures_cancel_all_open_orders(symbol=symbol)
            log.info(f"Cancelled all {symbol} orders")
            return result
        except BinanceAPIException as e:
            log.error(f"Failed to cancel orders: {e}")
            raise
    
    def get_market_data_snapshot(self, symbol: str) -> Dict:
        """
        Get complete market data snapshot
        This is the standard interface for downstream modules
        
        Note: Account info retrieval failure will be noted in return, won't raise exception
        """
        try:
            price = self.get_ticker_price(symbol)
            orderbook = self.get_orderbook(symbol)
            funding = self.get_funding_rate(symbol)
            oi = self.get_open_interest(symbol)
            
            # Futures account info (requires authentication, returns empty if failed)
            account = None
            position = None
            account_error = None
            
            try:
                account = self.get_futures_account()
                position = self.get_futures_position(symbol)
            except Exception as e:
                account_error = str(e)
                log.warning(f"Failed to get account/position info (API key may not be configured): {e}")
            
            return {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'price': price,
                'orderbook': orderbook,
                'funding': funding,
                'oi': oi,
                'account': account,
                'position': position,
                'account_error': account_error  # Pass error information
            }
            
        except Exception as e:
            log.error(f"Failed to get market snapshot: {e}")
            raise
    
    def get_symbol_info(self, symbol: str) -> Dict:
        """Get trading pair info (including filters)"""
        try:
            info = self.client.get_symbol_info(symbol)
            return info or {}
        except BinanceAPIException as e:
            log.error(f"Failed to get symbol info: {e}")
            raise
    
    def get_symbol_min_notional(self, symbol: str) -> float:
        """Try to parse minimum notional from trading pair info (minNotional or MIN_NOTIONAL)

        Returns float (returns 0.0 if not found)
        """
        try:
            info = self.get_symbol_info(symbol)
            filters = info.get('filters', []) if isinstance(info, dict) else []

            # Common filter fields: {'filterType': 'MIN_NOTIONAL', 'minNotional': '100'}
            for f in filters:
                if not isinstance(f, dict):
                    continue
                ft = f.get('filterType')
                if ft == 'MIN_NOTIONAL':
                    try:
                        return float(f.get('minNotional', 0))
                    except Exception:
                        continue

                # Some endpoints return minNotional field directly
                if 'minNotional' in f:
                    try:
                        return float(f.get('minNotional', 0))
                    except Exception:
                        continue

            # Compatibility fallback: some contracts may use different naming
            for f in filters:
                if not isinstance(f, dict):
                    continue
                for k in ['minNotional', 'minNotionalValue', 'minNotionalAmt', 'NOTIONAL', 'minNotionalUSD']:
                    if k in f:
                        try:
                            return float(f.get(k, 0))
                        except Exception:
                            continue

            return 0.0
        except Exception as e:
            log.warning(f"Failed to parse min notional, returning 0: {e}")
            return 0.0
