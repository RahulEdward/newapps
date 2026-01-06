"""
Decision Validator
Validates legality and safety of LLM decisions
"""

from typing import Dict, List, Tuple, Optional
from src.utils.logger import log


class DecisionValidator:
    """
    Decision Validator
    
    Validation Rules:
    1. Required field check
    2. Numeric range check
    3. Stop loss direction check
    4. Risk-reward ratio check
    5. Numeric format check
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Default configuration
        self.max_leverage = self.config.get('max_leverage', 5)
        self.max_position_pct = self.config.get('max_position_pct', 30.0)
        self.min_confidence = self.config.get('min_confidence', 0)
        self.max_confidence = self.config.get('max_confidence', 100)
        self.min_risk_reward_ratio = self.config.get('min_risk_reward_ratio', 2.0)
        
    def validate(self, decision: Dict) -> Tuple[bool, List[str]]:
        """
        Validate decision
        
        Args:
            decision: Decision dictionary
            
        Returns:
            (is_valid, errors)
            - is_valid: Whether validation passed
            - errors: List of errors
        """
        errors = []
        
        # 1. Required field check (all action types need these)
        required_fields = ['symbol', 'action', 'reasoning']
        for field in required_fields:
            if field not in decision:
                errors.append(f"Missing required field: {field}")
        
        # If basic fields missing, return immediately
        if errors:
            return False, errors
        
        # 2. Action validity check
        valid_actions = [
            'open_long', 'open_short', 
            'close_long', 'close_short', 
            'close_position',
            'hold', 'wait'
        ]
        if decision['action'] not in valid_actions:
            errors.append(f"Invalid action: {decision['action']}")
        
        # 3. Confidence check (if exists)
        if 'confidence' in decision:
            confidence = decision.get('confidence', 0)
            if not (self.min_confidence <= confidence <= self.max_confidence):
                errors.append(f"confidence out of range [{self.min_confidence}, {self.max_confidence}]: {confidence}")
        
        # 4. Format validation (all fields)
        format_errors = self._validate_format(decision)
        errors.extend(format_errors)
        
        # 5. Additional checks for open position actions
        if decision['action'] in ['open_long', 'open_short']:
            # 5.1 Required fields for opening position
            open_required = ['leverage', 'position_size_usd', 'stop_loss', 'take_profit']
            for field in open_required:
                if field not in decision or decision[field] is None:
                    errors.append(f"Open position action missing required field: {field}")
            
            # If missing open position fields, skip subsequent checks
            if any('Open position action missing required field' in e for e in errors):
                return False, errors
            
            # 5.2 Leverage range check
            leverage = decision.get('leverage', 1)
            if not (1 <= leverage <= self.max_leverage):
                errors.append(f"leverage out of range [1, {self.max_leverage}]: {leverage}")
            
            # 5.3 Position size check (if has position_size_pct)
            if 'position_size_pct' in decision:
                position_pct = decision['position_size_pct']
                if not (0 <= position_pct <= self.max_position_pct):
                    errors.append(f"position_size_pct out of range [0, {self.max_position_pct}]: {position_pct}")
            
            # 5.4 Numeric format check (cannot be string formula)
            numeric_fields = ['leverage', 'position_size_usd', 'stop_loss', 'take_profit', 'risk_usd']
            for field in numeric_fields:
                if field in decision:
                    value = decision[field]
                    if isinstance(value, str):
                        errors.append(f"{field} cannot be string (may contain formula): {value}")
                    elif not isinstance(value, (int, float)):
                        errors.append(f"{field} must be a number: {value}")
            
            # 5.5 Stop loss direction check
            if not self.validate_stop_loss_direction(decision):
                action = decision['action']
                entry = decision.get('entry_price', decision.get('current_price', 0))
                stop_loss = decision.get('stop_loss', 0)
                if action == 'open_long':
                    errors.append(f"Long stop loss direction error: stop_loss ({stop_loss}) must be < entry_price ({entry})")
                elif action == 'open_short':
                    errors.append(f"Short stop loss direction error: stop_loss ({stop_loss}) must be > entry_price ({entry})")
            
            # 5.6 Risk-reward ratio check
            if not self.validate_risk_reward_ratio(decision):
                ratio = self.calculate_risk_reward_ratio(decision)
                errors.append(f"Insufficient risk-reward ratio: {ratio:.2f} < {self.min_risk_reward_ratio}")
        
        return len(errors) == 0, errors
    
    def _validate_format(self, decision: Dict) -> List[str]:
        """
        Validate numeric format
        
        Check rules:
        1. Prohibit range symbol ~
        2. Prohibit thousands separator ,
        
        Args:
            decision: Decision dictionary
            
        Returns:
            List of errors
        """
        errors = []
        
        for key, value in decision.items():
            if isinstance(value, str):
                # Check range symbol
                if '~' in value:
                    errors.append(f"Field {key} contains prohibited range symbol '~': {value}")
                
                # Check thousands separator (in numeric context)
                import re
                if re.match(r'^\d{1,3}(,\d{3})+(\.\d+)?$', value):
                    errors.append(f"Field {key} contains prohibited thousands separator ',': {value}")
        
        return errors
    
    def validate_stop_loss_direction(self, decision: Dict) -> bool:
        """
        Validate stop loss direction
        
        Rules:
        - Long: stop_loss < entry_price
        - Short: stop_loss > entry_price
        
        Args:
            decision: Decision dictionary
            
        Returns:
            True if valid, False otherwise
        """
        action = decision.get('action')
        
        # Only check open position actions
        if action not in ['open_long', 'open_short']:
            return True
        
        # Get prices
        entry_price = decision.get('entry_price') or decision.get('current_price')
        stop_loss = decision.get('stop_loss')
        
        # If missing price info, cannot validate
        if entry_price is None or stop_loss is None:
            return True
        
        # Validate direction
        if action == 'open_long':
            return stop_loss < entry_price
        elif action == 'open_short':
            return stop_loss > entry_price
        
        return True
    
    def validate_risk_reward_ratio(self, decision: Dict) -> bool:
        """
        Validate risk-reward ratio
        
        Requirement: (take_profit - entry) / (entry - stop_loss) >= min_ratio
        
        Args:
            decision: Decision dictionary
            
        Returns:
            True if valid, False otherwise
        """
        ratio = self.calculate_risk_reward_ratio(decision)
        
        if ratio is None:
            return True  # Don't block when cannot calculate
        
        return ratio >= self.min_risk_reward_ratio
    
    def calculate_risk_reward_ratio(self, decision: Dict) -> Optional[float]:
        """
        Calculate risk-reward ratio
        
        Args:
            decision: Decision dictionary
            
        Returns:
            Risk-reward ratio, None if cannot calculate
        """
        action = decision.get('action')
        
        # Only calculate for open position actions
        if action not in ['open_long', 'open_short']:
            return None
        
        # Get prices
        entry_price = decision.get('entry_price') or decision.get('current_price')
        stop_loss = decision.get('stop_loss')
        take_profit = decision.get('take_profit')
        
        # If missing price info, cannot calculate
        if None in [entry_price, stop_loss, take_profit]:
            return None
        
        # Calculate risk and reward
        if action == 'open_long':
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
        elif action == 'open_short':
            risk = abs(stop_loss - entry_price)
            reward = abs(entry_price - take_profit)
        else:
            return None
        
        # Avoid division by zero
        if risk == 0:
            return None
        
        return reward / risk
    
    def get_validation_summary(self, decision: Dict) -> str:
        """
        Get validation summary (for logging)
        
        Args:
            decision: Decision dictionary
            
        Returns:
            Validation summary string
        """
        is_valid, errors = self.validate(decision)
        
        if is_valid:
            summary = f"Decision validation passed: {decision.get('action', 'unknown')}"
            
            # Add key information
            if decision.get('action') in ['open_long', 'open_short']:
                ratio = self.calculate_risk_reward_ratio(decision)
                if ratio:
                    summary += f", risk-reward ratio: {ratio:.2f}"
        else:
            summary = f"Decision validation failed: {len(errors)} errors\n"
            for i, error in enumerate(errors, 1):
                summary += f"  {i}. {error}\n"
        
        return summary


# Test code
if __name__ == '__main__':
    validator = DecisionValidator()
    
    # Test case 1: Valid long decision
    test1 = {
        'symbol': 'BTCUSDT',
        'action': 'open_long',
        'confidence': 75,
        'leverage': 2,
        'position_size_usd': 200.0,
        'entry_price': 86000.0,
        'stop_loss': 84710.0,  # Correct: below entry price
        'take_profit': 88580.0,  # Correct: above entry price
        'risk_usd': 30.0,
        'reasoning': 'Test reasoning'
    }
    
    is_valid, errors = validator.validate(test1)
    print("Test 1 - Valid long decision:")
    print(f"  Validation result: {'Passed' if is_valid else 'Failed'}")
    if errors:
        print(f"  Errors: {errors}")
    ratio = validator.calculate_risk_reward_ratio(test1)
    print(f"  Risk-reward ratio: {ratio:.2f}")
    print()
    
    # Test case 2: Stop loss direction error
    test2 = {
        'symbol': 'BTCUSDT',
        'action': 'open_long',
        'confidence': 75,
        'leverage': 2,
        'position_size_usd': 200.0,
        'entry_price': 86000.0,
        'stop_loss': 87000.0,  # Error: above entry price
        'take_profit': 88580.0,
        'risk_usd': 30.0,
        'reasoning': 'Test reasoning'
    }
    
    is_valid, errors = validator.validate(test2)
    print("Test 2 - Stop loss direction error:")
    print(f"  Validation result: {'Passed' if is_valid else 'Failed'}")
    if errors:
        print(f"  Errors: {errors}")
    print()
    
    # Test case 3: Insufficient risk-reward ratio
    test3 = {
        'symbol': 'BTCUSDT',
        'action': 'open_long',
        'confidence': 75,
        'leverage': 2,
        'position_size_usd': 200.0,
        'entry_price': 86000.0,
        'stop_loss': 84000.0,
        'take_profit': 87000.0,  # Risk-reward ratio = 1000/2000 = 0.5 < 2.0
        'risk_usd': 30.0,
        'reasoning': 'Test reasoning'
    }
    
    is_valid, errors = validator.validate(test3)
    print("Test 3 - Insufficient risk-reward ratio:")
    print(f"  Validation result: {'Passed' if is_valid else 'Failed'}")
    if errors:
        print(f"  Errors: {errors}")
    ratio = validator.calculate_risk_reward_ratio(test3)
    print(f"  Risk-reward ratio: {ratio:.2f}")
