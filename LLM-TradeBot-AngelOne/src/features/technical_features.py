"""
Technical Feature Engineering Module

Build advanced features based on Step2 technical indicators for:
1. Enhanced decision-making in rule-based strategies
2. Machine learning model training
3. LLM context input

Design Principles:
- Input: 31 columns of technical indicators from Step2
- Output: 50+ columns of advanced features
- All features have clear financial meaning
- Avoid data leakage (no future data used)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from src.utils.logger import log


class TechnicalFeatureEngineer:
    """Technical Feature Engineer"""
    
    # Feature version (for tracking feature definition changes)
    FEATURE_VERSION = 'v1.0'
    
    def __init__(self):
        self.feature_count = 0
        self.feature_names = []
    
    def build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build advanced features based on technical indicators
        
        Args:
            df: DataFrame output from Step2 (with technical indicators)
            
        Returns:
            Extended DataFrame (original columns + new feature columns)
            
        Feature Categories:
        1. Price relative position features (8)
        2. Trend strength features (10)
        3. Momentum features (8)
        4. Volatility features (8)
        5. Volume features (8)
        6. Multi-indicator composite features (8)
        """
        log.info(f"Starting feature engineering: original columns={len(df.columns)}")
        
        # Copy data to avoid modifying original DataFrame
        df_features = df.copy()
        
        # 1. Price relative position features
        df_features = self._build_price_position_features(df_features)
        
        # 2. Trend strength features
        df_features = self._build_trend_strength_features(df_features)
        
        # 3. Momentum features
        df_features = self._build_momentum_features(df_features)
        
        # 4. Volatility features
        df_features = self._build_volatility_features(df_features)
        
        # 5. Volume features
        df_features = self._build_volume_features(df_features)
        
        # 6. Multi-indicator composite features
        df_features = self._build_composite_features(df_features)
        
        # Record feature information
        new_features = set(df_features.columns) - set(df.columns)
        self.feature_count = len(new_features)
        self.feature_names = sorted(list(new_features))
        
        log.info(
            f"Feature engineering complete: new features={self.feature_count}, "
            f"total columns={len(df_features.columns)}"
        )
        
        # Add feature metadata
        df_features.attrs['feature_version'] = self.FEATURE_VERSION
        df_features.attrs['feature_count'] = self.feature_count
        df_features.attrs['feature_names'] = self.feature_names
        
        return df_features
    
    def _build_price_position_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build price relative position features
        
        Financial meaning: Measure current price position relative to various technical reference points
        """
        # 1. Price position relative to moving averages
        df['price_to_sma20_pct'] = ((df['close'] - df['sma_20']) / df['sma_20'] * 100)
        df['price_to_sma50_pct'] = ((df['close'] - df['sma_50']) / df['sma_50'] * 100)
        df['price_to_ema12_pct'] = ((df['close'] - df['ema_12']) / df['ema_12'] * 100)
        df['price_to_ema26_pct'] = ((df['close'] - df['ema_26']) / df['ema_26'] * 100)
        
        # 2. Price position within Bollinger Bands (0-100, 50 is middle)
        df['bb_position'] = np.where(
            (df['bb_upper'] - df['bb_lower']) > 0,
            (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower']) * 100,
            50  # When BB width is 0, consider it at middle
        )
        
        # 3. Price deviation from VWAP
        df['price_to_vwap_pct'] = np.where(
            df['vwap'] > 0,
            (df['close'] - df['vwap']) / df['vwap'] * 100,
            0
        )
        
        # 4. Current price position relative to recent candlestick high/low
        df['price_to_recent_high_pct'] = (
            (df['close'] - df['high'].rolling(20).max()) / 
            df['high'].rolling(20).max() * 100
        )
        df['price_to_recent_low_pct'] = (
            (df['close'] - df['low'].rolling(20).min()) / 
            df['low'].rolling(20).min() * 100
        )
        
        return df
    
    def _build_trend_strength_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build trend strength features
        
        Financial meaning: Measure market trend strength and direction
        """
        # 1. EMA cross strength (distance between fast and slow lines)
        df['ema_cross_strength'] = (df['ema_12'] - df['ema_26']) / df['close'] * 100
        
        # 2. SMA cross strength
        df['sma_cross_strength'] = (df['sma_20'] - df['sma_50']) / df['close'] * 100
        
        # 3. MACD momentum (current MACD compared to historical)
        df['macd_momentum_5'] = df['macd'] - df['macd'].shift(5)
        df['macd_momentum_10'] = df['macd'] - df['macd'].shift(10)
        
        # 4. Trend alignment (whether EMA and SMA are in same direction)
        df['trend_alignment'] = np.where(
            (df['ema_cross_strength'] > 0) & (df['sma_cross_strength'] > 0),
            1,  # Double bullish
            np.where(
                (df['ema_cross_strength'] < 0) & (df['sma_cross_strength'] < 0),
                -1,  # Double bearish
                0  # Direction inconsistent
            )
        )
        
        # 5. Price trend slope (linear regression slope)
        def calc_slope(series):
            if len(series) < 2:
                return 0
            x = np.arange(len(series))
            try:
                slope = np.polyfit(x, series, 1)[0]
                return slope / series.iloc[-1] * 100 if series.iloc[-1] != 0 else 0
            except:
                return 0
        
        df['price_slope_5'] = df['close'].rolling(5).apply(calc_slope, raw=False)
        df['price_slope_10'] = df['close'].rolling(10).apply(calc_slope, raw=False)
        df['price_slope_20'] = df['close'].rolling(20).apply(calc_slope, raw=False)
        
        # 6. ADX alternative indicator: directional strength
        # Use price change direction consistency to measure trend strength
        df['directional_strength'] = (
            df['close'].diff().rolling(14).apply(
                lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 50,
                raw=False
            )
        )
        
        return df
    
    def _build_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build momentum features
        
        Financial meaning: Measure speed and acceleration of price changes
        """
        # 1. RSI momentum (rate of change of RSI)
        df['rsi_momentum_5'] = df['rsi'] - df['rsi'].shift(5)
        df['rsi_momentum_10'] = df['rsi'] - df['rsi'].shift(10)
        
        # 2. RSI zone (discretized)
        df['rsi_zone'] = pd.cut(
            df['rsi'],
            bins=[0, 30, 40, 60, 70, 100],
            labels=['oversold', 'weak', 'neutral', 'strong', 'overbought']
        )
        # Convert to numeric (for calculations)
        df['rsi_zone_numeric'] = pd.cut(
            df['rsi'],
            bins=[0, 30, 40, 60, 70, 100],
            labels=[-2, -1, 0, 1, 2]
        ).astype(float)
        
        # 3. Price momentum (multi-period returns)
        df['return_1'] = df['close'].pct_change(1) * 100
        df['return_5'] = df['close'].pct_change(5) * 100
        df['return_10'] = df['close'].pct_change(10) * 100
        df['return_20'] = df['close'].pct_change(20) * 100
        
        # 4. Momentum acceleration (change in returns)
        df['momentum_acceleration'] = df['return_5'] - df['return_5'].shift(5)
        
        return df
    
    def _build_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build volatility features
        
        Financial meaning: Measure market volatility and risk
        """
        # 1. ATR normalized (volatility relative to price)
        df['atr_normalized'] = df['atr'] / df['close'] * 100
        
        # 2. Bollinger Band width change
        df['bb_width_change'] = df['bb_width'] - df['bb_width'].shift(5)
        df['bb_width_pct_change'] = df['bb_width'].pct_change(5) * 100
        
        # 3. Historical volatility (multi-period standard deviation)
        df['volatility_5'] = df['close'].pct_change().rolling(5).std() * 100 * np.sqrt(5)
        df['volatility_10'] = df['close'].pct_change().rolling(10).std() * 100 * np.sqrt(10)
        df['volatility_20'] = df['close'].pct_change().rolling(20).std() * 100 * np.sqrt(20)
        
        # 4. High-low range trend
        df['hl_range_ma5'] = df['high_low_range'].rolling(5).mean()
        df['hl_range_expansion'] = df['high_low_range'] / df['hl_range_ma5']
        
        return df
    
    def _build_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build volume features
        
        Financial meaning: Measure market participation and capital flow
        """
        # 1. Volume trend
        df['volume_trend_5'] = df['volume'].rolling(5).mean() / df['volume_sma']
        df['volume_trend_10'] = df['volume'].rolling(10).mean() / df['volume_sma']
        
        # 2. Volume change rate
        df['volume_change_pct'] = df['volume'].pct_change() * 100
        df['volume_acceleration'] = df['volume_change_pct'] - df['volume_change_pct'].shift(5)
        
        # 3. Price-volume relationship (positive when price up with volume up)
        df['price_volume_trend'] = (
            (df['volume'] * np.sign(df['close'].diff())).rolling(20).sum()
        )
        
        # 4. OBV trend
        df['obv_ma20'] = df['obv'].rolling(20).mean()
        df['obv_trend'] = np.where(
            df['obv_ma20'] != 0,
            (df['obv'] - df['obv_ma20']) / abs(df['obv_ma20']) * 100,
            0
        )
        
        # 5. VWAP deviation trend
        df['vwap_deviation_ma5'] = df['price_to_vwap_pct'].rolling(5).mean()
        
        return df
    
    def _build_composite_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build composite features
        
        Financial meaning: Combined signals from multiple indicators
        """
        # 1. Trend confirmation score (-3 to +3)
        # Combines direction of EMA, SMA, MACD
        df['trend_confirmation_score'] = (
            np.sign(df['ema_cross_strength']) +
            np.sign(df['sma_cross_strength']) +
            np.sign(df['macd'])
        )
        
        # 2. Overbought/oversold composite score
        # Combines RSI, BB position, price deviation
        df['overbought_score'] = (
            (df['rsi'] > 70).astype(int) +
            (df['bb_position'] > 80).astype(int) +
            (df['price_to_sma20_pct'] > 5).astype(int)
        )
        df['oversold_score'] = (
            (df['rsi'] < 30).astype(int) +
            (df['bb_position'] < 20).astype(int) +
            (df['price_to_sma20_pct'] < -5).astype(int)
        )
        
        # 3. Market strength indicator
        # Combines trend strength, volume, volatility
        df['market_strength'] = (
            abs(df['ema_cross_strength']) * 
            df['volume_ratio'] * 
            (1 + df['atr_normalized'] / 100)
        )
        
        # 4. Risk signal
        # High volatility + low liquidity = high risk
        df['risk_signal'] = (
            df['volatility_20'] * 
            (1 / df['volume_ratio'].replace(0, 1))
        )
        
        # 5. Reversal probability score
        # RSI extreme + BB breakout + MACD divergence
        df['reversal_probability'] = (
            ((df['rsi'] > 80) | (df['rsi'] < 20)).astype(int) * 2 +
            ((df['bb_position'] > 95) | (df['bb_position'] < 5)).astype(int) * 2 +
            (df['macd_momentum_5'] * df['macd'] < 0).astype(int)  # MACD divergence
        )
        
        # 6. Trend sustainability score
        # Trend direction consistent + volume support + moderate volatility
        df['trend_sustainability'] = (
            abs(df['trend_confirmation_score']) * 
            np.clip(df['volume_ratio'], 0.5, 2) *
            (1 - np.clip(df['volatility_20'] / 10, 0, 1))  # High volatility reduces sustainability
        )
        
        return df
    
    def get_feature_importance_groups(self) -> Dict[str, List[str]]:
        """
        Return feature importance groups
        
        Used for:
        1. Feature selection
        2. Feature weights during model training
        3. Priority when building LLM context
        """
        return {
            'critical': [  # Core features (must use)
                'price_to_sma20_pct',
                'ema_cross_strength',
                'macd',
                'rsi',
                'bb_position',
                'trend_confirmation_score',
                'volume_ratio',
                'atr_normalized'
            ],
            'important': [  # Important features (recommended)
                'price_to_sma50_pct',
                'sma_cross_strength',
                'macd_momentum_5',
                'rsi_momentum_5',
                'volatility_20',
                'obv_trend',
                'trend_sustainability',
                'market_strength'
            ],
            'supplementary': [  # Supplementary features (optional)
                'price_slope_20',
                'directional_strength',
                'return_10',
                'bb_width_change',
                'price_volume_trend',
                'overbought_score',
                'oversold_score',
                'reversal_probability'
            ]
        }
    
    def get_feature_descriptions(self) -> Dict[str, str]:
        """
        Return feature descriptions (for documentation and LLM understanding)
        """
        return {
            # Price position features
            'price_to_sma20_pct': 'Price deviation percentage from 20-day MA',
            'price_to_sma50_pct': 'Price deviation percentage from 50-day MA',
            'bb_position': 'Price position within Bollinger Bands (0-100)',
            'price_to_vwap_pct': 'Price deviation from volume-weighted average price',
            
            # Trend features
            'ema_cross_strength': 'EMA12 and EMA26 cross strength',
            'sma_cross_strength': 'SMA20 and SMA50 cross strength',
            'trend_confirmation_score': 'Multi-indicator trend confirmation score (-3 to +3)',
            'trend_sustainability': 'Trend sustainability score',
            
            # Momentum features
            'rsi_momentum_5': '5-period RSI momentum',
            'return_10': '10-period return rate',
            'momentum_acceleration': 'Momentum acceleration',
            
            # Volatility features
            'atr_normalized': 'Normalized ATR (volatility relative to price)',
            'volatility_20': '20-period historical volatility',
            'bb_width_change': 'Bollinger Band width change',
            
            # Volume features
            'volume_ratio': 'Current volume relative to average',
            'obv_trend': 'OBV trend indicator',
            'price_volume_trend': 'Price-volume trend',
            
            # Composite features
            'market_strength': 'Market strength composite indicator',
            'overbought_score': 'Overbought composite score (0-3)',
            'oversold_score': 'Oversold composite score (0-3)',
            'reversal_probability': 'Reversal probability score',
            'risk_signal': 'Risk signal (volatility × inverse liquidity)'
        }
