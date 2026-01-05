"""
Position Analyzer Module
Calculate current price position within recent range, used to filter low-quality trades
"""

import pandas as pd
from typing import Dict, Tuple
from enum import Enum


class PriceLocation(Enum):
    """Price location classification"""
    SUPPORT = "support"      # Near support (0-20%)
    LOWER = "lower"          # Lower zone (20-40%)
    MIDDLE = "middle"        # Middle zone (40-60%)
    UPPER = "upper"          # Upper zone (60-80%)
    RESISTANCE = "resistance"  # Near resistance (80-100%)


class PositionQuality(Enum):
    """Position quality rating"""
    EXCELLENT = "excellent"  # Excellent (support/resistance)
    GOOD = "good"           # Good (lower/upper zone)
    POOR = "poor"           # Poor (near middle)
    TERRIBLE = "terrible"   # Terrible (middle zone)


class PositionAnalyzer:
    """
    Position Awareness Analyzer
    
    Core functions:
    1. Calculate price position percentage within recent range
    2. Determine position quality
    3. Provide position opening recommendations (allow long/short)
    
    Core principles:
    - Only go long near support
    - Only go short near resistance
    - Prohibit opening positions in middle zone (40-60%)
    """
    
    def __init__(self, 
                 lookback_4h: int = 48,   # 4-hour range (48 5-minute candles)
                 lookback_1d: int = 288):  # 1-day range (288 5-minute candles)
        """
        Initialize position analyzer
        
        Args:
            lookback_4h: Number of candles for 4-hour range
            lookback_1d: Number of candles for 1-day range
        """
        self.lookback_4h = lookback_4h
        self.lookback_1d = lookback_1d
        
    def analyze_position(self, 
                        df: pd.DataFrame, 
                        current_price: float,
                        timeframe: str = '5m') -> Dict:
        """
        Analyze price position
        
        Args:
            df: Candlestick data (must contain 'high' and 'low' columns)
            current_price: Current price
            timeframe: Time period (used to determine lookback)
            
        Returns:
            {
                'range_high': float,        # Range high price
                'range_low': float,         # Range low price
                'range_size': float,        # Range size
                'position_pct': float,      # Position percentage (0-100)
                'location': PriceLocation,  # Location classification
                'quality': PositionQuality, # Quality rating
                'allow_long': bool,         # Allow long position
                'allow_short': bool,        # Allow short position
                'reason': str               # Analysis reason
            }
        """
        
        # 1. Determine lookback period
        if timeframe == '5m':
            lookback = self.lookback_4h  # 4 hours
        elif timeframe == '15m':
            lookback = self.lookback_4h // 3  # About 4 hours
        elif timeframe == '1h':
            lookback = self.lookback_4h // 12  # About 4 hours
        else:
            lookback = self.lookback_4h
        
        # Ensure sufficient data
        lookback = min(lookback, len(df))
        
        # 2. Calculate range high/low
        recent_data = df.tail(lookback)
        range_high = recent_data['high'].max()
        range_low = recent_data['low'].min()
        range_size = range_high - range_low
        
        # 3. Calculate position percentage
        if range_size == 0:
            # Range is 0 (rare), return neutral
            position_pct = 50.0
        else:
            position_pct = ((current_price - range_low) / range_size) * 100
            position_pct = max(0, min(100, position_pct))  # Limit to 0-100
        
        # 4. Determine location classification
        location = self._classify_location(position_pct)
        
        # 5. Determine quality rating
        quality = self._classify_quality(position_pct)
        
        # 6. Determine if position opening is allowed
        allow_long, allow_short = self._check_allow_trade(position_pct, location)
        
        # 7. Generate analysis reason
        reason = self._generate_reason(position_pct, location, quality, range_high, range_low)
        
        return {
            'range_high': range_high,
            'range_low': range_low,
            'range_size': range_size,
            'position_pct': position_pct,
            'location': location.value,
            'quality': quality.value,
            'allow_long': allow_long,
            'allow_short': allow_short,
            'reason': reason
        }
    
    def _classify_location(self, position_pct: float) -> PriceLocation:
        """
        Classify price location
        
        Args:
            position_pct: Position percentage
            
        Returns:
            PriceLocation
        """
        if position_pct <= 20:
            return PriceLocation.SUPPORT
        elif position_pct <= 40:
            return PriceLocation.LOWER
        elif position_pct <= 60:
            return PriceLocation.MIDDLE
        elif position_pct <= 80:
            return PriceLocation.UPPER
        else:
            return PriceLocation.RESISTANCE
    
    def _classify_quality(self, position_pct: float) -> PositionQuality:
        """
        Evaluate position quality
        
        Args:
            position_pct: Position percentage
            
        Returns:
            PositionQuality
        """
        if position_pct <= 15 or position_pct >= 85:
            # Very close to support/resistance
            return PositionQuality.EXCELLENT
        elif position_pct <= 30 or position_pct >= 70:
            # Close to support/resistance
            return PositionQuality.GOOD
        elif 45 <= position_pct <= 55:
            # Right in the middle of range
            return PositionQuality.TERRIBLE
        else:
            # Other (near middle)
            return PositionQuality.POOR
    
    def _check_allow_trade(self, 
                          position_pct: float, 
                          location: PriceLocation) -> Tuple[bool, bool]:
        """
        Check if position opening is allowed
        
        Rules:
        - Long: Only at support and lower zone (0-40%)
        - Short: Only at resistance and upper zone (60-100%)
        - Middle zone (40-60%): Prohibit any position opening
        
        Args:
            position_pct: Position percentage
            location: Location classification
            
        Returns:
            (allow_long, allow_short)
        """
        # Middle zone: Prohibit any position opening
        if 40 <= position_pct <= 60:
            return False, False
        
        # Long: Only in lower half
        allow_long = position_pct < 60
        
        # Short: Only in upper half
        allow_short = position_pct > 40
        
        return allow_long, allow_short
    
    def _generate_reason(self, 
                        position_pct: float,
                        location: PriceLocation,
                        quality: PositionQuality,
                        range_high: float,
                        range_low: float) -> str:
        """
        Generate analysis reason
        
        Args:
            position_pct: Position percentage
            location: Location classification
            quality: Quality rating
            range_high: Range high price
            range_low: Range low price
            
        Returns:
            Reason description
        """
        location_desc = {
            PriceLocation.SUPPORT: "near support",
            PriceLocation.LOWER: "lower zone",
            PriceLocation.MIDDLE: "middle zone",
            PriceLocation.UPPER: "upper zone",
            PriceLocation.RESISTANCE: "near resistance"
        }
        
        quality_desc = {
            PositionQuality.EXCELLENT: "excellent",
            PositionQuality.GOOD: "good",
            PositionQuality.POOR: "poor",
            PositionQuality.TERRIBLE: "terrible"
        }
        
        reason = f"Price position: {position_pct:.1f}% ({location_desc[location]}), "
        reason += f"Quality: {quality_desc[quality]}, "
        reason += f"Range: ${range_low:.2f} - ${range_high:.2f}"
        
        return reason


# Test code
if __name__ == '__main__':
    import numpy as np
    
    # Create test data
    dates = pd.date_range('2025-01-01', periods=100, freq='5min')
    prices = 87000 + np.cumsum(np.random.randn(100) * 50)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'high': prices + np.random.rand(100) * 20,
        'low': prices - np.random.rand(100) * 20,
        'close': prices
    })
    
    analyzer = PositionAnalyzer()
    
    # Test different positions
    test_prices = [
        (df['low'].min() + 50, "Near support"),
        ((df['high'].max() + df['low'].min()) / 2, "Middle zone"),
        (df['high'].max() - 50, "Near resistance")
    ]
    
    print("Position Analysis Test:\n")
    for price, desc in test_prices:
        result = analyzer.analyze_position(df, price)
        print(f"{desc}:")
        print(f"  Price: ${price:.2f}")
        print(f"  Position: {result['position_pct']:.1f}%")
        print(f"  Classification: {result['location']}")
        print(f"  Quality: {result['quality']}")
        print(f"  Allow long: {result['allow_long']}")
        print(f"  Allow short: {result['allow_short']}")
        print(f"  Reason: {result['reason']}")
        print()
