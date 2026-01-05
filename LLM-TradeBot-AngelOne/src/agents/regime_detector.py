"""
Market Regime Detector
Identifies whether the market is in trending/ranging/high volatility state
"""

import pandas as pd
import numpy as np
from typing import Dict
from enum import Enum


class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING_UP = "trending_up"       # Clear uptrend
    TRENDING_DOWN = "trending_down"   # Clear downtrend
    CHOPPY = "choppy"                 # Ranging market (garbage time)
    VOLATILE = "volatile"             # High volatility (dangerous)
    VOLATILE_DIRECTIONLESS = "volatile_directionless"  # High ADX but unclear direction (whipsaw)
    UNKNOWN = "unknown"               # Cannot determine


class RegimeDetector:
    """
    Market Regime Detector
    
    Core functions:
    1. Use ADX to determine trend strength
    2. Use Bollinger Band width to determine volatility
    3. Use ATR to determine risk level
    4. Comprehensive market regime determination
    
    Decision rules:
    - CHOPPY (ranging): Prohibit chasing momentum, only range trading
    - VOLATILE (high volatility): Prohibit opening positions or reduce leverage
    - UNKNOWN (cannot determine): Force observation mode
    """
    
    def __init__(self,
                 adx_trend_threshold: float = 25.0,    # ADX > 25 = trending
                 adx_choppy_threshold: float = 20.0,   # ADX < 20 = ranging
                 bb_width_volatile_ratio: float = 1.5,  # BB width > 1.5x average = high volatility
                 atr_high_threshold: float = 2.0):      # ATR% > 2% = high volatility
        """
        Initialize Market Regime Detector
        
        Args:
            adx_trend_threshold: ADX trend threshold
            adx_choppy_threshold: ADX ranging threshold
            bb_width_volatile_ratio: Bollinger Band width volatility ratio
            atr_high_threshold: ATR high volatility threshold (percentage)
        """
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_choppy_threshold = adx_choppy_threshold
        self.bb_width_volatile_ratio = bb_width_volatile_ratio
        self.atr_high_threshold = atr_high_threshold
    
    def detect_regime(self, df: pd.DataFrame) -> Dict:
        """
        Detect market regime
        
        Args:
            df: Candlestick data (must include technical indicators)
            
        Returns:
            {
                'regime': MarketRegime,
                'confidence': float,  # 0-100
                'adx': float,
                'bb_width_pct': float,
                'atr_pct': float,
                'trend_direction': str,  # 'up', 'down', 'neutral'
                'reason': str
            }
        """
        
        # 1. Calculate ADX (if not present, calculate it)
        adx = self._get_or_calculate_adx(df)
        
        # 2. Calculate Bollinger Band width percentage
        bb_width_pct = self._calculate_bb_width_pct(df)
        
        # 3. Calculate ATR percentage
        atr_pct = self._calculate_atr_pct(df)
        
        # 4. Determine trend direction
        trend_direction = self._detect_trend_direction(df)
        
        # 5. Comprehensive market regime determination
        regime, confidence, reason = self._classify_regime(
            adx, bb_width_pct, atr_pct, trend_direction, df
        )
        
        # ✅ Sanity Checks: Clip values to valid ranges and handle NaN
        def safe_clip(val, min_val, max_val, default=0.0):
            """Clip value to range, handle NaN/None/inf"""
            if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                return default
            return max(min_val, min(max_val, float(val)))
        
        confidence = safe_clip(confidence, 0, 100, 50.0)
        adx = safe_clip(adx, 0, 100, 20.0)
        bb_width_pct = safe_clip(bb_width_pct, 0, 50, 2.0)
        atr_pct = safe_clip(atr_pct, 0, 20, 0.5)
        
        # 6. CHOPPY-specific analysis (Range Trading Intelligence)
        choppy_analysis = None
        if regime == MarketRegime.CHOPPY:
            choppy_analysis = self._analyze_choppy_market(df, bb_width_pct)
        
        return {
            'regime': regime.value,
            'confidence': confidence,
            'adx': adx,
            'bb_width_pct': bb_width_pct,
            'atr_pct': atr_pct,
            'trend_direction': trend_direction,
            'reason': reason,
            'position': self._calculate_price_position(df),
            'choppy_analysis': choppy_analysis  # CHOPPY-specific insights
        }
    
    def _get_or_calculate_adx(self, df: pd.DataFrame) -> float:
        """
        Get or calculate ADX
        
        ADX (Average Directional Index) measures trend strength
        - ADX > 25: Strong trend
        - ADX < 20: Weak trend/ranging
        """
        # If ADX column exists, use it directly
        if 'adx' in df.columns:
            return df['adx'].iloc[-1]
        
        # Otherwise use simplified calculation (EMA difference as proxy)
        if 'ema_12' in df.columns and 'ema_26' in df.columns:
            ema_diff = abs(df['ema_12'].iloc[-1] - df['ema_26'].iloc[-1])
            price = df['close'].iloc[-1]
            adx_proxy = (ema_diff / price) * 100 * 10  # Convert to ADX-like value
            return adx_proxy
        
        # Cannot calculate, return neutral value
        return 20.0
    
    def _calculate_bb_width_pct(self, df: pd.DataFrame) -> float:
        """
        Calculate Bollinger Band width percentage
        
        Width = (Upper - Lower) / Middle * 100
        """
        if 'bb_upper' in df.columns and 'bb_lower' in df.columns and 'bb_middle' in df.columns:
            upper = df['bb_upper'].iloc[-1]
            lower = df['bb_lower'].iloc[-1]
            middle = df['bb_middle'].iloc[-1]
            
            if middle > 0:
                width_pct = ((upper - lower) / middle) * 100
                return width_pct
        
        # Cannot calculate, return default value
        return 2.0
    
    def _calculate_atr_pct(self, df: pd.DataFrame) -> float:
        """
        Calculate ATR percentage
        
        ATR% = ATR / Current Price * 100
        """
        if 'atr' in df.columns:
            atr = df['atr'].iloc[-1]
            price = df['close'].iloc[-1]
            
            if price > 0:
                atr_pct = (atr / price) * 100
                return atr_pct
        
        # Cannot calculate, return default value
        return 0.5
    
    def _detect_trend_direction(self, df: pd.DataFrame) -> str:
        """
        Detect trend direction
        
        Uses SMA20 and SMA50 for determination
        """
        if 'sma_20' in df.columns and 'sma_50' in df.columns:
            sma20 = df['sma_20'].iloc[-1]
            sma50 = df['sma_50'].iloc[-1]
            price = df['close'].iloc[-1]
            
            # Price and moving average relationship
            if price > sma20 > sma50:
                return 'up'
            elif price < sma20 < sma50:
                return 'down'
        
        return 'neutral'
    
    def _classify_regime(self, 
                        adx: float,
                        bb_width_pct: float,
                        atr_pct: float,
                        trend_direction: str,
                        df: pd.DataFrame = None) -> tuple:
        """
        Comprehensive market regime classification (Enhanced with TSS)
        
        Returns:
            (regime, confidence, reason)
        """
        
        # 1. High volatility detection (highest priority)
        if atr_pct > self.atr_high_threshold:
            return (
                MarketRegime.VOLATILE,
                80.0,
                f"High volatility market (ATR {atr_pct:.2f}% > {self.atr_high_threshold}%)"
            )

        # 2. Calculate Trend Strength Score (TSS)
        # TSS Components:
        # - ADX (0-100): Weight 40%
        # - EMA Alignment (Boolean): Weight 30%
        # - MACD Pulse (Boolean): Weight 30%
        
        tss = 0
        tss_details = []
        
        # Component A: ADX
        if adx > 25:
            tss += 40
            tss_details.append("ADX>25(+40)")
        elif adx > 20:
            tss += 20
            tss_details.append("ADX>20(+20)")
            
        # Component B: EMA Alignment
        if trend_direction in ['up', 'down']:
            tss += 30
            tss_details.append("EMA_Aligned(+30)")
            
        # Component C: MACD Momentum (if available)
        macd_aligned = False
        if df is not None and 'macd' in df.columns and 'macd_signal' in df.columns:
            macd = df['macd'].iloc[-1]
            signal = df['macd_signal'].iloc[-1]
            if (trend_direction == 'up' and macd > signal > 0) or \
               (trend_direction == 'down' and macd < signal < 0):
                tss += 30
                tss_details.append("MACD_Momentum(+30)")
                macd_aligned = True
        
        # 3. Classify based on TSS
        if tss >= 70: # Strong Trend (e.g. ADX>25 + EMA)
             if trend_direction == 'up':
                 return (MarketRegime.TRENDING_UP, 85.0, f"Strong uptrend (TSS:{tss} - {','.join(tss_details)})")
             elif trend_direction == 'down':
                 return (MarketRegime.TRENDING_DOWN, 85.0, f"Strong downtrend (TSS:{tss} - {','.join(tss_details)})")
        
        elif tss >= 30: # Weak Trend
             if trend_direction == 'up':
                 return (MarketRegime.TRENDING_UP, 60.0, f"Weak uptrend (TSS:{tss} - {','.join(tss_details)})")
             elif trend_direction == 'down':
                 return (MarketRegime.TRENDING_DOWN, 60.0, f"Weak downtrend (TSS:{tss} - {','.join(tss_details)})")
             
        # 4. Fallback to Choppy/Volatile
        if adx < self.adx_choppy_threshold:
            return (
                MarketRegime.CHOPPY,
                70.0,
                f"Ranging market (ADX {adx:.1f} < {self.adx_choppy_threshold})"
            )
            
        # 5. ADX high but no alignment -> Volatile Directionless
        return (
            MarketRegime.VOLATILE_DIRECTIONLESS,
            65.0,
            f"Direction unclear (ADX {adx:.1f} but trend not aligned)"
        )
    
    def _calculate_price_position(self, df: pd.DataFrame, lookback: int = 50) -> Dict:
        """
        Calculate price position within recent range
        
        Returns:
            {
                'position_pct': float,  # 0-100, 0=lowest, 100=highest
                'location': str  # 'low', 'middle', 'high'
            }
        """
        try:
            if len(df) < lookback:
                lookback = len(df)
            
            recent_high = df['high'].iloc[-lookback:].max()
            recent_low = df['low'].iloc[-lookback:].min()
            current_price = df['close'].iloc[-1]
            
            if recent_high == recent_low:
                position_pct = 50.0
            else:
                position_pct = ((current_price - recent_low) / (recent_high - recent_low)) * 100
            
            # Clip to 0-100
            position_pct = max(0, min(100, position_pct))
            
            # Determine location
            if position_pct <= 25:
                location = 'low'
            elif position_pct >= 75:
                location = 'high'
            else:
                location = 'middle'
            
            return {
                'position_pct': position_pct,
                'location': location
            }
        except Exception:
            return {'position_pct': 50.0, 'location': 'unknown'}

    def _analyze_choppy_market(self, df: pd.DataFrame, current_bb_width: float, lookback: int = 20) -> Dict:
        """
        CHOPPY market specific analysis
        
        Provides key information for range trading and breakout alerts:
        1. Squeeze detection (Bollinger Band narrowing)
        2. Support/resistance identification
        3. Breakout probability assessment
        4. Mean reversion opportunities
        
        Returns:
            {
                'squeeze_active': bool,          # Whether in squeeze state
                'squeeze_intensity': float,      # Squeeze intensity 0-100
                'range': {                       # Range information
                    'support': float,
                    'resistance': float,
                    'range_pct': float           # Range width as percentage of price
                },
                'breakout_probability': float,   # Breakout probability 0-100
                'breakout_direction': str,       # Likely breakout direction 'up', 'down', 'unknown'
                'mean_reversion_signal': str,    # 'buy_dip', 'sell_rally', 'neutral'
                'consolidation_bars': int,       # Consecutive ranging candle count
                'strategy_hint': str             # Strategy suggestion
            }
        """
        try:
            # 1. Squeeze detection - BB width narrowing relative to historical values
            squeeze_active = False
            squeeze_intensity = 0.0
            
            if 'bb_upper' in df.columns and 'bb_lower' in df.columns and 'bb_middle' in df.columns:
                # Calculate historical BB width
                bb_widths = ((df['bb_upper'] - df['bb_lower']) / df['bb_middle'] * 100).iloc[-lookback:]
                avg_width = bb_widths.mean()
                min_width = bb_widths.min()
                
                # Current width vs average width
                if avg_width > 0:
                    width_ratio = current_bb_width / avg_width
                    if width_ratio < 0.7:  # Width below 70% of average = Squeeze
                        squeeze_active = True
                        squeeze_intensity = (1 - width_ratio) * 100  # 0-100
            
            # 2. Support/resistance identification
            recent_high = df['high'].iloc[-lookback:].max()
            recent_low = df['low'].iloc[-lookback:].min()
            current_price = df['close'].iloc[-1]
            
            range_pct = ((recent_high - recent_low) / current_price) * 100 if current_price > 0 else 0
            
            # 3. Price position and mean reversion signal
            position_pct = ((current_price - recent_low) / (recent_high - recent_low) * 100) if (recent_high - recent_low) > 0 else 50
            
            if position_pct <= 20:
                mean_reversion_signal = 'buy_dip'
            elif position_pct >= 80:
                mean_reversion_signal = 'sell_rally'
            else:
                mean_reversion_signal = 'neutral'
            
            # 4. Breakout probability assessment
            breakout_probability = 0.0
            breakout_direction = 'unknown'
            
            # Squeeze + price near boundary = high breakout probability
            if squeeze_active:
                breakout_probability += squeeze_intensity * 0.5  # Max 50 from squeeze
                
                # Price near boundary increases probability
                if position_pct >= 85:
                    breakout_probability += 30
                    breakout_direction = 'up'
                elif position_pct <= 15:
                    breakout_probability += 30
                    breakout_direction = 'down'
                else:
                    breakout_probability += 10
            
            # Volume anomaly detection increases probability
            if 'volume' in df.columns:
                recent_vol = df['volume'].iloc[-5:].mean()
                avg_vol = df['volume'].iloc[-lookback:].mean()
                if recent_vol > avg_vol * 1.5:
                    breakout_probability += 20
            
            breakout_probability = min(100, breakout_probability)
            
            # 5. Consecutive ranging candle count (for detecting end of consolidation)
            consolidation_bars = 0
            for i in range(1, min(50, len(df))):
                idx = -i
                bar_range = (df['high'].iloc[idx] - df['low'].iloc[idx]) / df['close'].iloc[idx] * 100
                if bar_range < 1.5:  # Volatility below 1.5% considered ranging
                    consolidation_bars += 1
                else:
                    break
            
            # 6. Strategy suggestion
            if squeeze_active and breakout_probability >= 60:
                if breakout_direction == 'up':
                    strategy_hint = "SQUEEZE_BREAKOUT_LONG: Prepare for upside breakout, set alerts at resistance"
                elif breakout_direction == 'down':
                    strategy_hint = "SQUEEZE_BREAKOUT_SHORT: Prepare for downside breakout, set alerts at support"
                else:
                    strategy_hint = "SQUEEZE_IMMINENT: Volatility expansion expected, wait for direction confirmation"
            elif mean_reversion_signal == 'buy_dip':
                strategy_hint = "MEAN_REVERSION_LONG: Price near support, consider long with tight stop below support"
            elif mean_reversion_signal == 'sell_rally':
                strategy_hint = "MEAN_REVERSION_SHORT: Price near resistance, consider short with tight stop above resistance"
            else:
                strategy_hint = "RANGE_WAIT: No clear edge, wait for price to reach range extremes"
            
            return {
                'squeeze_active': squeeze_active,
                'squeeze_intensity': min(100, max(0, squeeze_intensity)),
                'range': {
                    'support': recent_low,
                    'resistance': recent_high,
                    'range_pct': min(20, max(0, range_pct))
                },
                'breakout_probability': breakout_probability,
                'breakout_direction': breakout_direction,
                'mean_reversion_signal': mean_reversion_signal,
                'consolidation_bars': consolidation_bars,
                'strategy_hint': strategy_hint
            }
            
        except Exception as e:
            return {
                'squeeze_active': False,
                'squeeze_intensity': 0,
                'range': {'support': 0, 'resistance': 0, 'range_pct': 0},
                'breakout_probability': 0,
                'breakout_direction': 'unknown',
                'mean_reversion_signal': 'neutral',
                'consolidation_bars': 0,
                'strategy_hint': 'ANALYSIS_ERROR: Unable to analyze choppy market'
            }


# Test code
if __name__ == '__main__':
    # Create test data
    dates = pd.date_range('2025-01-01', periods=100, freq='5min')
    
    # Simulate uptrend
    uptrend_prices = 87000 + np.cumsum(np.random.randn(100) * 10 + 5)
    
    df_uptrend = pd.DataFrame({
        'timestamp': dates,
        'close': uptrend_prices,
        'high': uptrend_prices + 50,
        'low': uptrend_prices - 50,
        'sma_20': uptrend_prices - 100,
        'sma_50': uptrend_prices - 200,
        'ema_12': uptrend_prices - 50,
        'ema_26': uptrend_prices - 150,
        'atr': np.full(100, 100),
        'bb_upper': uptrend_prices + 200,
        'bb_middle': uptrend_prices,
        'bb_lower': uptrend_prices - 200
    })
    
    # Simulate ranging market
    choppy_prices = 87000 + np.random.randn(100) * 50
    
    df_choppy = pd.DataFrame({
        'timestamp': dates,
        'close': choppy_prices,
        'high': choppy_prices + 30,
        'low': choppy_prices - 30,
        'sma_20': np.full(100, 87000),
        'sma_50': np.full(100, 87000),
        'ema_12': choppy_prices,
        'ema_26': choppy_prices,
        'atr': np.full(100, 50),
        'bb_upper': choppy_prices + 100,
        'bb_middle': choppy_prices,
        'bb_lower': choppy_prices - 100
    })
    
    detector = RegimeDetector()
    
    print("Market Regime Detection Test:\n")
    
    print("1. Uptrend Test:")
    result = detector.detect_regime(df_uptrend)
    print(f"   Regime: {result['regime']}")
    print(f"   Confidence: {result['confidence']:.1f}%")
    print(f"   ADX: {result['adx']:.1f}")
    print(f"   Trend direction: {result['trend_direction']}")
    print(f"   Reason: {result['reason']}")
    print()
    
    print("2. Ranging Market Test:")
    result = detector.detect_regime(df_choppy)
    print(f"   Regime: {result['regime']}")
    print(f"   Confidence: {result['confidence']:.1f}%")
    print(f"   ADX: {result['adx']:.1f}")
    print(f"   Trend direction: {result['trend_direction']}")
    print(f"   Reason: {result['reason']}")
