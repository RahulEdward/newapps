"""
Execution Commander (The Executor) Module

Updated for AngelOne Indian Stock Market Integration
"""
from typing import Dict, Optional, List, Union
from src.api.angelone import AngelOneClient
# Legacy Binance client for backward compatibility
try:
    from src.api.binance_client import BinanceClient
except ImportError:
    BinanceClient = None
from src.risk.manager import RiskManager
from src.utils.logger import log
from datetime import datetime
import time


class ExecutionEngine:
    """
    Execution Commander (The Executor)
    
    Supports both AngelOne (Indian market) and Binance (crypto)
    """
    
    def __init__(
        self, 
        client: Union[AngelOneClient, 'BinanceClient'], 
        risk_manager: RiskManager
    ):
        self.client = client
        self.risk_manager = risk_manager
        
        # Detect client type
        self._is_angelone = isinstance(client, AngelOneClient)
        
        log.info("🚀 The Executor (Execution Engine) initialized")
    
    def execute_decision(
        self,
        decision: Dict,
        account_info: Dict,
        position_info: Optional[Dict],
        current_price: float
    ) -> Dict:
        """
        Execute trading decision
        
        Args:
            decision: Risk-validated decision
            account_info: Account information
            position_info: Position information
            current_price: Current price
            
        Returns:
            Execution result
        """
        
        action = decision['action']
        symbol = decision['symbol']
        
        result = {
            'success': False,
            'action': action,
            'timestamp': datetime.now().isoformat(),
            'orders': [],
            'message': ''
        }
        
        try:
            if action == 'hold':
                result['success'] = True
                result['message'] = 'Hold - no action taken'
                log.info("Executing hold, no operation")
                return result
            
            elif action == 'open_long':
                return self._open_long(decision, account_info, current_price)
            
            elif action == 'open_short':
                return self._open_short(decision, account_info, current_price)
            
            elif action == 'close_position':
                return self._close_position(decision, position_info)
            
            elif action == 'add_position':
                return self._add_position(decision, account_info, position_info, current_price)
            
            elif action == 'reduce_position':
                return self._reduce_position(decision, position_info)
            
            else:
                result['message'] = f'Unknown action: {action}'
                log.error(result['message'])
                return result
                
        except Exception as e:
            log.error(f"Trade execution failed: {e}")
            result['message'] = f'Execution failed: {str(e)}'
            return result
    
    def _open_long(self, decision: Dict, account_info: Dict, current_price: float) -> Dict:
        """Open long position"""
        symbol = decision['symbol']
        
        # Calculate position size
        quantity = self.risk_manager.calculate_position_size(
            account_balance=account_info['available_balance'],
            position_pct=decision['position_size_pct'],
            leverage=decision['leverage'],
            current_price=current_price
        )
        
        if self._is_angelone:
            # AngelOne: Use create_order
            # Determine product type based on decision
            product_type = decision.get('product_type', 'INTRADAY')
            
            order = self.client.create_order(
                symbol=symbol,
                side='BUY',
                order_type='MARKET',
                quantity=int(quantity),  # AngelOne requires integer quantity
                product_type=product_type
            )
            
            entry_price = current_price  # Market order, use current price
            
            # AngelOne doesn't have native SL/TP like Binance futures
            # Would need to place separate SL orders
            sl_tp_orders = []
            
            stop_loss_price = self.risk_manager.calculate_stop_loss_price(
                entry_price=entry_price,
                stop_loss_pct=decision['stop_loss_pct'],
                side='LONG'
            )
            
            take_profit_price = self.risk_manager.calculate_take_profit_price(
                entry_price=entry_price,
                take_profit_pct=decision['take_profit_pct'],
                side='LONG'
            )
            
            log.executor(f"Long opened: {quantity} {symbol} @ {entry_price}")
            
        else:
            # Binance: Original logic
            # Set leverage
            try:
                self.client.client.futures_change_leverage(
                    symbol=symbol,
                    leverage=decision['leverage']
                )
                log.executor(f"Leverage set to {decision['leverage']}x")
            except Exception as e:
                log.executor(f"Failed to set leverage: {e}", success=False)
            
            # Place market buy order (open long)
            order = self.client.place_market_order(
                symbol=symbol,
                side='BUY',
                quantity=quantity,
                position_side='LONG'
            )
            
            # Calculate stop loss and take profit prices
            entry_price = float(order.get('avgPrice', current_price))
            
            stop_loss_price = self.risk_manager.calculate_stop_loss_price(
                entry_price=entry_price,
                stop_loss_pct=decision['stop_loss_pct'],
                side='LONG'
            )
            
            take_profit_price = self.risk_manager.calculate_take_profit_price(
                entry_price=entry_price,
                take_profit_pct=decision['take_profit_pct'],
                side='LONG'
            )
            
            # Set stop loss and take profit
            sl_tp_orders = self.client.set_stop_loss_take_profit(
                symbol=symbol,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                position_side='LONG'
            )
            
            log.executor(f"Long opened: {quantity} {symbol} @ {entry_price}")
        
        return {
            'success': True,
            'action': 'open_long',
            'timestamp': datetime.now().isoformat(),
            'orders': [order] + sl_tp_orders,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss_price,
            'take_profit': take_profit_price,
            'message': 'Long position opened successfully'
        }
    
    def _open_short(self, decision: Dict, account_info: Dict, current_price: float) -> Dict:
        """Open short position"""
        symbol = decision['symbol']
        
        quantity = self.risk_manager.calculate_position_size(
            account_balance=account_info['available_balance'],
            position_pct=decision['position_size_pct'],
            leverage=decision['leverage'],
            current_price=current_price
        )
        
        if self._is_angelone:
            # AngelOne: Use create_order for SELL
            # Note: Short selling in Indian market requires margin/F&O
            product_type = decision.get('product_type', 'INTRADAY')
            
            order = self.client.create_order(
                symbol=symbol,
                side='SELL',
                order_type='MARKET',
                quantity=int(quantity),
                product_type=product_type
            )
            
            entry_price = current_price
            sl_tp_orders = []
            
            stop_loss_price = self.risk_manager.calculate_stop_loss_price(
                entry_price=entry_price,
                stop_loss_pct=decision['stop_loss_pct'],
                side='SHORT'
            )
            
            take_profit_price = self.risk_manager.calculate_take_profit_price(
                entry_price=entry_price,
                take_profit_pct=decision['take_profit_pct'],
                side='SHORT'
            )
            
            log.executor(f"Short opened: {quantity} {symbol} @ {entry_price}")
            
        else:
            # Binance: Original logic
            # Set leverage
            try:
                self.client.client.futures_change_leverage(
                    symbol=symbol,
                    leverage=decision['leverage']
                )
            except Exception as e:
                log.executor(f"Failed to set leverage: {e}", success=False)
            
            # Place market sell order (open short)
            order = self.client.place_market_order(
                symbol=symbol,
                side='SELL',
                quantity=quantity,
                position_side='SHORT'
            )
            
            entry_price = float(order.get('avgPrice', current_price))
            
            stop_loss_price = self.risk_manager.calculate_stop_loss_price(
                entry_price=entry_price,
                stop_loss_pct=decision['stop_loss_pct'],
                side='SHORT'
            )
            
            take_profit_price = self.risk_manager.calculate_take_profit_price(
                entry_price=entry_price,
                take_profit_pct=decision['take_profit_pct'],
                side='SHORT'
            )
            
            sl_tp_orders = self.client.set_stop_loss_take_profit(
                symbol=symbol,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                position_side='SHORT'
            )
            
            log.executor(f"Short opened: {quantity} {symbol} @ {entry_price}")
        
        return {
            'success': True,
            'action': 'open_short',
            'timestamp': datetime.now().isoformat(),
            'orders': [order] + sl_tp_orders,
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss_price,
            'take_profit': take_profit_price,
            'message': 'Short position opened successfully'
        }
    
    def _close_position(self, decision: Dict, position_info: Optional[Dict]) -> Dict:
        """Close position"""
        if not position_info or position_info.get('position_amt', 0) == 0:
            return {
                'success': False,
                'action': 'close_position',
                'timestamp': datetime.now().isoformat(),
                'message': 'No position to close'
            }
        
        symbol = decision['symbol']
        position_amt = position_info['position_amt']
        
        if self._is_angelone:
            # AngelOne: Close by placing opposite order
            side = 'SELL' if position_amt > 0 else 'BUY'
            quantity = abs(position_amt)
            
            log.executor(f"Closing position: {side} {quantity} {symbol}")
            
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=int(quantity),
                product_type='INTRADAY'  # Or get from position info
            )
            
            log.executor(f"Position closed: {quantity} {symbol}")
            
        else:
            # Binance: Original logic
            # Cancel all pending orders
            self.client.cancel_all_orders(symbol)
            
            # Close position
            side = 'SELL' if position_amt > 0 else 'BUY'
            quantity = abs(position_amt)
            
            log.executor(f"Closing position: {side} {quantity} {symbol}")
            
            order = self.client.place_market_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                reduce_only=True
            )
            
            log.executor(f"Position closed: {quantity} {symbol}")
        
        return {
            'success': True,
            'action': 'close_position',
            'timestamp': datetime.now().isoformat(),
            'orders': [order],
            'quantity': quantity,
            'message': 'Position closed successfully'
        }
    
    def _add_position(
        self,
        decision: Dict,
        account_info: Dict,
        position_info: Optional[Dict],
        current_price: float
    ) -> Dict:
        """Add to position"""
        if not position_info or position_info.get('position_amt', 0) == 0:
            return {
                'success': False,
                'action': 'add_position',
                'timestamp': datetime.now().isoformat(),
                'message': 'No position to add to'
            }
        
        # Determine if current position is long or short
        if position_info['position_amt'] > 0:
            return self._open_long(decision, account_info, current_price)
        else:
            return self._open_short(decision, account_info, current_price)
    
    def _reduce_position(self, decision: Dict, position_info: Optional[Dict]) -> Dict:
        """Reduce position"""
        if not position_info or position_info.get('position_amt', 0) == 0:
            return {
                'success': False,
                'action': 'reduce_position',
                'timestamp': datetime.now().isoformat(),
                'message': 'No position to reduce'
            }
        
        symbol = decision['symbol']
        position_amt = position_info['position_amt']
        
        # Reduce by half
        reduce_qty = abs(position_amt) * 0.5
        side = 'SELL' if position_amt > 0 else 'BUY'
        
        if self._is_angelone:
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=int(reduce_qty),
                product_type='INTRADAY'
            )
        else:
            order = self.client.place_market_order(
                symbol=symbol,
                side=side,
                quantity=reduce_qty,
                reduce_only=True
            )
        
        log.executor(f"Position reduced: {reduce_qty} {symbol}")
        
        return {
            'success': True,
            'action': 'reduce_position',
            'timestamp': datetime.now().isoformat(),
            'orders': [order],
            'quantity': reduce_qty,
            'message': 'Position reduced successfully'
        }
