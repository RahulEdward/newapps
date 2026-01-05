"""
Backtest Engine Core
================================

Coordinates data replay, strategy execution, and performance evaluation

Author: AI Trader Team
Date: 2025-12-31
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
import pandas as pd

from src.backtest.data_replay import DataReplayAgent
from src.backtest.portfolio import BacktestPortfolio, Side, Trade
from src.backtest.metrics import PerformanceMetrics, MetricsResult
from src.backtest.report import BacktestReport
from src.utils.logger import log


@dataclass
class BacktestConfig:
    """Backtest Configuration"""
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = 10000.0
    max_position_size: float = 1000000.0
    leverage: int = 1
    stop_loss_pct: float = 1.0
    take_profit_pct: float = 2.0
    slippage: float = 0.001
    commission: float = 0.0004
    step: int = 1  # 1=every 5 minutes, 3=every 15 minutes, 12=every hour
    margin_mode: str = "cross"  # "cross" or "isolated"
    contract_type: str = "linear"  # "linear" or "inverse"
    contract_size: float = 100.0  # Contract face value (BTC=100 USD)
    strategy_mode: str = "agent"  # "technical" (EMA) or "agent" (Multi-Agent)
    use_llm: bool = False  # Whether to call LLM in backtest (expensive, slow)
    llm_cache: bool = True  # Cache LLM responses
    llm_throttle_ms: int = 100  # LLM call interval (ms) to avoid rate limits
    
    # Indian Market Settings (AngelOne)
    market: str = "crypto"  # "crypto" (Binance) or "indian" (AngelOne)
    exchange: str = "NSE"  # NSE, BSE, NFO, MCX (for Indian market)
    product_type: str = "INTRADAY"  # INTRADAY, DELIVERY, CARRYFORWARD
    
    # Indian Market Charges (as percentage)
    stt_pct: float = 0.025  # Securities Transaction Tax (0.025% for intraday)
    stamp_duty_pct: float = 0.003  # Stamp Duty (0.003%)
    exchange_charges_pct: float = 0.00325  # Exchange charges (0.00325%)
    sebi_charges_pct: float = 0.0001  # SEBI charges (0.0001%)
    gst_pct: float = 18.0  # GST on brokerage (18%)
    
    def __post_init__(self):
        """Validate configuration parameters"""
        from datetime import datetime
        
        # Validate date format
        try:
            # Try full datetime format first
            try:
                start = datetime.strptime(self.start_date, '%Y-%m-%d %H:%M')
            except ValueError:
                # Fallback to date only
                start = datetime.strptime(self.start_date, '%Y-%m-%d')
            
            try:
                end = datetime.strptime(self.end_date, '%Y-%m-%d %H:%M')
            except ValueError:
                # Fallback to date only
                end = datetime.strptime(self.end_date, '%Y-%m-%d')
                
            if start >= end:
                raise ValueError(f"start_date ({self.start_date}) must be before end_date ({self.end_date})")
        except ValueError as e:
            if "does not match format" in str(e):
                raise ValueError(f"Invalid date format. Expected YYYY-MM-DD or YYYY-MM-DD HH:MM, got start_date={self.start_date}, end_date={self.end_date}")
            raise
        
        # Validate numeric ranges
        if self.initial_capital <= 0:
            raise ValueError(f"initial_capital must be positive, got {self.initial_capital}")
        
        if self.max_position_size <= 0:
            raise ValueError(f"max_position_size must be positive, got {self.max_position_size}")
        
        if self.leverage < 1 or self.leverage > 125:
            raise ValueError(f"leverage must be between 1 and 125, got {self.leverage}")
        
        if self.stop_loss_pct < 0 or self.stop_loss_pct > 100:
            raise ValueError(f"stop_loss_pct must be between 0 and 100, got {self.stop_loss_pct}")
        
        if self.take_profit_pct < 0:
            raise ValueError(f"take_profit_pct must be non-negative, got {self.take_profit_pct}")
        
        if self.slippage < 0 or self.slippage > 1:
            raise ValueError(f"slippage must be between 0 and 1, got {self.slippage}")
        
        if self.commission < 0 or self.commission > 1:
            raise ValueError(f"commission must be between 0 and 1, got {self.commission}")
        
        if self.step < 1:
            raise ValueError(f"step must be at least 1, got {self.step}")
        
        # Validate symbol format
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("symbol must be a non-empty string")
        
        # Validate strategy mode
        if self.strategy_mode not in ['technical', 'agent']:
            raise ValueError(f"strategy_mode must be 'technical' or 'agent', got {self.strategy_mode}")
        
        # Validate margin mode
        if self.margin_mode not in ['cross', 'isolated']:
            raise ValueError(f"margin_mode must be 'cross' or 'isolated', got {self.margin_mode}")
        
        # Validate contract type
        if self.contract_type not in ['linear', 'inverse']:
            raise ValueError(f"contract_type must be 'linear' or 'inverse', got {self.contract_type}")
        
        # Validate market type
        if self.market not in ['crypto', 'indian']:
            raise ValueError(f"market must be 'crypto' or 'indian', got {self.market}")
        
        # Validate Indian market settings
        if self.market == 'indian':
            if self.exchange not in ['NSE', 'BSE', 'NFO', 'MCX', 'CDS', 'BFO']:
                raise ValueError(f"exchange must be NSE, BSE, NFO, MCX, CDS, or BFO for Indian market, got {self.exchange}")
            if self.product_type not in ['INTRADAY', 'DELIVERY', 'CARRYFORWARD', 'MARGIN']:
                raise ValueError(f"product_type must be INTRADAY, DELIVERY, CARRYFORWARD, or MARGIN, got {self.product_type}")
    
    def calculate_indian_charges(self, turnover: float, is_buy: bool = True) -> float:
        """
        Calculate Indian market charges (STT, stamp duty, exchange charges, SEBI, GST)
        
        Args:
            turnover: Trade value (price * quantity)
            is_buy: True for buy, False for sell
            
        Returns:
            Total charges in INR
        """
        if self.market != 'indian':
            return turnover * self.commission
        
        charges = 0.0
        
        # Brokerage (use commission as brokerage rate)
        brokerage = turnover * self.commission
        charges += brokerage
        
        # STT (Securities Transaction Tax) - only on sell for intraday
        if self.product_type == 'INTRADAY':
            if not is_buy:  # STT only on sell for intraday
                charges += turnover * (self.stt_pct / 100)
        else:  # Delivery - STT on both buy and sell
            charges += turnover * (self.stt_pct / 100)
        
        # Stamp Duty - only on buy
        if is_buy:
            charges += turnover * (self.stamp_duty_pct / 100)
        
        # Exchange charges
        charges += turnover * (self.exchange_charges_pct / 100)
        
        # SEBI charges
        charges += turnover * (self.sebi_charges_pct / 100)
        
        # GST on brokerage and exchange charges
        gst_base = brokerage + (turnover * self.exchange_charges_pct / 100)
        charges += gst_base * (self.gst_pct / 100)
        
        return charges



@dataclass
class BacktestResult:
    """Backtest result"""
    config: BacktestConfig
    metrics: MetricsResult
    equity_curve: pd.DataFrame
    trades: List[Trade]
    decisions: List[Dict] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict:
        # Get decision data and deduplicate
        def _get_filtered_decisions():
            """Get filtered and deduplicated decision list"""
            # Get last 50 decisions
            recent = self.decisions[-50:] if len(self.decisions) > 50 else self.decisions
            # Get all non-hold decisions
            non_hold = [d for d in self.decisions if d.get('action') != 'hold']
            
            # Merge and deduplicate (based on timestamp)
            seen = set()
            result = []
            for d in recent + non_hold:
                # Use timestamp as unique key
                key = d.get('timestamp')
                if key and key not in seen:
                    seen.add(key)
                    # Keep only needed fields
                    filtered = {k: v for k, v in d.items() if k in ['timestamp', 'action', 'confidence', 'reason', 'price', 'vote_details']}
                    result.append(filtered)
            return result
        
        return {
            'config': {
                'symbol': self.config.symbol,
                'start_date': self.config.start_date,
                'end_date': self.config.end_date,
                'initial_capital': self.config.initial_capital,
            },
            'metrics': self.metrics.to_dict(),
            'total_trades': len(self.trades),
            'duration_seconds': self.duration_seconds,
            'decisions': _get_filtered_decisions(),
        }


class BacktestEngine:
    """
    Backtest Engine Core
    
    Workflow:
    1. Load historical data
    2. Initialize virtual portfolio
    3. Iterate through each time point
    4. Execute strategy decisions
    5. Simulate trade execution
    6. Record equity and trades
    7. Calculate performance metrics
    8. Generate report
    """
    
    def __init__(
        self,
        config: BacktestConfig,
        strategy_fn: Optional[Callable] = None
    ):
        """
        Initialize backtest engine
        
        Args:
            config: Backtest configuration
            strategy_fn: Strategy function, receives (snapshot, portfolio) returns {'action': 'long/short/hold', 'confidence': 0-1}
        """
        self.config = config
        self.strategy_fn = strategy_fn or self._default_strategy
        
        # 组件
        self.data_replay: Optional[DataReplayAgent] = None
        self.portfolio: Optional[BacktestPortfolio] = None
        self.agent_runner = None
        
        # Initialize Agent Runner if needed
        if config.strategy_mode == "agent":
            from src.backtest.agent_wrapper import BacktestAgentRunner
            self.agent_runner = BacktestAgentRunner(config.__dict__)
        
        # 状态
        self.is_running = False
        self.current_timestamp: Optional[datetime] = None
        self.decisions: List[Dict] = []
        
        log.info(f"🔬 BacktestEngine initialized | {config.symbol} | "
                 f"{config.start_date} to {config.end_date}")
    
    async def run(self, progress_callback: Callable = None) -> BacktestResult:
        """
        Run complete backtest
        
        Args:
            progress_callback: Progress callback function (current, total, pct)
            
        Returns:
            BacktestResult object
        """
        start_time = datetime.now()
        self.is_running = True
        
        log.info("=" * 60)
        log.info("🚀 Starting Backtest")
        log.info("=" * 60)
        
        # 1. Initialize data replay agent
        self.data_replay = DataReplayAgent(
            symbol=self.config.symbol,
            start_date=self.config.start_date,
            end_date=self.config.end_date
        )
        
        success = await self.data_replay.load_data()
        if not success:
            raise RuntimeError("Failed to load historical data")
        
        # 2. Initialize portfolio
        self.portfolio = BacktestPortfolio(
            initial_capital=self.config.initial_capital,
            slippage=self.config.slippage,
            commission=self.config.commission
        )
        
        # 3. Iterate through time points
        timestamps = list(self.data_replay.iterate_timestamps(step=self.config.step))
        total = len(timestamps)
        
        log.info(f"📊 Processing {total} timestamps (step={self.config.step})")
        log.info(f"⏱️  Estimated time: {total * 72 / 60:.1f} minutes (3 LLM calls per timepoint)")
        
        for i, timestamp in enumerate(timestamps):
            if not self.is_running:
                log.warning("Backtest stopped by user")
                break
            
            self.current_timestamp = timestamp
            
            try:
                # Get market snapshot
                snapshot = self.data_replay.get_snapshot_at(timestamp)
                current_price = self.data_replay.get_current_price()
                
                # 🆕 Check and apply funding rate settlement
                funding_rate = self.data_replay.get_funding_rate_for_settlement(timestamp)
                if funding_rate is not None:
                    # Get mark price (if available)
                    fr_record = self.data_replay.get_funding_rate_at(timestamp)
                    mark_price = fr_record.mark_price if fr_record and fr_record.mark_price > 0 else current_price
                    
                    # Apply funding rate to all positions
                    for symbol in list(self.portfolio.positions.keys()):
                        self.portfolio.apply_funding_fee(symbol, funding_rate, mark_price, timestamp)
                
                # 🆕 Check liquidation
                prices = {self.config.symbol: current_price}
                liquidated = self.portfolio.check_liquidation(prices, timestamp)
                if liquidated:
                    log.warning(f"⚠️ Positions liquidated: {liquidated}")
                    continue  # Skip strategy execution after liquidation
                
                # Check stop loss and take profit
                self.portfolio.check_stop_loss_take_profit(prices, timestamp)
                
                # Execute strategy
                decision = await self._execute_strategy(snapshot, current_price)
                self.decisions.append(decision)
                
                # Execute trade
                await self._execute_decision(decision, current_price, timestamp)
                
                # Record equity (OPTIMIZATION: Sample every 12 steps or on key events)
                should_record_equity = (i % 12 == 0) or (i == total - 1) or (decision['action'] != 'hold')
                if should_record_equity:
                    self.portfolio.record_equity(timestamp, prices)
                
                
                # 进度回调（包含实时收益数据和增量可视化数据）
                if progress_callback:
                    progress_pct = (i + 1) / total * 100  # +1 because we just completed this timepoint
                    
                    # Send progress update
                    current_equity = self.portfolio.get_current_equity(prices)
                    profit = current_equity - self.config.initial_capital
                    profit_pct = (profit / self.config.initial_capital) * 100
                    
                    # Calculate fresh equity point for real-time display (not from stale curve)
                    # Update peak for drawdown calculation
                    if current_equity > self.portfolio.peak_equity:
                        peak_equity = current_equity
                    else:
                        peak_equity = self.portfolio.peak_equity
                    
                    drawdown = peak_equity - current_equity
                    drawdown_pct = drawdown / peak_equity * 100 if peak_equity > 0 else 0
                    
                    latest_equity_point = {
                        'timestamp': timestamp.isoformat(),
                        'total_equity': float(current_equity),
                        'drawdown_pct': float(drawdown_pct)
                    }
                    
                    # 获取最新交易（最近1笔）
                    latest_trade = None
                    if self.portfolio.trades:
                        trade = self.portfolio.trades[-1]
                        latest_trade = {
                            'timestamp': trade.timestamp.isoformat(),
                            'side': trade.side.value,
                                            'action': trade.action,
                            'price': float(trade.price),
                            'pnl': float(trade.pnl),
                            'pnl_pct': float(trade.pnl_pct)
                        }
                    
                    # 计算实时指标
                    trades_count = len(self.portfolio.trades)
                    winning_trades = sum(1 for t in self.portfolio.trades if t.pnl > 0 and t.action == 'close')
                    win_rate = (winning_trades / trades_count * 100) if trades_count > 0 else 0
                    
                    callback_data = {
                        'progress': progress_pct,
                        'current_timepoint': i + 1,  # Human-readable: 1-indexed
                        'total_timepoints': total,
                        'current_equity': current_equity,
                        'profit': profit,
                        'profit_pct': profit_pct,
                        'timestamp': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                        'equity_point': latest_equity_point,
                        'latest_trade': latest_trade,
                        'metrics': {
                            'total_trades': trades_count,
                            'win_rate': win_rate,
                            'max_drawdown_pct': self.portfolio.equity_curve[-1].drawdown_pct if self.portfolio.equity_curve else 0
                        }
                    }

                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(callback_data)
                    else:
                        progress_callback(callback_data)
                
            except (KeyError, ValueError, IndexError) as e:
                # Recoverable data error: log warning and skip this timestamp
                log.warning(f"Data error at {timestamp}: {type(e).__name__}: {e}, skipping this timestamp")
                continue
            except Exception as e:
                # Fatal error: log error and terminate backtest
                log.error(f"Fatal error at {timestamp}: {type(e).__name__}: {e}")
                log.error(f"Backtest terminated due to fatal error")
                raise RuntimeError(f"Backtest failed at {timestamp}: {e}") from e
        
        # 4. Force close all positions
        await self._close_all_positions()
        
        # 5. Calculate performance metrics
        equity_curve = self.portfolio.get_equity_dataframe()
        trades = self.portfolio.trades
        
        metrics = PerformanceMetrics.calculate(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=self.config.initial_capital
        )
        
        # 6. Generate result
        duration = (datetime.now() - start_time).total_seconds()
        
        result = BacktestResult(
            config=self.config,
            metrics=metrics,
            equity_curve=equity_curve,
            trades=trades,
            decisions=self.decisions,
            duration_seconds=duration
        )
        
        self.is_running = False
        
        log.info("=" * 60)
        log.info("✅ Backtest Complete")
        log.info(f"   Duration: {duration:.1f}s")
        log.info(f"   Total Return: {metrics.total_return:+.2f}%")
        log.info(f"   Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
        log.info(f"   Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        log.info(f"   Win Rate: {metrics.win_rate:.1f}%")
        log.info(f"   Total Trades: {metrics.total_trades}")
        log.info(f"   💸 Funding Paid: ${self.portfolio.total_funding_paid:.4f}")
        log.info(f"   💰 Fees Paid: ${self.portfolio.total_fees_paid:.2f}")
        log.info(f"   📉 Slippage Cost: ${self.portfolio.total_slippage_cost:.2f}")
        log.info(f"   🔥 Liquidations: {self.portfolio.liquidation_count}")
        log.info("=" * 60)
        
        return result
    
    async def _execute_strategy(
        self,
        snapshot,
        current_price: float
    ) -> Dict:
        """Execute strategy and return decision"""
        try:
            # 调用策略函数
            # DEBUG LOG
            log.info(f"DEBUG: execute_strategy mode={self.config.strategy_mode} runner={self.agent_runner}")
            
            if self.config.strategy_mode == "agent" and self.agent_runner:
                log.info("DEBUG: Entering agent runner step")
                decision = await self.agent_runner.step(snapshot, self.portfolio)
            else:
                decision = await self.strategy_fn(
                    snapshot=snapshot,
                    portfolio=self.portfolio,
                    current_price=current_price,
                    config=self.config
                )
            
            decision['timestamp'] = self.current_timestamp
            decision['price'] = current_price
            
            return decision
            
        except Exception as e:
            log.warning(f"Strategy error: {e}")
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'strategy_error: {e}',
                'timestamp': self.current_timestamp,
                'price': current_price
            }
    
    async def _execute_decision(
        self,
        decision: Dict,
        current_price: float,
        timestamp: datetime
    ):
        """Execute trade decision"""
        action = decision.get('action', 'hold')
        confidence = decision.get('confidence', 0.0)
        
        # 0. Global Safety Check: Minimum Confidence 50%
        # Filters out weak mechanical signals when LLM yields (0% confidence)
        if action in ['long', 'short', 'open_long', 'open_short', 'add_position'] and confidence < 50:
            log.warning(f"🚫 Confidence {confidence}% < 50% for {action}. Forcing WAIT.")
            return {'action': 'wait', 'reason': 'low_confidence_filtering'}
        
        # NOTE: Volatile Regime Guard REMOVED - was too strict, blocking all trades
        # The LLM already provides this context in the reason field
        
        # Normalize actions
        if action == 'open_long': action = 'long'
        if action == 'open_short': action = 'short'
        
        symbol = self.config.symbol
        has_position = symbol in self.portfolio.positions
        
        # Handle Add Position (Treat as increasing existing position)
        if action == 'add_position' and has_position:
            # Re-map to long/short based on current side
            current_side = self.portfolio.positions[symbol].side
            action = 'long' if current_side == Side.LONG else 'short'
            # Fall through to Open logic
            
        # Handle Reduce Position
        if action == 'reduce_position' and has_position:
            # Partial Close logic
            current_pos = self.portfolio.positions[symbol]
            reduce_pct = 0.5 # Default reduce by 50%
            
            # Check if LLM specified size
            params = decision.get('trade_params') or {}
            if params.get('position_size_pct', 0) > 0:
                # Interpret as "Reduce BY X%" or "Reduce TO X%"? 
                # Usually "Position Size" implies target. 
                # Let's assume Reduce means "Close 50%" unless specific instructions.
                # Simplest: Reduce 50%
                pass
            
            reduce_qty = current_pos.quantity * reduce_pct
            self.portfolio.close_position(
                symbol=symbol,
                price=current_price,
                timestamp=timestamp,
                quantity=reduce_qty,
                reason='reduce_position'
            )
            return

        # Basic Action Filtering
        if action in ['close', 'close_short', 'close_long'] and has_position:
            # Close Position
            # Validate direction matches if specified (close_short for SHORT, close_long for LONG)
            current_side = self.portfolio.positions[symbol].side
            if action == 'close_short' and current_side != Side.SHORT:
                log.warning(f"⚠️ close_short signal but position is {current_side}, ignoring")
                return
            if action == 'close_long' and current_side != Side.LONG:
                log.warning(f"⚠️ close_long signal but position is {current_side}, ignoring")
                return
            
            # PHASE 2: Enforce Minimum Hold Time (3h) - Hard Block
            pos = self.portfolio.positions[symbol]
            current_pnl_pct = pos.get_pnl_pct(current_price)
            hold_hours = (timestamp - pos.entry_time).total_seconds() / 3600 if pos.entry_time else 0
            
            # Hard minimum hold: Block ALL closes before 3h unless severe loss
            if hold_hours < 3:
                # Only allow close if: (a) losing > 5%, or (b) reason contains stop_loss/trailing
                close_reason = decision.get('reason', '').lower()
                is_stop_loss = 'stop_loss' in close_reason or 'trailing' in close_reason
                is_severe_loss = current_pnl_pct < -5.0
                
                if not is_stop_loss and not is_severe_loss:
                    log.info(f"🛡️ HOLD ENFORCEMENT: {hold_hours:.1f}h < 3h min hold. PnL={current_pnl_pct:+.2f}%. Blocking close.")
                    return
            
            self.portfolio.close_position(
                symbol=symbol,
                price=current_price,
                timestamp=timestamp,
                reason='signal'
            )
            log.info(f"✅ Closed {current_side.value} position via {action} signal")
            return

        if action in ['long', 'short']:
            side = Side.LONG if action == 'long' else Side.SHORT
            
            # Handle reverse position (Reversal)
            if has_position:
                current_side = self.portfolio.positions[symbol].side
                if current_side != side:
                    # Reverse signal, close first
                    self.portfolio.close_position(
                        symbol=symbol,
                        price=current_price,
                        timestamp=timestamp,
                        reason='reverse_signal'
                    )
                    has_position = False # Mark as no position to execute open below
            
            # Execute open/add position (Open / Add)
            # At this point we either have no position (New/Reversal) or same-direction position (Add)
            
            # --- Copy previous dynamic parameter logic ---
            params = decision.get('trade_params') or {}
            leverage = params.get('leverage') or self.config.leverage
            sl_pct = params.get('stop_loss_pct') or self.config.stop_loss_pct
            tp_pct = params.get('take_profit_pct') or self.config.take_profit_pct
            trailing_pct = params.get('trailing_stop_pct')
            
            available_cash = self.portfolio.cash
            
            if params.get('position_size_pct', 0) > 0:
                use_cash = available_cash * (params['position_size_pct'] / 100)
                target_position_value = use_cash * leverage
                position_size = min(
                    target_position_value,
                    available_cash * 0.98 * leverage,
                    self.config.max_position_size * leverage
                )
            else:
                # Default logic
                position_size = min(
                    self.config.max_position_size * leverage,
                    available_cash * 0.95
                )
            
            # If adding position, check if exceeds total limit (Portfolio.open_position usually handles increase, but we need to control total)
            # For simplicity, we assume position_size is the order amount for this trade (Incremental)
            # For "Add", Agent usually means "Add X amount".
            
            quantity = position_size / current_price
            
            if quantity > 0:
                self.portfolio.open_position(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=current_price,
                    timestamp=timestamp,
                    stop_loss_pct=sl_pct,
                    take_profit_pct=tp_pct,
                    trailing_stop_pct=trailing_pct
                )
    
    async def _close_all_positions(self):
        """Close all positions"""
        if self.portfolio is None:
            return
        
        for symbol in list(self.portfolio.positions.keys()):
            current_price = self.data_replay.get_current_price()
            self.portfolio.close_position(
                symbol=symbol,
                price=current_price,
                timestamp=self.current_timestamp,
                reason='backtest_end'
            )
    
    async def _default_strategy(
        self,
        snapshot,
        portfolio: BacktestPortfolio,
        current_price: float,
        config: BacktestConfig
    ) -> Dict:
        """
        Default strategy (simple trend following)
        
        Uses EMA crossover as signal (direct calculation, no external dependencies)
        """
        # Get stable data
        df = snapshot.stable_5m.copy()
        
        if len(df) < 50:
            return {'action': 'hold', 'confidence': 0.0, 'reason': 'insufficient_data'}
        
        # Calculate EMA (direct calculation)
        close = df['close'].astype(float)
        ema_20 = close.ewm(span=20, adjust=False).mean()
        ema_50 = close.ewm(span=50, adjust=False).mean()
        
        # Current and previous values
        ema_fast = ema_20.iloc[-1]
        ema_slow = ema_50.iloc[-1]
        ema_fast_prev = ema_20.iloc[-2]
        ema_slow_prev = ema_50.iloc[-2]
        
        # Golden cross / Death cross
        symbol = config.symbol
        has_position = symbol in portfolio.positions
        
        if ema_fast > ema_slow and ema_fast_prev <= ema_slow_prev:
            # Golden cross - go long
            if has_position:
                current_side = portfolio.positions[symbol].side
                if current_side == Side.SHORT:
                    return {'action': 'long', 'confidence': 0.7, 'reason': 'golden_cross_reverse'}
                return {'action': 'hold', 'confidence': 0.5, 'reason': 'already_long'}
            return {'action': 'long', 'confidence': 0.7, 'reason': 'golden_cross'}
        
        elif ema_fast < ema_slow and ema_fast_prev >= ema_slow_prev:
            # Death cross - go short
            if has_position:
                current_side = portfolio.positions[symbol].side
                if current_side == Side.LONG:
                    return {'action': 'short', 'confidence': 0.7, 'reason': 'death_cross_reverse'}
                return {'action': 'hold', 'confidence': 0.5, 'reason': 'already_short'}
            return {'action': 'short', 'confidence': 0.7, 'reason': 'death_cross'}
        
        return {'action': 'hold', 'confidence': 0.3, 'reason': 'no_signal'}
    
    def stop(self):
        """Stop backtest"""
        self.is_running = False
    
    def generate_report(self, result: BacktestResult, filename: str = None) -> str:
        """
        Generate backtest report
        
        Args:
            result: Backtest result
            filename: File name
            
        Returns:
            Report file path
        """
        report = BacktestReport()
        
        config_dict = {
            'symbol': self.config.symbol,
            'initial_capital': self.config.initial_capital,
            'start_date': self.config.start_date,
            'end_date': self.config.end_date,
        }
        
        trades_df = self.portfolio.get_trades_dataframe() if self.portfolio else pd.DataFrame()
        
        filepath = report.generate(
            metrics=result.metrics,
            equity_curve=result.equity_curve,
            trades_df=trades_df,
            config=config_dict,
            filename=filename
        )
        
        log.info(f"📄 Report saved to: {filepath}")
        return filepath


# CLI entry support
async def run_backtest_cli(
    symbol: str = "BTCUSDT",
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-01",
    initial_capital: float = 10000,
    step: int = 3
) -> BacktestResult:
    """
    CLI run backtest
    
    Args:
        symbol: Trading pair
        start_date: Start date
        end_date: End date
        initial_capital: Initial capital
        step: Time step
        
        Returns:
        BacktestResult
    """
    config = BacktestConfig(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        step=step
    )
    
    engine = BacktestEngine(config)
    
    def progress(current, total, pct):
        print(f"\rProgress: {current}/{total} ({pct:.1f}%)", end="", flush=True)
    
    result = await engine.run(progress_callback=progress)
    print()  # Newline
    
    # Generate report
    report_path = engine.generate_report(result)
    print(f"\n📄 Report: {report_path}")
    
    return result


# Test function
async def test_backtest_engine():
    """Test backtest engine"""
    print("\n" + "=" * 60)
    print("🧪 Testing BacktestEngine")
    print("=" * 60)
    
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_date="2024-12-01",
        end_date="2024-12-07",
        initial_capital=10000,
        step=12  # 每小时一个决策点
    )
    
    engine = BacktestEngine(config)
    
    def progress(current, total, pct):
        if current % 10 == 0:
            print(f"   Progress: {pct:.1f}%")
    
    result = await engine.run(progress_callback=progress)
    
    print(f"\n📊 Results:")
    print(f"   Total Return: {result.metrics.total_return:+.2f}%")
    print(f"   Max Drawdown: {result.metrics.max_drawdown_pct:.2f}%")
    print(f"   Sharpe Ratio: {result.metrics.sharpe_ratio:.2f}")
    print(f"   Total Trades: {result.metrics.total_trades}")
    
    # 生成报告
    report_path = engine.generate_report(result, "test_backtest")
    print(f"\n📄 Report: {report_path}")
    
    print("\n✅ BacktestEngine test complete!")
    return result


if __name__ == "__main__":
    asyncio.run(test_backtest_engine())
