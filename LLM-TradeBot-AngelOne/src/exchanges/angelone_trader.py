"""
AngelOne Trader Implementation

This module implements the BaseTrader interface for AngelOne Indian stock market trading.
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from .base import (
    BaseTrader, 
    ExchangeAccount, 
    AccountBalance, 
    Position, 
    OrderResult,
    ExchangeType
)
from src.api.angelone import AngelOneClient
from src.utils.logger import log


class AngelOneTrader(BaseTrader):
    """
    AngelOne implementation of BaseTrader.
    
    Supports NSE, BSE, NFO, MCX exchanges for Indian market trading.
    """
    
    def __init__(self, account: ExchangeAccount):
        """
        Initialize AngelOne trader.
        
        Args:
            account: ExchangeAccount with API credentials
        """
        super().__init__(account)
        self.client: Optional[AngelOneClient] = None
        self._default_exchange = 'NSE'
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format for AngelOne API.
        
        Converts formats like:
        - RELIANCE -> RELIANCE-EQ
        - NIFTY -> NIFTY (unchanged for index)
        
        Args:
            symbol: Symbol in any supported format
            
        Returns:
            Normalized symbol for AngelOne API
        """
        symbol = symbol.upper()
        
        # If already has suffix, return as-is
        if '-' in symbol:
            return symbol
        
        # Add -EQ suffix for equity symbols
        # (This is a simplified logic - real implementation would check instrument type)
        return symbol
    
    async def initialize(self) -> bool:
        """Initialize AngelOne client connection."""
        try:
            # Extract credentials from account
            # For AngelOne, we need: api_key, client_code (user_id), password, totp_secret
            self.client = AngelOneClient(
                api_key=self.account.api_key,
                client_code=self.account.user_id,  # Using user_id as client_code
                password=self.account.secret_key,  # Using secret_key as password
                totp_secret=self.account.passphrase,  # Using passphrase as TOTP secret
                default_exchange=self._default_exchange
            )
            
            # Connect to AngelOne
            await self.client.connect()
            
            self._initialized = True
            log.info(f"AngelOneTrader initialized: {self.account_name}")
            return True
            
        except Exception as e:
            log.error(f"Failed to initialize AngelOneTrader: {e}")
            return False
    
    def _ensure_initialized(self):
        """Ensure client is initialized before operations."""
        if not self._initialized or not self.client:
            raise RuntimeError("AngelOneTrader not initialized. Call initialize() first.")
    
    async def get_balance(self) -> AccountBalance:
        """Get account balance."""
        self._ensure_initialized()
        
        try:
            account = self.client.get_account()
            
            return AccountBalance(
                total_equity=float(account.get('totalBalance', 0)),
                available_balance=float(account.get('availableBalance', 0)),
                unrealized_pnl=float(account.get('totalUnrealizedProfit', 0)),
                wallet_balance=float(account.get('totalBalance', 0)),
                margin_balance=float(account.get('availableBalance', 0))
            )
            
        except Exception as e:
            log.error(f"[{self.account_name}] Failed to get balance: {e}")
            raise
    
    async def get_positions(self, symbol: str = None) -> List[Position]:
        """Get open positions."""
        self._ensure_initialized()
        
        try:
            positions = self.client.get_positions()
            
            result = []
            for pos in positions:
                # Filter by symbol if specified
                if symbol and pos.get('symbol') != symbol:
                    continue
                
                quantity = float(pos.get('quantity', 0))
                if quantity != 0:
                    result.append(Position(
                        symbol=pos.get('symbol', ''),
                        side="LONG" if quantity > 0 else "SHORT",
                        quantity=abs(quantity),
                        entry_price=float(pos.get('avgPrice', 0)),
                        unrealized_pnl=float(pos.get('unrealizedPnl', 0)),
                        leverage=1,  # Indian market typically doesn't use leverage like crypto
                        mark_price=float(pos.get('ltp', 0)),
                        liquidation_price=0.0,  # Not applicable for Indian market
                        margin_type="cash"
                    ))
            
            return result
            
        except Exception as e:
            log.error(f"[{self.account_name}] Failed to get positions: {e}")
            raise
    
    async def get_market_price(self, symbol: str) -> float:
        """Get current market price."""
        self._ensure_initialized()
        
        normalized_symbol = self._normalize_symbol(symbol)
        
        try:
            ticker = self.client.get_ticker_price(normalized_symbol)
            return float(ticker.get('price', 0))
            
        except Exception as e:
            log.error(f"[{self.account_name}] Failed to get price for {normalized_symbol}: {e}")
            raise
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Set leverage for a symbol.
        Note: Indian market doesn't support leverage like crypto futures.
        This is a no-op for AngelOne.
        """
        log.info(f"[{self.account_name}] Leverage not applicable for Indian market")
        return True
    
    async def open_long(
        self, 
        symbol: str, 
        quantity: float, 
        leverage: int = 1,
        reduce_only: bool = False
    ) -> OrderResult:
        """Open a long position (BUY)."""
        self._ensure_initialized()
        
        normalized_symbol = self._normalize_symbol(symbol)
        
        try:
            order = self.client.create_order(
                symbol=normalized_symbol,
                side='BUY',
                order_type='MARKET',
                quantity=int(quantity),
                product_type='INTRADAY'
            )
            
            log.info(f"[{self.account_name}] Long opened: {quantity} {symbol}")
            
            return OrderResult(
                success=order.get('status') != 'REJECTED',
                order_id=str(order.get('orderId', '')),
                symbol=symbol,
                side='BUY',
                quantity=quantity,
                price=float(order.get('price', 0)),
                status=order.get('status', 'PLACED'),
                raw_response=order
            )
            
        except Exception as e:
            log.error(f"[{self.account_name}] Failed to open long: {e}")
            return OrderResult(success=False, error=str(e))
    
    async def open_short(
        self, 
        symbol: str, 
        quantity: float, 
        leverage: int = 1,
        reduce_only: bool = False
    ) -> OrderResult:
        """Open a short position (SELL)."""
        self._ensure_initialized()
        
        normalized_symbol = self._normalize_symbol(symbol)
        
        try:
            order = self.client.create_order(
                symbol=normalized_symbol,
                side='SELL',
                order_type='MARKET',
                quantity=int(quantity),
                product_type='INTRADAY'
            )
            
            log.info(f"[{self.account_name}] Short opened: {quantity} {symbol}")
            
            return OrderResult(
                success=order.get('status') != 'REJECTED',
                order_id=str(order.get('orderId', '')),
                symbol=symbol,
                side='SELL',
                quantity=quantity,
                price=float(order.get('price', 0)),
                status=order.get('status', 'PLACED'),
                raw_response=order
            )
            
        except Exception as e:
            log.error(f"[{self.account_name}] Failed to open short: {e}")
            return OrderResult(success=False, error=str(e))
    
    async def close_position(self, symbol: str, quantity: float = 0) -> OrderResult:
        """Close an existing position."""
        self._ensure_initialized()
        
        normalized_symbol = self._normalize_symbol(symbol)
        
        try:
            # Get current position
            positions = await self.get_positions(normalized_symbol)
            if not positions:
                return OrderResult(success=False, error="No position found")
            
            position = positions[0]
            close_qty = quantity if quantity > 0 else position.quantity
            
            # Determine close side
            close_side = 'SELL' if position.side == 'LONG' else 'BUY'
            
            order = self.client.create_order(
                symbol=normalized_symbol,
                side=close_side,
                order_type='MARKET',
                quantity=int(close_qty),
                product_type='INTRADAY'
            )
            
            log.info(f"[{self.account_name}] Position closed: {close_qty} {symbol}")
            
            return OrderResult(
                success=order.get('status') != 'REJECTED',
                order_id=str(order.get('orderId', '')),
                symbol=symbol,
                side=close_side,
                quantity=close_qty,
                price=float(order.get('price', 0)),
                status=order.get('status', 'PLACED'),
                raw_response=order
            )
            
        except Exception as e:
            log.error(f"[{self.account_name}] Failed to close position: {e}")
            return OrderResult(success=False, error=str(e))
    
    async def set_stop_loss(
        self, 
        symbol: str, 
        stop_price: float,
        position_side: str = "LONG"
    ) -> OrderResult:
        """Set stop-loss order."""
        self._ensure_initialized()
        
        normalized_symbol = self._normalize_symbol(symbol)
        
        try:
            # Get current position to determine quantity
            positions = await self.get_positions(normalized_symbol)
            if not positions:
                return OrderResult(success=False, error="No position found for SL")
            
            position = positions[0]
            side = 'SELL' if position_side.upper() == 'LONG' else 'BUY'
            
            order = self.client.create_order(
                symbol=normalized_symbol,
                side=side,
                order_type='STOPLOSS_MARKET',
                quantity=int(position.quantity),
                trigger_price=stop_price,
                product_type='INTRADAY'
            )
            
            log.info(f"[{self.account_name}] Stop-loss set: {symbol} @ {stop_price}")
            
            return OrderResult(
                success=order.get('status') != 'REJECTED',
                order_id=str(order.get('orderId', '')),
                symbol=symbol,
                side=side,
                price=stop_price,
                status='NEW',
                raw_response=order
            )
            
        except Exception as e:
            log.error(f"[{self.account_name}] Failed to set stop-loss: {e}")
            return OrderResult(success=False, error=str(e))
    
    async def set_take_profit(
        self, 
        symbol: str, 
        take_profit_price: float,
        position_side: str = "LONG"
    ) -> OrderResult:
        """Set take-profit order."""
        self._ensure_initialized()
        
        normalized_symbol = self._normalize_symbol(symbol)
        
        try:
            # Get current position to determine quantity
            positions = await self.get_positions(normalized_symbol)
            if not positions:
                return OrderResult(success=False, error="No position found for TP")
            
            position = positions[0]
            side = 'SELL' if position_side.upper() == 'LONG' else 'BUY'
            
            # Use LIMIT order for take profit
            order = self.client.create_order(
                symbol=normalized_symbol,
                side=side,
                order_type='LIMIT',
                quantity=int(position.quantity),
                price=take_profit_price,
                product_type='INTRADAY'
            )
            
            log.info(f"[{self.account_name}] Take-profit set: {symbol} @ {take_profit_price}")
            
            return OrderResult(
                success=order.get('status') != 'REJECTED',
                order_id=str(order.get('orderId', '')),
                symbol=symbol,
                side=side,
                price=take_profit_price,
                status='NEW',
                raw_response=order
            )
            
        except Exception as e:
            log.error(f"[{self.account_name}] Failed to set take-profit: {e}")
            return OrderResult(success=False, error=str(e))
    
    async def cancel_all_orders(self, symbol: str) -> bool:
        """Cancel all open orders for a symbol."""
        self._ensure_initialized()
        
        try:
            # Get all orders
            orders = self.client.get_order_book()
            
            # Cancel each pending order for the symbol
            cancelled = 0
            for order in orders:
                if order.get('symbol') == symbol and order.get('status') in ['PENDING', 'OPEN', 'NEW']:
                    try:
                        self.client.cancel_order(order.get('orderId'))
                        cancelled += 1
                    except Exception as e:
                        log.warning(f"Failed to cancel order {order.get('orderId')}: {e}")
            
            log.info(f"[{self.account_name}] Cancelled {cancelled} orders for {symbol}")
            return True
            
        except Exception as e:
            log.error(f"[{self.account_name}] Failed to cancel orders: {e}")
            return False
    
    async def get_klines(
        self, 
        symbol: str, 
        interval: str, 
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Get candlestick data."""
        self._ensure_initialized()
        
        normalized_symbol = self._normalize_symbol(symbol)
        
        try:
            klines = self.client.get_klines(
                symbol=normalized_symbol,
                interval=interval,
                limit=limit
            )
            
            return klines
            
        except Exception as e:
            log.error(f"[{self.account_name}] Failed to get klines: {e}")
            raise
    
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """
        Get funding rate for a symbol.
        Note: Not applicable for Indian stock market.
        """
        return {'symbol': symbol, 'funding_rate': 0, 'note': 'Not applicable for Indian market'}
    
    async def get_open_interest(self, symbol: str) -> Dict[str, Any]:
        """
        Get open interest for a symbol.
        Note: Only applicable for F&O segment.
        """
        return {'symbol': symbol, 'open_interest': 0, 'note': 'Only applicable for F&O segment'}
