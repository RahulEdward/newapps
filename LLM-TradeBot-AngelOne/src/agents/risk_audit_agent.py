"""
👮 Risk Guardian (The Guardian) Agent
===========================================

Responsibilities:
1. Stop-loss direction auto-correction - Detect and correct fatal errors like long stop > entry, short stop < entry
2. Capital simulation - Simulate order execution, verify margin sufficiency, position compliance
3. Veto power - Block high-risk decisions directly (e.g., reverse position opening)
4. Physical isolation execution - Run independently, not dependent on other Agent states
5. Audit logging - Record all blocked events and risk control decisions

Author: AI Trader Team
Date: 2025-12-19
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from src.utils.logger import log


class RiskLevel(Enum):
    """Risk level"""
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    FATAL = "fatal"


@dataclass
class RiskCheckResult:
    """Risk check result"""
    passed: bool  # Whether passed
    risk_level: RiskLevel
    blocked_reason: Optional[str] = None  # Block reason (if not passed)
    corrections: Optional[Dict] = None  # Auto-correction content
    warnings: List[str] = None  # Warning messages


@dataclass
class PositionInfo:
    """Position information"""
    symbol: str
    side: str  # 'long' or 'short'
    entry_price: float
    quantity: float
    unrealized_pnl: float


class RiskAuditAgent:
    """
    Risk Guardian (The Guardian)
    
    Core functions:
    - Stop-loss direction auto-correction: Long stop must be < entry, short stop must be > entry
    - Capital simulation: Simulate order execution, verify margin sufficiency
    - Veto power: Block high-risk decisions (e.g., reverse position, over-leverage)
    - Physical isolation: Run independently, not dependent on other Agents
    """
    
    def __init__(
        self, 
        max_leverage: float = 10.0,
        max_position_pct: float = 0.3,  # Max single position ratio (30%)
        max_total_risk_pct: float = 0.02,  # Max total risk exposure (2%)
        min_stop_loss_pct: float = 0.005,  # Min stop-loss distance (0.5%)
        max_stop_loss_pct: float = 0.05,  # Max stop-loss distance (5%)
    ):
        """
        Initialize Risk Guardian (The Guardian)
        
        Args:
            max_leverage: Maximum leverage multiplier
            max_position_pct: Max single position ratio to total capital
            max_total_risk_pct: Max total risk exposure ratio to total capital
            min_stop_loss_pct: Min stop-loss distance (prevent stop hunting)
            max_stop_loss_pct: Max stop-loss distance (prevent excessive loss)
        """
        self.max_leverage = max_leverage
        self.max_position_pct = max_position_pct
        self.max_total_risk_pct = max_total_risk_pct
        self.min_stop_loss_pct = min_stop_loss_pct
        self.max_stop_loss_pct = max_stop_loss_pct
        
        # Audit log
        self.audit_log: List[Dict] = []
        
        # Block statistics
        self.block_stats = {
            'total_checks': 0,
            'total_blocks': 0,
            'stop_loss_corrections': 0,
            'reverse_position_blocks': 0,
            'insufficient_margin_blocks': 0,
            'over_leverage_blocks': 0,
        }
        log.info("👮 The Guardian initialized")
    
    async def audit_decision(
        self,
        decision: Dict,
        current_position: Optional[PositionInfo],
        account_balance: float,
        current_price: float,
        atr_pct: float = None  # New: ATR percentage for dynamic stop-loss calculation
    ) -> RiskCheckResult:
        """
        Perform risk audit on decision (main entry point)
        
        Args:
            decision: Output from The Critic (Adversarial Commentator)
                {
                    'action': 'long/short/close_long/close_short/hold',
                    'entry_price': 100000.0,
                    'stop_loss': 99000.0,
                    'take_profit': 102000.0,
                    'quantity': 0.01,  # BTC quantity
                    'leverage': 5.0,
                    'confidence': 0.75
                }
            current_position: Current position info (None means no position)
            account_balance: Account available balance (USDT)
            current_price: Current market price
            atr_pct: ATR percentage (e.g., 2.5 means 2.5%);
                     Used for dynamic stop-loss calculation, defaults to 2% if not provided
            
        Returns:
            RiskCheckResult object
        """
        self.block_stats['total_checks'] += 1
        warnings = []
        corrections = {}
        
        action = decision.get('action', 'hold')
        
        # 0. If hold, pass directly
        if action == 'hold':
            return RiskCheckResult(
                passed=True,
                risk_level=RiskLevel.SAFE,
                warnings=['Observing']
            )

        # 0.1 Adversarial data extraction (Market Awareness)
        regime = decision.get('regime')
        position = decision.get('position')
        confidence = decision.get('confidence', 0)
        
        # 0.2 Market regime block (Regime Filter)
        if regime:
            r_type = regime.get('regime')
            if r_type == 'unknown':
                return self._block_decision('total_blocks', "Market regime unclear, position opening suspended")
            if r_type == 'volatile':
                return self._block_decision('total_blocks', f"High volatility market (ATR {regime.get('atr_pct', 0):.2f}%), risk control blocked")
            if r_type == 'choppy' and confidence < 80:
                return self._block_decision('total_blocks', f"Ranging market with insufficient confidence ({confidence:.1f} < 80), position opening blocked")

        # 0.3 Price position block (Position Filter)
        if position:
            pos_pct = position.get('position_pct', 50)
            location = position.get('location')
            if location == 'middle' or 40 <= pos_pct <= 60:
                return self._block_decision('total_blocks', f"Price in middle of range ({pos_pct:.1f}%), poor R/R, position opening prohibited")
            
            if action == 'long' and pos_pct > 70:
                return self._block_decision('total_blocks', f"Long position too high ({pos_pct:.1f}%), pullback risk exists")
            
            if action == 'short' and pos_pct < 30:
                return self._block_decision('total_blocks', f"Short position too low ({pos_pct:.1f}%), bounce risk exists")

        # 0.4 Risk/Reward ratio hard check (R/R Ratio)
        entry_price = decision.get('entry_price', current_price)
        stop_loss = decision.get('stop_loss')
        take_profit = decision.get('take_profit')
        if entry_price and stop_loss and take_profit:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            if risk > 0:
                rr_ratio = reward / risk
                if rr_ratio < 1.5:
                    return self._block_decision('total_blocks', f"Risk/reward ratio insufficient ({rr_ratio:.2f} < 1.5)")
        
        # 1. [VETO] Check reverse position opening
        if current_position:
            # 1.1 Check duplicate position opening (Duplicate Open Block)
            duplicated_check = self._check_duplicate_open(action, current_position)
            if not duplicated_check['passed']:
                return self._block_decision(
                    'total_blocks',
                    duplicated_check['reason']
                )
            
            # 1.2 Check reverse position opening
            reverse_check = self._check_reverse_position(action, current_position)
            if not reverse_check['passed']:
                return self._block_decision(
                    'reverse_position_blocks',
                    reverse_check['reason']
                )
        
        # 2. [FATAL CORRECTION] Stop-loss direction check
        if action in ['long', 'short']:
            stop_loss_check = self._check_and_fix_stop_loss(
                action=action,
                entry_price=decision.get('entry_price', current_price),
                stop_loss=decision.get('stop_loss'),
                current_price=current_price,
                atr_pct=atr_pct  # Pass ATR for dynamic calculation
            )
            
            if not stop_loss_check['passed']:
                if stop_loss_check['can_fix']:
                    # Auto-correct
                    corrections['stop_loss'] = stop_loss_check['corrected_value']
                    warnings.append(f"⚠️ Stop-loss direction error corrected: {decision.get('stop_loss')} -> {stop_loss_check['corrected_value']}")
                    self.block_stats['stop_loss_corrections'] += 1
                else:
                    # Cannot fix, block
                    return self._block_decision(
                        'stop_loss_corrections',
                        stop_loss_check['reason']
                    )
        
        # 3. [CAPITAL SIMULATION] Margin check
        margin_check = self._check_margin_sufficiency(
            action=action,
            entry_price=decision.get('entry_price', current_price),
            quantity=decision.get('quantity', 0),
            leverage=decision.get('leverage', 1.0),
            account_balance=account_balance
        )
        
        if not margin_check['passed']:
            return self._block_decision(
                'insufficient_margin_blocks',
                margin_check['reason']
            )
        
        # 4. [LEVERAGE CHECK] Prevent over-leverage
        leverage = decision.get('leverage', 1.0)
        if leverage > self.max_leverage:
            return self._block_decision(
                'over_leverage_blocks',
                f"Leverage {leverage}x exceeds max limit {self.max_leverage}x"
            )
        
        # 5. [POSITION CHECK] Single position ratio
        position_check = self._check_position_size(
            quantity=decision.get('quantity', 0),
            entry_price=decision.get('entry_price', current_price),
            account_balance=account_balance
        )
        
        if not position_check['passed']:
            warnings.append(f"⚠️ {position_check['reason']}")
        
        # 6. [RISK EXPOSURE] Total risk check
        risk_check = self._check_total_risk_exposure(
            action=action,
            entry_price=decision.get('entry_price', current_price),
            stop_loss=corrections.get('stop_loss', decision.get('stop_loss')),
            quantity=decision.get('quantity', 0),
            account_balance=account_balance
        )
        
        if not risk_check['passed']:
            warnings.append(f"⚠️ {risk_check['reason']}")
        
        # 7. Comprehensive risk level evaluation
        risk_level = self._evaluate_risk_level(
            len(warnings),
            decision.get('confidence', 0),
            leverage
        )
        
        # 8. Record audit log
        # log.guardian(f"Audit passed: {action.upper()} (Confidence: {confidence:.1f}%)")
        self._log_audit(
            decision=decision,
            result='PASSED',
            corrections=corrections,
            warnings=warnings
        )
        
        return RiskCheckResult(
            passed=True,
            risk_level=risk_level,
            corrections=corrections if corrections else None,
            warnings=warnings if warnings else None
        )
    
    
    def _check_duplicate_open(
        self,
        action: str,
        current_position: PositionInfo
    ) -> Dict:
        """
        Check for duplicate position opening (Single Position Rule)
        
        Rule: If already holding a position for the same symbol, prohibit opening again (long/short).
        Only allow close/add/reduce related operations (currently only single position supported)
        """
        if action in ['long', 'open_long', 'short', 'open_short']:
            # Any open action with existing position -> block
            return {
                'passed': False,
                'reason': f"[Single Position Limit] Currently holding {current_position.side} position, duplicate {action} prohibited"
            }
        
        return {'passed': True}
    
    def _check_reverse_position(
        self, 
        action: str, 
        current_position: PositionInfo
    ) -> Dict:
        """
        Check for reverse position opening attempt (fatal error)
        
        Example: Already have long position, attempting to open short
        """
        if action == 'long' and current_position.side == 'short':
            return {
                'passed': False,
                'reason': f"[FATAL RISK] Opening {action} while holding {current_position.side} position prohibited"
            }
        
        if action == 'short' and current_position.side == 'long':
            return {
                'passed': False,
                'reason': f"[FATAL RISK] Opening {action} while holding {current_position.side} position prohibited"
            }
        
        return {'passed': True}
    
    def _check_and_fix_stop_loss(
        self,
        action: str,
        entry_price: float,
        stop_loss: Optional[float],
        current_price: float,
        atr_pct: float = None  # New ATR parameter
    ) -> Dict:
        """
        Check and correct stop-loss direction (core function - ATR enhanced version)
        
        Rules:
        - Long: Stop-loss must be < entry price
        - Short: Stop-loss must be > entry price
        
        ATR dynamic calculation:
        - If atr_pct provided, use 1.5 * ATR as stop-loss distance
        - Keep min/max stop-loss limits as boundaries
        
        Returns:
            {
                'passed': bool,
                'can_fix': bool,
                'corrected_value': float,
                'reason': str
            }
        """
        # Calculate dynamic stop-loss distance
        # Priority: ATR -> default 2%
        if atr_pct and atr_pct > 0:
            # Use 1.5 * ATR as stop-loss distance (common strategy)
            dynamic_stop_pct = min(max(atr_pct * 1.5 / 100, self.min_stop_loss_pct), self.max_stop_loss_pct)
            log.debug(f"📊 ATR-based stop: ATR={atr_pct:.2f}%, dynamic_stop={dynamic_stop_pct:.2%}")
        else:
            # No ATR data, use default 2%
            dynamic_stop_pct = 0.02
        
        if not stop_loss:
            # No stop-loss set, use dynamic stop-loss distance
            default_stop = (
                entry_price * (1 - dynamic_stop_pct) if action == 'long' 
                else entry_price * (1 + dynamic_stop_pct)
            )
            return {
                'passed': False,
                'can_fix': True,
                'corrected_value': default_stop,
                'reason': f"No stop-loss set, using dynamic stop (ATR-based {dynamic_stop_pct:.1%}): {default_stop:.2f}"
            }
        
        # Long check
        if action == 'long':
            if stop_loss >= entry_price:
                # Stop-loss direction error, use dynamic stop correction
                corrected = entry_price * (1 - dynamic_stop_pct)
                return {
                    'passed': False,
                    'can_fix': True,
                    'corrected_value': corrected,
                    'reason': f"Long stop-loss {stop_loss} >= entry {entry_price}, ATR corrected to {corrected:.2f}"
                }
            
            # Check if stop-loss distance is reasonable
            stop_distance_pct = abs(entry_price - stop_loss) / entry_price
            if stop_distance_pct < self.min_stop_loss_pct:
                corrected = entry_price * (1 - max(dynamic_stop_pct, self.min_stop_loss_pct))
                return {
                    'passed': False,
                    'can_fix': True,
                    'corrected_value': corrected,
                    'reason': f"Stop-loss distance too small ({stop_distance_pct:.2%}), adjusted to {max(dynamic_stop_pct, self.min_stop_loss_pct):.2%}"
                }
            
            if stop_distance_pct > self.max_stop_loss_pct:
                corrected = entry_price * (1 - self.max_stop_loss_pct)
                return {
                    'passed': False,
                    'can_fix': True,
                    'corrected_value': corrected,
                    'reason': f"Stop-loss distance too large ({stop_distance_pct:.2%}), adjusted to {self.max_stop_loss_pct:.2%}"
                }
        
        # Short check
        if action == 'short':
            if stop_loss <= entry_price:
                # Stop-loss direction error, use dynamic stop correction
                corrected = entry_price * (1 + dynamic_stop_pct)
                return {
                    'passed': False,
                    'can_fix': True,
                    'corrected_value': corrected,
                    'reason': f"Short stop-loss {stop_loss} <= entry {entry_price}, ATR corrected to {corrected:.2f}"
                }
            
            # Check stop-loss distance
            stop_distance_pct = abs(stop_loss - entry_price) / entry_price
            if stop_distance_pct < self.min_stop_loss_pct:
                corrected = entry_price * (1 + max(dynamic_stop_pct, self.min_stop_loss_pct))
                return {
                    'passed': False,
                    'can_fix': True,
                    'corrected_value': corrected,
                    'reason': f"Stop-loss distance too small ({stop_distance_pct:.2%}), adjusted to {max(dynamic_stop_pct, self.min_stop_loss_pct):.2%}"
                }
            
            if stop_distance_pct > self.max_stop_loss_pct:
                corrected = entry_price * (1 + self.max_stop_loss_pct)
                return {
                    'passed': False,
                    'can_fix': True,
                    'corrected_value': corrected,
                    'reason': f"Stop-loss distance too large ({stop_distance_pct:.2%}), adjusted to {self.max_stop_loss_pct:.2%}"
                }
        
        return {'passed': True}
    
    def _check_margin_sufficiency(
        self,
        action: str,
        entry_price: float,
        quantity: float,
        leverage: float,
        account_balance: float
    ) -> Dict:
        """
        Capital simulation: Check if margin is sufficient
        
        Formula:
        Required margin = (Quantity * Entry Price) / Leverage
        """
        if action in ['close_long', 'close_short', 'hold']:
            return {'passed': True}
        
        required_margin = (quantity * entry_price) / leverage
        
        # Reserve 5% buffer
        if required_margin > account_balance * 0.95:
            return {
                'passed': False,
                'reason': f"Insufficient margin: Need {required_margin:.2f} USDT, Available {account_balance:.2f} USDT"
            }
        
        return {'passed': True, 'required_margin': required_margin}
    
    def _check_position_size(
        self,
        quantity: float,
        entry_price: float,
        account_balance: float
    ) -> Dict:
        """
        Check if single position ratio exceeds limit
        
        Position value = Quantity * Price
        Ratio = Position value / Account balance
        """
        position_value = quantity * entry_price
        position_pct = position_value / account_balance
        
        if position_pct > self.max_position_pct:
            return {
                'passed': False,
                'reason': f"Single position ratio {position_pct:.2%} exceeds limit {self.max_position_pct:.2%}"
            }
        
        return {'passed': True}
    
    def _check_total_risk_exposure(
        self,
        action: str,
        entry_price: float,
        stop_loss: Optional[float],
        quantity: float,
        account_balance: float
    ) -> Dict:
        """
        Check total risk exposure (maximum possible loss)
        
        Risk exposure = |Entry price - Stop-loss| * Quantity
        Risk ratio = Risk exposure / Account balance
        """
        if not stop_loss or action in ['close_long', 'close_short', 'hold']:
            return {'passed': True}
        
        risk_exposure = abs(entry_price - stop_loss) * quantity
        risk_pct = risk_exposure / account_balance
        
        if risk_pct > self.max_total_risk_pct:
            return {
                'passed': False,
                'reason': f"Risk exposure {risk_pct:.2%} exceeds limit {self.max_total_risk_pct:.2%}"
            }
        
        return {'passed': True}
    
    def _evaluate_risk_level(
        self,
        warning_count: int,
        confidence: float,
        leverage: float
    ) -> RiskLevel:
        """Comprehensive risk level evaluation"""
        if warning_count >= 3 or leverage > 8:
            return RiskLevel.DANGER
        elif warning_count >= 1 or leverage > 5:
            return RiskLevel.WARNING
        elif confidence > 0.7:
            return RiskLevel.SAFE
        else:
            return RiskLevel.WARNING
    
    def _block_decision(self, stat_key: str, reason: str) -> RiskCheckResult:
        """Block decision and record"""
        self.block_stats['total_blocks'] += 1
        self.block_stats[stat_key] += 1
        
        # log.guardian(f"Decision blocked: {reason}", blocked=True)
        
        self._log_audit(
            decision={'blocked': True},
            result='BLOCKED',
            corrections=None,
            warnings=[reason]
        )
        
        return RiskCheckResult(
            passed=False,
            risk_level=RiskLevel.FATAL,
            blocked_reason=reason
        )
    
    def _log_audit(
        self,
        decision: Dict,
        result: str,
        corrections: Optional[Dict],
        warnings: List[str]
    ):
        """Record audit log"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'decision': decision,
            'result': result,
            'corrections': corrections,
            'warnings': warnings,
        }
        self.audit_log.append(log_entry)
        
        # Keep last 1000 records
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]
    
    def get_audit_report(self) -> Dict:
        """Generate audit report"""
        return {
            'total_checks': self.block_stats['total_checks'],
            'total_blocks': self.block_stats['total_blocks'],
            'block_rate': (
                self.block_stats['total_blocks'] / self.block_stats['total_checks']
                if self.block_stats['total_checks'] > 0 else 0
            ),
            'block_breakdown': {
                'stop_loss_corrections': self.block_stats['stop_loss_corrections'],
                'reverse_position_blocks': self.block_stats['reverse_position_blocks'],
                'insufficient_margin_blocks': self.block_stats['insufficient_margin_blocks'],
                'over_leverage_blocks': self.block_stats['over_leverage_blocks'],
            },
            'recent_logs': self.audit_log[-10:]  # Last 10 logs
        }


# ============================================
# Test Functions
# ============================================
async def test_risk_audit():
    """Test Risk Audit Agent"""
    print("\n" + "="*60)
    print("🧪 Testing Risk Audit Agent")
    print("="*60)
    
    # Initialize
    risk_agent = RiskAuditAgent(
        max_leverage=10.0,
        max_position_pct=0.3,
        min_stop_loss_pct=0.005,
        max_stop_loss_pct=0.05
    )
    
    # Test 1: Long stop-loss direction correction
    print("\n1️⃣ Testing long stop-loss direction correction...")
    decision_1 = {
        'action': 'long',
        'entry_price': 100000.0,
        'stop_loss': 100500.0,  # ❌ Error: Long stop > entry
        'quantity': 0.01,
        'leverage': 5.0,
        'confidence': 0.75
    }
    
    result_1 = await risk_agent.audit_decision(
        decision=decision_1,
        current_position=None,
        account_balance=10000.0,
        current_price=100000.0
    )
    
    print(f"  Result: {'✅ Passed' if result_1.passed else '❌ Blocked'}")
    if result_1.warnings:
        for w in result_1.warnings:
            print(f"  {w}")
    
    # Test 2: Short stop-loss direction correction
    print("\n2️⃣ Testing short stop-loss direction correction...")
    decision_2 = {
        'action': 'short',
        'entry_price': 100000.0,
        'stop_loss': 99500.0,  # ❌ Error: Short stop < entry
        'quantity': 0.01,
        'leverage': 5.0,
        'confidence': 0.75
    }
    
    result_2 = await risk_agent.audit_decision(
        decision=decision_2,
        current_position=None,
        account_balance=10000.0,
        current_price=100000.0
    )
    
    print(f"  Result: {'✅ Passed' if result_2.passed else '❌ Blocked'}")
    if result_2.corrections:
        print(f"  Corrections: {result_2.corrections}")
    
    # Test 3: Reverse position block
    print("\n3️⃣ Testing reverse position block...")
    current_pos = PositionInfo(
        symbol='BTCUSDT',
        side='long',
        entry_price=99000.0,
        quantity=0.01,
        unrealized_pnl=100.0
    )
    
    decision_3 = {
        'action': 'short',  # ❌ Error: Already have long, trying to open short
        'entry_price': 100000.0,
        'stop_loss': 101000.0,
        'quantity': 0.01,
        'leverage': 5.0,
        'confidence': 0.75
    }
    
    result_3 = await risk_agent.audit_decision(
        decision=decision_3,
        current_position=current_pos,
        account_balance=10000.0,
        current_price=100000.0
    )
    
    print(f"  Result: {'✅ Passed' if result_3.passed else '❌ Blocked'}")
    if result_3.blocked_reason:
        print(f"  Block reason: {result_3.blocked_reason}")
    
    # Test 4: Insufficient margin block
    print("\n4️⃣ Testing insufficient margin block...")
    decision_4 = {
        'action': 'long',
        'entry_price': 100000.0,
        'stop_loss': 98000.0,
        'quantity': 0.5,  # ❌ Quantity too large, insufficient margin
        'leverage': 2.0,
        'confidence': 0.75
    }
    
    result_4 = await risk_agent.audit_decision(
        decision=decision_4,
        current_position=None,
        account_balance=10000.0,
        current_price=100000.0
    )
    
    print(f"  Result: {'✅ Passed' if result_4.passed else '❌ Blocked'}")
    if result_4.blocked_reason:
        print(f"  Block reason: {result_4.blocked_reason}")
    
    # Generate audit report
    print("\n5️⃣ Audit Report...")
    report = risk_agent.get_audit_report()
    print(f"  Total checks: {report['total_checks']}")
    print(f"  Total blocks: {report['total_blocks']}")
    print(f"  Block rate: {report['block_rate']:.2%}")
    print(f"  Stop-loss corrections: {report['block_breakdown']['stop_loss_corrections']}")
    print(f"  Reverse position blocks: {report['block_breakdown']['reverse_position_blocks']}")
    
    print("\n✅ Risk Audit Agent test passed!")
    return risk_agent


if __name__ == '__main__':
    asyncio.run(test_risk_audit())
