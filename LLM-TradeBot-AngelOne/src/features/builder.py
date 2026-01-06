"""
Feature Building Module - Prepare input data for LLM
"""
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np
from src.utils.logger import log


class FeatureBuilder:
    """Feature Builder - Convert market data to LLM-understandable context"""
    
    def __init__(self):
        pass
    
    def build_market_context(
        self,
        symbol: str,
        multi_timeframe_states: Dict[str, Dict],
        snapshot: Dict,
        position_info: Optional[Dict] = None
    ) -> Dict:
        """
        Build complete market context
        
        Args:
            symbol: Trading pair
            multi_timeframe_states: Multi-timeframe market states
            snapshot: Market snapshot
            position_info: Position information
            
        Returns:
            Structured market context (with complete metadata and data quality validation)
        """
        
        # === Data Quality Validation (Silent Check) ===
        # Validate multi-timeframe price consistency
        price_check = self._validate_multiframe_prices(multi_timeframe_states)
        if not price_check['consistent']:
            log.debug(f"[{symbol}] Multi-timeframe price consistency: {', '.join(price_check['warnings'])}")
        
        # Validate multi-timeframe time alignment
        alignment_check = self._validate_multiframe_alignment(multi_timeframe_states)
        if not alignment_check['aligned']:
            log.debug(f"[{symbol}] Multi-timeframe time alignment: {', '.join(alignment_check['warnings'])}")
        
        # Validate indicator completeness (per timeframe)
        indicator_completeness = {}
        for tf, state in multi_timeframe_states.items():
            if 'indicator_completeness' in state:
                indicator_completeness[tf] = state['indicator_completeness']
            else:
                # If processor didn't provide, mark as unknown
                indicator_completeness[tf] = {
                    'is_complete': None,
                    'issues': ['Indicator completeness check not provided'],
                    'overall_coverage': None
                }
        
        # Extract current price info
        current_price = snapshot.get('price', {}).get('price', 0)
        
        # Funding rate
        funding_rate = snapshot.get('funding', {}).get('funding_rate', 0)
        
        # Open interest
        oi_data = snapshot.get('oi', {})
        
        # Order book liquidity analysis
        orderbook = snapshot.get('orderbook', {})
        liquidity_score = self._analyze_liquidity(orderbook)
        
        # Extract account fetch error (if any)
        account_fetch_error = snapshot.get('account_error', None)
        
        # Extract snapshot IDs (for data consistency tracking)
        snapshot_ids = {}
        for tf, state in multi_timeframe_states.items():
            if 'snapshot_id' in state:
                snapshot_ids[tf] = state['snapshot_id']
        
        # Build context
        context = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            
            # === Data Consistency Tracking ===
            'snapshot_ids': snapshot_ids,
            
            # Market overview
            'market_overview': {
                'current_price': current_price,
                'funding_rate': funding_rate,
                'funding_rate_status': self._classify_funding_rate(funding_rate),
                'open_interest': oi_data.get('open_interest', 0),
                'liquidity': liquidity_score
            },
            
            # Multi-timeframe analysis
            'multi_timeframe': multi_timeframe_states,
            
            # Position context
            'position_context': self._build_position_context(
                position_info,
                current_price,
                snapshot.get('account', {}),
                account_fetch_error
            ),
            
            # Risk constraints
            'risk_constraints': self._get_risk_constraints(),
            
            # Data Quality Report
            'data_quality': {
                'price_consistency': price_check,
                'time_alignment': alignment_check,
                'indicator_completeness': indicator_completeness,
                'overall_score': self._calculate_quality_score(price_check, alignment_check, indicator_completeness)
            }
        }
        
        return context
    
    def _analyze_liquidity(self, orderbook: Dict) -> str:
        """
        Analyze order book liquidity
        
        Returns:
            'high', 'medium', 'low'
        """
        if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
            return 'unknown'
        
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        if not bids or not asks:
            return 'low'
        
        # Calculate top 5 levels depth
        bid_depth = sum([q for p, q in bids[:5]])
        ask_depth = sum([q for p, q in asks[:5]])
        
        total_depth = bid_depth + ask_depth
        
        # Simple classification (thresholds need adjustment based on actual market)
        if total_depth > 100:
            return 'high'
        elif total_depth > 50:
            return 'medium'
        else:
            return 'low'
    
    def _classify_funding_rate(self, funding_rate: float) -> str:
        """
        Classify funding rate
        
        Returns:
            'extremely_positive', 'positive', 'neutral', 'negative', 'extremely_negative'
        """
        if funding_rate > 0.001:
            return 'extremely_positive'
        elif funding_rate > 0.0003:
            return 'positive'
        elif funding_rate < -0.001:
            return 'extremely_negative'
        elif funding_rate < -0.0003:
            return 'negative'
        else:
            return 'neutral'
    
    def _build_position_context(
        self,
        position: Optional[Dict],
        current_price: float,
        account: Optional[Dict],
        account_fetch_error: Optional[str] = None
    ) -> Dict:
        """
        Build position context
        
        Important: Do not convert None/missing to 0, explicitly mark as None
        """
        
        # If no account info, explicitly mark as None
        if not account or account_fetch_error:
            return {
                'has_position': False,
                'side': 'NONE',
                'size': None,
                'entry_price': None,
                'current_pnl_pct': None,
                'unrealized_pnl': None,
                'account_balance': None,
                'total_balance': None,
                'margin_usage_pct': None,
                'account_fetch_error': account_fetch_error or 'No account data available',
                'warning': 'Account info missing, trading is not recommended'
            }
        
        if not position or position.get('position_amt', 0) == 0:
            return {
                'has_position': False,
                'side': 'NONE',
                'size': 0,
                'entry_price': 0,
                'current_pnl_pct': 0,
                'unrealized_pnl': 0,
                'account_balance': account.get('available_balance', 0),
                'total_balance': account.get('total_wallet_balance', 0),
                'margin_usage_pct': 0,
                'account_fetch_error': None
            }
        
        position_amt = position.get('position_amt', 0)
        entry_price = position.get('entry_price', 0)
        unrealized_pnl = position.get('unrealized_profit', 0)
        
        # Calculate PnL percentage
        if entry_price > 0:
            if position_amt > 0:  # LONG
                pnl_pct = (current_price - entry_price) / entry_price * 100
            else:  # SHORT
                pnl_pct = (entry_price - current_price) / entry_price * 100
        else:
            pnl_pct = 0
        
        # Calculate margin usage rate
        total_balance = account.get('total_wallet_balance', 0)
        margin_balance = account.get('total_margin_balance', 0)
        
        margin_usage_pct = 0
        if total_balance > 0:
            margin_usage_pct = (margin_balance / total_balance) * 100
        
        return {
            'has_position': True,
            'side': 'LONG' if position_amt > 0 else 'SHORT',
            'size': abs(position_amt),
            'entry_price': entry_price,
            'current_price': current_price,
            'current_pnl_pct': round(pnl_pct, 2),
            'unrealized_pnl': unrealized_pnl,
            'account_balance': account.get('available_balance', 0),
            'total_balance': total_balance,
            'margin_usage_pct': round(margin_usage_pct, 2),
            'leverage': position.get('leverage', 1),
            'account_fetch_error': None
        }
    
    def _get_risk_constraints(self) -> Dict:
        """Get risk constraint configuration"""
        from src.config import config
        
        return {
            'max_risk_per_trade_pct': config.risk.get('max_risk_per_trade_pct', 1.5),
            'max_total_position_pct': config.risk.get('max_total_position_pct', 30.0),
            'max_leverage': config.risk.get('max_leverage', 5),
            'max_consecutive_losses': config.risk.get('max_consecutive_losses', 3)
        }
    
    def format_for_llm(self, context: Dict) -> str:
        """
        Format context as LLM-friendly text
        
        This is the final input provided to DeepSeek
        """
        
        market = context['market_overview']
        position = context['position_context']
        mtf = context['multi_timeframe']
        constraints = context['risk_constraints']
        
        # Build text description
        text = f"""
## Market Snapshot ({context['timestamp']})

**Trading Pair**: {context['symbol']}
**Current Price**: ${market['current_price']:,.2f}

### Market Status Overview
- **Funding Rate**: {market['funding_rate']:.4%} ({market['funding_rate_status']})
  - Funding rate reflects long/short power balance
- **Open Interest (OI)**: {market['open_interest']:,.0f}
  - Increasing OI indicates new capital entering
- **Liquidity Depth**: {market['liquidity']}
  - Reflects order book depth

### Multi-Timeframe Analysis
"""
        
        # Add multi-timeframe states (sorted by timeframe)
        timeframe_order = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        sorted_tfs = sorted(mtf.keys(), key=lambda x: timeframe_order.index(x) if x in timeframe_order else 999)
        
        for tf in sorted_tfs:
            state = mtf[tf]
            text += f"\n**{tf}**:\n"
            text += f"  - Trend: {state.get('trend', 'N/A')}\n"
            text += f"  - Volatility: {state.get('volatility', 'N/A')} (ATR: {state.get('atr_pct', 'N/A')}%)\n"
            text += f"  - Momentum: {state.get('momentum', 'N/A')}\n"
            text += f"  - RSI: {state.get('rsi', 'N/A')}\n"
            text += f"  - MACD Signal: {state.get('macd_signal', 'N/A')}\n"
            text += f"  - Volume Ratio: {state.get('volume_ratio', 'N/A')}\n"
            text += f"  - Volume Change: {state.get('volume_change_pct', 'N/A')}%\n"
            text += f"  - Current Price: ${state.get('price', 'N/A')}\n"
            
            levels = state.get('key_levels', {})
            if levels.get('support'):
                text += f"  - Support: {levels['support']}\n"
            if levels.get('resistance'):
                text += f"  - Resistance: {levels['resistance']}\n"
        
        # Position info
        text += "\n### Current Position\n"
        if position.get('account_fetch_error'):
            text += f"Warning: {position['warning']}\n"
            text += f"- Error Reason: {position['account_fetch_error']}\n"
        elif position['has_position']:
            text += f"- Direction: {position['side']}\n"
            text += f"- Quantity: {position['size']}\n"
            text += f"- Entry Price: ${position['entry_price']:,.2f}\n"
            text += f"- Current PnL: {position['current_pnl_pct']:.2f}%\n"
            text += f"- Unrealized PnL: ${position['unrealized_pnl']:,.2f}\n"
            text += f"- Leverage: {position['leverage']}x\n"
            text += f"- Margin Usage: {position['margin_usage_pct']:.1f}%\n"
        else:
            text += "- No Position\n"
        
        text += f"\n### Account Info\n"
        if position.get('account_fetch_error'):
            text += "- Available Balance: **Unable to fetch**\n"
            text += "- Total Balance: **Unable to fetch**\n"
        else:
            balance = position.get('account_balance')
            total = position.get('total_balance', 0)
            text += f"- Available Balance: ${balance:,.2f}\n" if balance is not None else "- Available Balance: **Unknown**\n"
            text += f"- Total Balance: ${total:,.2f}\n"
        
        # Risk constraints
        text += f"\n### Risk Constraints\n"
        text += f"- Max Risk Per Trade: {constraints['max_risk_per_trade_pct']}%\n"
        text += f"- Max Total Position: {constraints['max_total_position_pct']}%\n"
        text += f"- Max Leverage: {constraints['max_leverage']}x\n"
        text += f"- Max Consecutive Losses: {constraints['max_consecutive_losses']} times\n"
        
        return text
    
    def _validate_multiframe_prices(self, multi_timeframe_states: Dict[str, Dict]) -> Dict:
        """Validate multi-timeframe price consistency"""
        all_prices = []
        warnings = []
        
        for tf, state in multi_timeframe_states.items():
            if 'close' in state:
                all_prices.append(state['close'])
            else:
                warnings.append(f"{tf} missing close price")
        
        if len(set(all_prices)) > 1:
            warnings.append("Close prices across different timeframes are inconsistent")
        
        return {
            'consistent': len(warnings) == 0,
            'warnings': warnings
        }
    
    def _validate_multiframe_alignment(self, multi_timeframe_states: Dict[str, Dict]) -> Dict:
        """Validate multi-timeframe time alignment"""
        all_times = []
        warnings = []
        
        for tf, state in multi_timeframe_states.items():
            if 'timestamp' in state:
                all_times.append(state['timestamp'])
            else:
                warnings.append(f"{tf} missing timestamp")
        
        if len(set(all_times)) > 1:
            warnings.append("Timestamps across different timeframes are inconsistent")
        
        return {
            'aligned': len(warnings) == 0,
            'warnings': warnings
        }
    
    def _calculate_quality_score(self, price_check: Dict, alignment_check: Dict, indicator_completeness: Dict) -> float:
        """Calculate data quality score (0-100)"""
        score = 100.0
        
        if not price_check.get('consistent', True):
            score -= 30
        elif len(price_check.get('warnings', [])) > 0:
            score -= 15
        
        if not alignment_check.get('aligned', True):
            score -= 20
        
        completeness_scores = []
        for tf, comp in indicator_completeness.items():
            if comp.get('is_complete') is True:
                completeness_scores.append(100.0)
            elif comp.get('overall_coverage') is not None:
                completeness_scores.append(comp['overall_coverage'] * 100)
            else:
                completeness_scores.append(0.0)
        
        if completeness_scores:
            avg_completeness = sum(completeness_scores) / len(completeness_scores)
            score -= (100 - avg_completeness) * 0.5
        else:
            score -= 50
        
        return max(score, 0.0)
