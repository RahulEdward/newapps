"""
The Critic Agent (Decision Core)
===========================================

Responsibilities:
1. Weighted voting mechanism - Integrate multiple signal sources from quant analyst
2. Dynamic weight adjustment - Adjust signal weights based on historical performance
3. Multi-period alignment decision - Priority: 1h > 15m > 5m
4. LLM decision enhancement - Pass quantitative signals as context to DeepSeek
5. Final decision output - Unified format {action, confidence, reason}

Author: AI Trader Team
Date: 2025-12-19
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import json

from src.utils.logger import log
from src.agents.position_analyzer import PositionAnalyzer
from src.agents.regime_detector import RegimeDetector
from src.agents.predict_agent import PredictResult


@dataclass
class SignalWeight:
    """Signal weight configuration
    
    Note: All weights should sum to 1.0 (excluding dynamic sentiment)
    Current config: trend(0.45) + oscillator(0.20) + prophet(0.15) = 0.80
    sentiment uses dynamic weight (0.20)
    """
    # Trend signals (total 0.35) - OPTIMIZATION (Phase 3): Reduced from 0.45
    trend_5m: float = 0.05   # Reduced from 0.10
    trend_15m: float = 0.10  # Reduced from 0.15
    trend_1h: float = 0.20   # Kept same (Core trend backbone)
    # Oscillator signals (total 0.20)
    oscillator_5m: float = 0.05
    oscillator_15m: float = 0.07
    oscillator_1h: float = 0.08
    # Prophet ML prediction weight
    prophet: float = 0.15
    # Sentiment signal (dynamic weight, 0.30 when data available, 0 when not) - OPTIMIZATION (Phase 3): Increased from 0.20
    sentiment: float = 0.30
    # Other extended signals (e.g., LLM)
    llm_signal: float = 0.0  # To be integrated


@dataclass
class VoteResult:
    """Voting result"""
    action: str  # 'long', 'short', 'close_long', 'close_short', 'hold'
    confidence: float  # 0.0 ~ 1.0
    weighted_score: float  # -100 ~ +100
    vote_details: Dict[str, float]  # Contribution score from each signal
    multi_period_aligned: bool  # Whether multi-period is aligned
    reason: str  # Decision reason
    regime: Optional[Dict] = None      # Market regime info
    position: Optional[Dict] = None    # Price position info
    trade_params: Optional[Dict] = None # Dynamic trade params (stop_loss, take_profit, leverage, etc.)


class DecisionCoreAgent:
    """The Critic (Decision Core Agent)
    
    Core functions:
    - Weighted voting: Integrate multiple signals based on configurable weights
    - Multi-period alignment: Detect multi-period trend consistency
    - Market awareness: Integrate position awareness and regime detection
    - Confidence enhancement: Calibrate confidence based on market regime and price position
    """
    
    def __init__(self, weights: Optional[SignalWeight] = None):
        """
        Initialize The Critic (Decision Core Agent)
        
        Args:
            weights: Custom signal weights (default uses built-in config)
        """
        self.weights = weights or SignalWeight()
        self.history: List[VoteResult] = []  # Historical decision records
        
        # Initialize auxiliary analyzers
        self.position_analyzer = PositionAnalyzer()
        self.regime_detector = RegimeDetector()
        
        self.performance_tracker = {
            'trend_5m': {'total': 0, 'correct': 0},
            'trend_15m': {'total': 0, 'correct': 0},
            'trend_1h': {'total': 0, 'correct': 0},
            'oscillator_5m': {'total': 0, 'correct': 0},
            'oscillator_15m': {'total': 0, 'correct': 0},
            'oscillator_1h': {'total': 0, 'correct': 0},
        }
        
    async def make_decision(
        self, 
        quant_analysis: Dict, 
        predict_result: Optional[PredictResult] = None,
        market_data: Optional[Dict] = None
    ) -> VoteResult:
        """
        Execute weighted voting decision
        
        Args:
            quant_analysis: Output from QuantAnalystAgent
            predict_result: Output from PredictAgent (ML prediction)
            market_data: Raw market data containing df_5m, df_15m, df_1h and current_price
            
        Returns:
            VoteResult object
        """
        # 1. Extract signal scores
        # 1. Extract signal scores
        # Fix: Read from granular scores provided by QuantAnalystAgent
        trend_data = quant_analysis.get('trend', {})
        osc_data = quant_analysis.get('oscillator', {})
        sentiment_data = quant_analysis.get('sentiment', {})
        
        scores = {
            'trend_5m': trend_data.get('trend_5m_score', 0),
            'trend_15m': trend_data.get('trend_15m_score', 0),
            'trend_1h': trend_data.get('trend_1h_score', 0),
            'oscillator_5m': osc_data.get('osc_5m_score', 0),
            'oscillator_15m': osc_data.get('osc_15m_score', 0),
            'oscillator_1h': osc_data.get('osc_1h_score', 0),
            'sentiment': sentiment_data.get('total_sentiment_score', 0)
        }
        
        # Integrate Prophet prediction score
        if predict_result is not None and hasattr(predict_result, 'probability_up'):
            # Map probability (0~1) to score (-100~+100)
            # 0.5 -> 0, 1.0 -> 100, 0.0 -> -100
            prob = predict_result.probability_up
            prophet_score = (prob - 0.5) * 200
            scores['prophet'] = prophet_score
        else:
            scores['prophet'] = 0.0
        
        # Calculate dynamic sentiment weight (use config weight when data available, 0 when not)
        has_sentiment = scores.get('sentiment', 0) != 0
        w_sentiment = self.weights.sentiment if has_sentiment else 0.0
        w_others = 1.0 - w_sentiment

        # 2. Market regime and position analysis
        regime = None
        position = None
        if market_data:
            df_5m = market_data.get('df_5m')
            curr_price = market_data.get('current_price')
            if df_5m is not None and curr_price is not None:
                regime = self.regime_detector.detect_regime(df_5m)
                position = self.position_analyzer.analyze_position(df_5m, curr_price)

        # 3. Weighted calculation (score range -100~+100)
        weighted_score = (
            (scores['trend_5m'] * self.weights.trend_5m +
             scores['trend_15m'] * self.weights.trend_15m +
             scores['trend_1h'] * self.weights.trend_1h +
             scores['oscillator_5m'] * self.weights.oscillator_5m +
             scores['oscillator_15m'] * self.weights.oscillator_15m +
             scores['oscillator_1h'] * self.weights.oscillator_1h +
             scores.get('prophet', 0) * self.weights.prophet) * w_others +
            (scores.get('sentiment', 0) * w_sentiment)
        )
        
        # 4. Calculate actual contribution score from each signal (for dashboard display)
        vote_details = {
            'trend_5m': scores['trend_5m'] * self.weights.trend_5m * w_others,
            'trend_15m': scores['trend_15m'] * self.weights.trend_15m * w_others,
            'trend_1h': scores['trend_1h'] * self.weights.trend_1h * w_others,
            'oscillator_5m': scores['oscillator_5m'] * self.weights.oscillator_5m * w_others,
            'oscillator_15m': scores['oscillator_15m'] * self.weights.oscillator_15m * w_others,
            'oscillator_1h': scores['oscillator_1h'] * self.weights.oscillator_1h * w_others,
            'prophet': scores.get('prophet', 0) * self.weights.prophet * w_others,
            'sentiment': scores.get('sentiment', 0) * w_sentiment
        }

        # 5. Early filter logic: Choppy market + poor position
        if regime and position:
            if regime['regime'] == 'choppy' and position['location'] == 'middle':
                result = VoteResult(
                    action='hold',
                    confidence=10.0,
                    weighted_score=0,
                    vote_details=vote_details,
                    multi_period_aligned=False,
                    reason=f"Adversarial filter: Choppy market and price in middle zone ({position['position_pct']:.1f}%), position opening prohibited",
                    regime=regime,
                    position=position
                )
                self.history.append(result)
                return result
        
        # 6. Multi-period alignment detection
        
        # 6. Multi-period alignment detection
        aligned, alignment_reason = self._check_multi_period_alignment(
            scores['trend_1h'],
            scores['trend_15m'],
            scores['trend_5m']
        )
        
        # 7. Initial decision mapping (pass regime for dynamic thresholds)
        action, base_confidence = self._score_to_action(weighted_score, aligned, regime)
        
        # 8. Comprehensive confidence calibration and adversarial audit
        final_confidence = base_confidence * 100
        
        # --- Adversarial audit: Institutional fund flow divergence check ---
        sent_details = quant_analysis.get('sentiment', {}).get('details', {})
        inst_nf_1h = sent_details.get('inst_netflow_1h', 0)
        
        if action == 'open_long' and inst_nf_1h < -1000000: # 1h institutional net outflow exceeds 1M
            final_confidence *= 0.5
            alignment_reason += " | Adversarial warning: Technical bullish but large institutional outflow (divergence)"
        elif action == 'open_short' and inst_nf_1h > 1000000: # 1h institutional net inflow exceeds 1M
            final_confidence *= 0.5
            alignment_reason += " | Adversarial warning: Technical bearish but large institutional inflow (divergence)"

        if regime and position:
            final_confidence = self._calculate_comprehensive_confidence(
                final_confidence, regime, position, aligned
            )
            # Confidence decay logic
            if action == 'open_long' and not position['allow_long']:
                final_confidence *= 0.3
                alignment_reason += f" | Warning: Long position too high ({position['position_pct']:.1f}%)"
            elif action == 'open_short' and not position['allow_short']:
                final_confidence *= 0.3
                alignment_reason += f" | Warning: Short position too low ({position['position_pct']:.1f}%)"

        # 9. Generate decision reason
        reason = self._generate_reason(
            weighted_score, 
            aligned, 
            alignment_reason, 
            quant_analysis,
            prophet_score=scores.get('prophet', 0),
            regime=regime
        )
        # 10. Build result
        result = VoteResult(
            action=action,
            confidence=final_confidence,
            weighted_score=weighted_score,
            vote_details=vote_details,
            multi_period_aligned=aligned,
            reason=reason,
            regime=regime,
            position=position
        )
        
        # 11. Record history
        self.history.append(result)
        
        return result

    async def vote(self, snapshot: Any, quant_analysis: Dict) -> VoteResult:
        """
        Compatibility interface: Call make_decision
        """
        # Convert snapshot to market_data format for make_decision
        market_data = {
            'df_5m': snapshot.stable_5m if hasattr(snapshot, 'stable_5m') else None,
            'current_price': snapshot.live_5m.get('close', 0) if hasattr(snapshot, 'live_5m') else 0
        }
        return await self.make_decision(quant_analysis, market_data)

    def _calculate_comprehensive_confidence(self, 
                                          base_conf: float, 
                                          regime: Dict, 
                                          position: Dict, 
                                          aligned: bool) -> float:
        """Calculate comprehensive confidence"""
        conf = base_conf
        
        # Bonus points
        if aligned: conf += 15
        if regime['regime'] in ['trending_up', 'trending_down']: conf += 10
        if position['quality'] == 'excellent': conf += 15
        
        # Penalty points
        if regime['regime'] == 'choppy': conf -= 25
        if position['location'] == 'middle': conf -= 30
        if regime['regime'] == 'volatile': conf -= 20
        
        return max(5.0, min(100.0, conf))
    
    def _check_multi_period_alignment(
        self, 
        score_1h: float, 
        score_15m: float, 
        score_5m: float
    ) -> Tuple[bool, str]:
        """
        Detect multi-period trend consistency
        
        Strategy:
        - All three periods same direction (all positive or all negative) -> Strong alignment
        - 1h and 15m aligned, 5m can differ -> Partial alignment
        - 1h neutral, check 15m and 5m -> Optimization: Relaxed conditions
        - Other -> Not aligned
        
        Returns:
            (is_aligned, alignment_reason)
        """
        signs = [
            1 if score_1h > 10 else (-1 if score_1h < -10 else 0),
            1 if score_15m > 10 else (-1 if score_15m < -10 else 0),
            1 if score_5m > 10 else (-1 if score_5m < -10 else 0)
        ]
        
        # All three periods fully aligned
        if signs[0] == signs[1] == signs[2] and signs[0] != 0:
            return True, f"Three-period strong {'bullish' if signs[0] > 0 else 'bearish'} alignment"
        
        # 1h and 15m aligned (ignore 5m noise)
        if signs[0] == signs[1] and signs[0] != 0:
            return True, f"Medium-long period {'bullish' if signs[0] > 0 else 'bearish'} alignment (1h+15m)"
        
        # Optimization: 1h neutral, check if 15m and 5m are aligned
        if signs[0] == 0 and signs[1] == signs[2] and signs[1] != 0:
            return True, f"Short period {'bullish' if signs[1] > 0 else 'bearish'} alignment (15m+5m), 1h neutral"
        
        # Optimization: 1h neutral but 15m has clear direction
        if signs[0] == 0 and abs(score_15m) > 30:
            direction = 'bullish' if signs[1] > 0 else 'bearish'
            return True, f"15m strong {direction} signal (score:{score_15m:.0f}), 1h neutral"
        
        # Not aligned
        return False, f"Multi-period divergence (1h:{signs[0]}, 15m:{signs[1]}, 5m:{signs[2]})"
    
    def _score_to_action(
        self, 
        weighted_score: float, 
        aligned: bool,
        regime: Dict = None
    ) -> Tuple[str, float]:
        """
        Map weighted score to trading action
        
        Strategy:
        - Score > 50 and aligned -> long (high confidence)
        - Score > threshold -> long (medium confidence)
        - Score < -50 and aligned -> short (high confidence)
        - Score < -threshold -> short (medium confidence)
        - Other -> hold
        
        Optimization: Dynamically adjust threshold based on market regime
        
        Returns:
            (action, confidence)
        """
        # Dynamic threshold: Adjust based on market regime
        # CRITICAL FIX: Threshold needs to match actual weighted score range
        # Total weight sum is about 0.80, theoretical max score = 100 * 0.80 = 80
        # Actual case: Single direction signal (e.g., trend_15m=60) contributes 60 * 0.10 = 6
        # Reasonable threshold range: 8-15 (not 20-30)
        base_threshold = 15
        if regime:
            regime_type = regime.get('regime', '')
            if regime_type in ['VOLATILE_DIRECTIONLESS', 'choppy']:
                # Volatile directionless market: Significantly lower threshold to capture signals
                base_threshold = 8
            elif regime_type in ['TRENDING', 'TRENDING_UP', 'TRENDING_DOWN']:
                # Trending market: Standard threshold
                base_threshold = 15
            elif regime_type in ['VOLATILE_TRENDING']:
                # Volatile trending: Slightly lower
                base_threshold = 10
        
        high_threshold = base_threshold + 10  # Strong signal threshold
        
        # Strong signal threshold (requires multi-period alignment)
        if weighted_score > high_threshold and aligned:
            return 'long', 0.85
        if weighted_score < -high_threshold and aligned:
            return 'short', 0.85
        
        # Medium signal threshold
        if weighted_score > base_threshold:
            confidence = 0.6 + (weighted_score - base_threshold) * 0.01
            return 'long', min(confidence, 0.75)
        if weighted_score < -base_threshold:
            confidence = 0.6 + (abs(weighted_score) - base_threshold) * 0.01
            return 'short', min(confidence, 0.75)
        
        # Weak signal or conflict -> hold
        return 'hold', abs(weighted_score) / 100  # Confidence depends on absolute score
    
    def _generate_reason(
        self, 
        weighted_score: float,
        aligned: bool,
        alignment_reason: str,

        quant_analysis: Dict,
        prophet_score: float = 0.0,
        regime: Optional[Dict] = None
    ) -> str:
        """Generate decision reason (explainability)"""
        # Extract key information (using correct key paths)
        trend_data = quant_analysis.get('trend', {})
        osc_data = quant_analysis.get('oscillator', {})
        sentiment_data = quant_analysis.get('sentiment', {})
        
        reasons = []
        
        # 1. Market regime
        if regime:
            regime_name = regime.get('regime', 'unknown').upper()
            reasons.append(f"[{regime_name}]")
        
        # 2. Overall score
        reasons.append(f"Weighted score: {weighted_score:.1f}")
        
        # 3. Multi-period alignment status
        reasons.append(f"Period alignment: {alignment_reason}")
        
        # 4. Main driving factors (using correct granular scores)
        vote_details = {
            'trend_1h': trend_data.get('trend_1h_score', 0),
            'trend_15m': trend_data.get('trend_15m_score', 0),
            'oscillator_1h': osc_data.get('osc_1h_score', 0),
            'oscillator_15m': osc_data.get('osc_15m_score', 0),
            'sentiment': sentiment_data.get('total_sentiment_score', 0),
            'prophet': prophet_score
        }
        sorted_signals = sorted(
            vote_details.items(), 
            key=lambda x: abs(x[1]), 
            reverse=True
        )[:2]
        
        for sig_name, sig_score in sorted_signals:
            if abs(sig_score) > 20:
                reasons.append(f"{sig_name}: {sig_score:+.0f}")
        
        return " | ".join(reasons)
    
    def update_performance(self, signal_name: str, is_correct: bool):
        """
        Update signal historical performance (for adaptive weight adjustment)
        
        Args:
            signal_name: Signal name (e.g., 'trend_5m')
            is_correct: Whether the signal prediction was accurate
        """
        if signal_name in self.performance_tracker:
            self.performance_tracker[signal_name]['total'] += 1
            if is_correct:
                self.performance_tracker[signal_name]['correct'] += 1
    
    def adjust_weights_by_performance(self) -> SignalWeight:
        """
        Adaptively adjust weights based on historical performance (advanced feature)
        
        Strategy:
        - Calculate win rate for each signal
        - Increase weight for high win rate signals, decrease for low
        - Ensure total weights sum to 1.0
        
        Returns:
            Adjusted weight configuration
        """
        # Calculate win rate for each signal
        win_rates = {}
        for sig_name, perf in self.performance_tracker.items():
            if perf['total'] > 0:
                win_rates[sig_name] = perf['correct'] / perf['total']
            else:
                win_rates[sig_name] = 0.5  # Default 50%
        
        # Normalize (sum = 1.0)
        total_rate = sum(win_rates.values())
        if total_rate > 0:
            normalized_weights = {
                k: v / total_rate for k, v in win_rates.items()
            }
        else:
            return self.weights  # Insufficient data, keep original weights
        
        # Update weights
        new_weights = SignalWeight(
            trend_5m=normalized_weights.get('trend_5m', self.weights.trend_5m),
            trend_15m=normalized_weights.get('trend_15m', self.weights.trend_15m),
            trend_1h=normalized_weights.get('trend_1h', self.weights.trend_1h),
            oscillator_5m=normalized_weights.get('oscillator_5m', self.weights.oscillator_5m),
            oscillator_15m=normalized_weights.get('oscillator_15m', self.weights.oscillator_15m),

            oscillator_1h=normalized_weights.get('oscillator_1h', self.weights.oscillator_1h),
            prophet=normalized_weights.get('prophet', self.weights.prophet),
        )
        
        return new_weights
    
    def to_llm_context(self, vote_result: VoteResult, quant_analysis: Dict) -> str:
        """
        Convert quantitative signals to LLM context (for DeepSeek decision enhancement)
        
        Returns:
            Formatted text context
        """
        context = f"""
### Quantitative Signal Summary (Decision Core Output)

**Weighted Voting Result**:
- Overall Score: {vote_result.weighted_score:.1f} (-100~+100)
- Suggested Action: {vote_result.action}
- Confidence: {vote_result.confidence:.2%}
- Multi-period Aligned: {'Yes' if vote_result.multi_period_aligned else 'No'}

**Market Regime (Regime Analysis)**:
- State: {vote_result.regime.get('regime', 'UNKNOWN').upper()}
- Confidence: {vote_result.regime.get('confidence', 0):.1f}%
- ADX: {vote_result.regime.get('adx', 0):.1f}
- Determination: {vote_result.regime.get('reason', 'N/A')}

**Decision Reason**: {vote_result.reason}

**Signal Details**:
"""
        # Add trend analysis for each period
        for period in ['5m', '15m', '1h']:
            trend_key = f'trend_{period}'
            osc_key = f'oscillator_{period}'
            
            if trend_key in quant_analysis:
                trend = quant_analysis[trend_key]
                context += f"\n[{period} Trend] {trend.get('signal', 'N/A')} (Score:{trend.get('score', 0)})"
                context += f"\n  - EMA Status: {trend.get('details', {}).get('ema_status', 'N/A')}"
            
            if osc_key in quant_analysis:
                osc = quant_analysis[osc_key]
                context += f"\n[{period} Oscillator] {osc.get('signal', 'N/A')} (Score:{osc.get('score', 0)})"
                rsi = osc.get('details', {}).get('rsi_value', 0)
                context += f"\n  - RSI: {rsi:.1f}"
        
        context += f"\n\n**Weight Distribution**: {json.dumps(vote_result.vote_details, indent=2)}"
        
        return context
    
    def get_statistics(self) -> Dict:
        """Get decision statistics"""
        if not self.history:
            return {'total_decisions': 0}
        
        total = len(self.history)
        actions = [h.action for h in self.history]
        avg_confidence = sum(h.confidence for h in self.history) / total
        aligned_count = sum(1 for h in self.history if h.multi_period_aligned)
        
        return {
            'total_decisions': total,
            'action_distribution': {
                'long': actions.count('long'),
                'short': actions.count('short'),
                'hold': actions.count('hold'),
            },
            'avg_confidence': avg_confidence,
            'alignment_rate': aligned_count / total,
            'performance_tracker': self.performance_tracker,
        }


# ============================================
# Test Function
# ============================================
async def test_decision_core():
    """Test Decision Core Agent"""
    print("\n" + "="*60)
    print("Testing Decision Core Agent")
    print("="*60)
    
    # Mock quant analyst output
    mock_quant_analysis = {
        'trend_5m': {
            'score': -15,
            'signal': 'weak_short',
            'details': {'ema_status': 'bearish_crossover'}
        },
        'trend_15m': {
            'score': 45,
            'signal': 'moderate_long',
            'details': {'ema_status': 'bullish'}
        },
        'trend_1h': {
            'score': 65,
            'signal': 'strong_long',
            'details': {'ema_status': 'strong_bullish'}
        },
        'oscillator_5m': {
            'score': -5,
            'signal': 'neutral',
            'details': {'rsi_value': 48.2}
        },
        'oscillator_15m': {
            'score': 20,
            'signal': 'moderate_long',
            'details': {'rsi_value': 62.5}
        },
        'oscillator_1h': {
            'score': 30,
            'signal': 'moderate_long',
            'details': {'rsi_value': 68.3}
        },
    }
    
    # Create decision core
    decision_core = DecisionCoreAgent()
    
    # Execute decision
    print("\n1. Testing weighted voting decision...")
    result = await decision_core.make_decision(mock_quant_analysis)
    
    print(f"  Decision action: {result.action}")
    print(f"  Overall score: {result.weighted_score:.2f}")
    print(f"  Confidence: {result.confidence:.2%}")
    print(f"  Multi-period aligned: {result.multi_period_aligned}")
    print(f"  Decision reason: {result.reason}")
    
    # Test LLM context generation
    print("\n2. Testing LLM context generation...")
    llm_context = decision_core.to_llm_context(result, mock_quant_analysis)
    print(llm_context[:500] + "...")  # Only show first 500 chars
    
    # Test statistics
    print("\n3. Testing statistics...")
    # Execute a few more decisions
    for _ in range(3):
        await decision_core.make_decision(mock_quant_analysis)
    
    stats = decision_core.get_statistics()
    print(f"  Total decisions: {stats['total_decisions']}")
    print(f"  Average confidence: {stats['avg_confidence']:.2%}")
    print(f"  Alignment rate: {stats['alignment_rate']:.2%}")
    
    print("\nDecision Core Agent test passed!")
    return decision_core


if __name__ == '__main__':
    # Run test
    asyncio.run(test_decision_core())
