"""
The Prophet Agent (Predict Agent)
===========================================

Responsibilities:
1. Receive structured feature data
2. Output future price rise probability (0.0 - 1.0)
3. Support Rule-based scoring and ML model two modes
4. Provide factor decomposition to explain prediction reasons

Author: AI Trader Team
Date: 2025-12-21
"""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import pandas as pd

from src.utils.logger import log


@dataclass
class PredictResult:
    """Prediction result"""
    probability_up: float      # 0.0 - 1.0: Price rise probability
    probability_down: float    # 0.0 - 1.0: Price fall probability
    confidence: float          # 0.0 - 1.0: Prediction confidence
    horizon: str               # Prediction time horizon (e.g., '5m', '15m', '1h')
    factors: Dict[str, float]  # Factor contribution decomposition
    model_type: str            # 'rule_based' or 'ml_model'
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def signal(self) -> str:
        """Generate signal based on probability"""
        if self.probability_up > 0.65:
            return 'strong_bullish'
        elif self.probability_up > 0.55:
            return 'bullish'
        elif self.probability_down > 0.65:
            return 'strong_bearish'
        elif self.probability_down > 0.55:
            return 'bearish'
        else:
            return 'neutral'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'probability_up': self.probability_up,
            'probability_down': self.probability_down,
            'confidence': self.confidence,
            'horizon': self.horizon,
            'signal': self.signal,
            'factors': self.factors,
            'model_type': self.model_type,
            'timestamp': self.timestamp.isoformat()
        }


class PredictAgent:
    """
    The Prophet (Predict Agent)
    
    Core functions:
    - Receive structured feature data (from TechnicalFeatureEngineer)
    - Use weighted Rule-based scoring to calculate rise/fall probability
    - Reserve ML model interface for future extension
    """
    
    # Feature weight configuration
    FEATURE_WEIGHTS = {
        # Trend features (higher weight)
        'trend_confirmation_score': 0.15,
        'ema_cross_strength': 0.10,
        'sma_cross_strength': 0.08,
        'macd_momentum_5': 0.05,
        
        # Momentum features
        'rsi': 0.12,
        'rsi_momentum_5': 0.05,
        'momentum_acceleration': 0.05,
        
        # Price position features
        'bb_position': 0.10,
        'price_to_sma20_pct': 0.08,
        
        # Volume features
        'volume_ratio': 0.07,
        'obv_trend': 0.05,
        
        # Volatility features
        'atr_normalized': 0.05,
        'volatility_20': 0.05,
    }
    
    # RSI thresholds
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    
    # Bollinger Band position thresholds
    BB_LOW_THRESHOLD = 20
    BB_HIGH_THRESHOLD = 80
    
    def __init__(self, horizon: str = '30m', symbol: str = 'BTCUSDT', model_path: str = None):
        """
        Initialize The Prophet (Predict Agent)
        
        Args:
            horizon: Prediction time horizon (default 30m - matches ML model label)
            symbol: Trading pair symbol (used to load corresponding model)
            model_path: ML model file path (optional, default generated based on symbol)
        """
        self.horizon = horizon
        self.symbol = symbol
        self.history: List[PredictResult] = []
        self.ml_model = None
        # Generate symbol-specific model path
        self.model_path = model_path or f'models/prophet_lgb_{symbol}.pkl'
        
        # Try to load ML model
        self._try_load_ml_model()
        
        mode_str = "ML Model" if self.ml_model is not None else "Rule-based scoring"
        log.info(f"The Prophet initialized | Horizon: {horizon} | Symbol: {symbol} | Mode: {mode_str}")
    
    def _try_load_ml_model(self):
        """Try to load ML model"""
        import os
        if os.path.exists(self.model_path):
            try:
                from src.models.prophet_model import ProphetMLModel, HAS_LIGHTGBM
                if HAS_LIGHTGBM:
                    self.ml_model = ProphetMLModel(self.model_path)
                    log.info(f"ML model loaded: {self.model_path}")
                else:
                    log.warning("LightGBM not installed, using Rule-based scoring mode")
            except Exception as e:
                log.warning(f"ML model load failed: {e}, using Rule-based scoring mode")
    
    async def predict(self, features: Dict[str, float]) -> PredictResult:
        """
        Predict price movement based on feature data
        
        Args:
            features: Structured feature dictionary (from TechnicalFeatureEngineer or extract_feature_snapshot)
            
        Returns:
            PredictResult object
        """
        # Preprocess features
        clean_features = self._preprocess_features(features)
        
        # Select prediction mode
        if self.ml_model is not None:
            result = await self._predict_with_ml(clean_features)
        else:
            result = await self._predict_with_rules(clean_features)
        
        # Record history
        self.history.append(result)
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        
        return result
    
    def _preprocess_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        Preprocess features: Handle missing values, outliers
        
        Args:
            features: Raw feature dictionary
            
        Returns:
            Cleaned feature dictionary
        """
        clean = {}
        
        for key, value in features.items():
            if value is None or (isinstance(value, float) and np.isnan(value)):
                # Missing value uses default
                clean[key] = self._get_default_value(key)
            elif isinstance(value, float) and np.isinf(value):
                # Infinite value uses boundary
                clean[key] = 100.0 if value > 0 else -100.0
            else:
                clean[key] = float(value) if isinstance(value, (int, float, np.number)) else 0.0
        
        return clean
    
    def _get_default_value(self, feature_name: str) -> float:
        """Get default value for feature"""
        defaults = {
            'rsi': 50.0,
            'bb_position': 50.0,
            'trend_confirmation_score': 0.0,
            'ema_cross_strength': 0.0,
            'sma_cross_strength': 0.0,
            'volume_ratio': 1.0,
            'atr_normalized': 1.0,
            'price_to_sma20_pct': 0.0,
            'obv_trend': 0.0,
        }
        return defaults.get(feature_name, 0.0)
    
    async def _predict_with_rules(self, features: Dict[str, float]) -> PredictResult:
        """
        Predict using Rule-based scoring system
        
        Scoring logic:
        - Base probability: 0.5 (neutral)
        - Adjust probability based on each feature
        - Final normalization to [0, 1]
        """
        bullish_score = 0.0
        bearish_score = 0.0
        factors = {}
        
        # 1. Trend confirmation score (-3 to +3)
        trend_score = features.get('trend_confirmation_score', 0)
        if trend_score >= 2:
            bullish_score += 0.15
            factors['trend_confirmation'] = 0.15
        elif trend_score >= 1:
            bullish_score += 0.08
            factors['trend_confirmation'] = 0.08
        elif trend_score <= -2:
            bearish_score += 0.15
            factors['trend_confirmation'] = -0.15
        elif trend_score <= -1:
            bearish_score += 0.08
            factors['trend_confirmation'] = -0.08
        else:
            factors['trend_confirmation'] = 0.0
        
        # 2. RSI (overbought/oversold)
        rsi = features.get('rsi', 50)
        if rsi < self.RSI_OVERSOLD:
            # Oversold -> Bullish reversal
            bullish_score += 0.12
            factors['rsi_oversold'] = 0.12
        elif rsi < 40:
            bullish_score += 0.06
            factors['rsi_low'] = 0.06
        elif rsi > self.RSI_OVERBOUGHT:
            # Overbought -> Bearish reversal
            bearish_score += 0.12
            factors['rsi_overbought'] = -0.12
        elif rsi > 60:
            bearish_score += 0.06
            factors['rsi_high'] = -0.06
        
        # 3. Bollinger Band position (0-100)
        bb_pos = features.get('bb_position', 50)
        if bb_pos < self.BB_LOW_THRESHOLD:
            bullish_score += 0.10
            factors['bb_oversold'] = 0.10
        elif bb_pos > self.BB_HIGH_THRESHOLD:
            bearish_score += 0.10
            factors['bb_overbought'] = -0.10
        
        # 4. EMA cross strength
        ema_strength = features.get('ema_cross_strength', 0)
        if ema_strength > 0.5:
            bullish_score += 0.08
            factors['ema_bullish'] = 0.08
        elif ema_strength > 0.2:
            bullish_score += 0.04
            factors['ema_bullish'] = 0.04
        elif ema_strength < -0.5:
            bearish_score += 0.08
            factors['ema_bearish'] = -0.08
        elif ema_strength < -0.2:
            bearish_score += 0.04
            factors['ema_bearish'] = -0.04
        
        # 5. Volume ratio
        vol_ratio = features.get('volume_ratio', 1.0)
        if vol_ratio > 1.5:
            # High volume amplifies trend signal
            if bullish_score > bearish_score:
                bullish_score += 0.05
                factors['volume_confirm_up'] = 0.05
            elif bearish_score > bullish_score:
                bearish_score += 0.05
                factors['volume_confirm_down'] = -0.05
        
        # 6. Momentum acceleration
        momentum_acc = features.get('momentum_acceleration', 0)
        if momentum_acc > 0.5:
            bullish_score += 0.05
            factors['momentum_up'] = 0.05
        elif momentum_acc < -0.5:
            bearish_score += 0.05
            factors['momentum_down'] = -0.05
        
        # 7. Trend sustainability
        trend_sustain = features.get('trend_sustainability', 0)
        if trend_sustain > 1.5:
            # Strong trend sustainability, enhance current direction
            direction = 1 if bullish_score > bearish_score else -1
            if direction > 0:
                bullish_score += 0.05
                factors['trend_sustain_up'] = 0.05
            else:
                bearish_score += 0.05
                factors['trend_sustain_down'] = -0.05
        
        # Calculate final probability
        total_score = bullish_score + bearish_score
        if total_score == 0:
            prob_up = 0.5
            prob_down = 0.5
        else:
            # Use sigmoid-style normalization
            net_score = bullish_score - bearish_score
            prob_up = 0.5 + (net_score / 2)  # Map net_score to [0, 1]
            prob_up = max(0.0, min(1.0, prob_up))
            prob_down = 1.0 - prob_up
        
        # Calculate confidence (based on signal strength)
        # FIX C2: Cap rule-based confidence at 70% to prevent over-aggressive AI Veto
        confidence = min(0.70, (bullish_score + bearish_score) / 0.5)
        
        return PredictResult(
            probability_up=round(prob_up, 4),
            probability_down=round(prob_down, 4),
            confidence=round(confidence, 4),
            horizon=self.horizon,
            factors=factors,
            model_type='rule_based'
        )
    
    async def _predict_with_ml(self, features: Dict[str, float]) -> PredictResult:
        """
        Predict using ML model
        
        Args:
            features: Preprocessed feature dictionary
        
        Returns:
            PredictResult object
        """
        try:
            # Use ML model to predict probability
            prob_up = self.ml_model.predict_proba(features)
            prob_down = 1.0 - prob_up
            
            # Get feature importance as factors
            importance = self.ml_model.get_feature_importance()
            # Take Top 5 important features
            top_factors = dict(sorted(
                importance.items(), 
                key=lambda x: abs(x[1]), 
                reverse=True
            )[:5])
            
            # Calculate base confidence based on probability deviation
            base_confidence = abs(prob_up - 0.5) * 2  # 0.0 - 1.0
            
            # Scale using validation set AUC score
            # AUC 0.5 -> 0.0 impact (Random)
            # AUC 1.0 -> 1.0 impact (Perfect)
            val_auc = self.ml_model.val_auc
            auc_factor = max(0.0, (val_auc - 0.5) * 2)
            
            # Final confidence = base confidence * model quality factor
            final_confidence = base_confidence * auc_factor
            
            return PredictResult(
                probability_up=round(prob_up, 4),
                probability_down=round(prob_down, 4),
                confidence=round(min(final_confidence, 1.0), 4),
                horizon=self.horizon,
                factors=top_factors,
                model_type='ml_lightgbm'
            )
        except Exception as e:
            log.warning(f"ML prediction failed: {e}, falling back to Rule-based scoring")
            return await self._predict_with_rules(features)
    
    def load_ml_model(self, model_path: str):
        """
        Load ML model
        
        Args:
            model_path: Model file path
        """
        from src.models.prophet_model import ProphetMLModel, HAS_LIGHTGBM
        if HAS_LIGHTGBM:
            self.ml_model = ProphetMLModel(model_path)
            self.model_path = model_path
            log.info(f"ML model loaded: {model_path}")
        else:
            log.warning("LightGBM not installed, cannot load ML model")
    
    def get_statistics(self) -> Dict:
        """Get prediction statistics"""
        if not self.history:
            return {'total_predictions': 0}
        
        total = len(self.history)
        signals = [h.signal for h in self.history]
        avg_confidence = sum(h.confidence for h in self.history) / total
        
        return {
            'total_predictions': total,
            'avg_confidence': avg_confidence,
            'signal_distribution': {
                'strong_bullish': signals.count('strong_bullish'),
                'bullish': signals.count('bullish'),
                'neutral': signals.count('neutral'),
                'bearish': signals.count('bearish'),
                'strong_bearish': signals.count('strong_bearish'),
            },
            'model_type': self.history[-1].model_type if self.history else 'unknown'
        }


# ============================================
# Test Functions
# ============================================
async def test_predict_agent():
    """Test The Prophet (Predict Agent)"""
    print("\n" + "="*60)
    print("🧪 Testing The Prophet (Predict Agent)")
    print("="*60)
    
    # Initialize
    agent = PredictAgent(horizon='15m')
    
    # Simulated feature data (bullish scenario)
    bullish_features = {
        'trend_confirmation_score': 2.5,
        'ema_cross_strength': 0.8,
        'sma_cross_strength': 0.5,
        'rsi': 35,
        'rsi_momentum_5': 5,
        'bb_position': 25,
        'volume_ratio': 1.6,
        'momentum_acceleration': 0.8,
        'trend_sustainability': 1.8,
        'atr_normalized': 1.2,
        'price_to_sma20_pct': 0.5,
    }
    
    print("\n1️⃣ Testing bullish scenario...")
    result = await agent.predict(bullish_features)
    print(f"  ✅ Up probability: {result.probability_up:.2%}")
    print(f"  ✅ Down probability: {result.probability_down:.2%}")
    print(f"  ✅ Signal: {result.signal}")
    print(f"  ✅ Confidence: {result.confidence:.2%}")
    print(f"  ✅ Factors: {result.factors}")
    
    # Simulated feature data (bearish scenario)
    bearish_features = {
        'trend_confirmation_score': -2.0,
        'ema_cross_strength': -0.6,
        'sma_cross_strength': -0.4,
        'rsi': 75,
        'rsi_momentum_5': -3,
        'bb_position': 85,
        'volume_ratio': 1.3,
        'momentum_acceleration': -0.6,
        'trend_sustainability': 0.5,
        'atr_normalized': 2.0,
        'price_to_sma20_pct': 3.0,
    }
    
    print("\n2️⃣ Testing bearish scenario...")
    result = await agent.predict(bearish_features)
    print(f"  ✅ Up probability: {result.probability_up:.2%}")
    print(f"  ✅ Down probability: {result.probability_down:.2%}")
    print(f"  ✅ Signal: {result.signal}")
    print(f"  ✅ Confidence: {result.confidence:.2%}")
    
    # Simulated neutral scenario
    neutral_features = {
        'trend_confirmation_score': 0,
        'ema_cross_strength': 0.1,
        'rsi': 50,
        'bb_position': 50,
        'volume_ratio': 1.0,
    }
    
    print("\n3️⃣ Testing neutral scenario...")
    result = await agent.predict(neutral_features)
    print(f"  ✅ Up probability: {result.probability_up:.2%}")
    print(f"  ✅ Signal: {result.signal}")
    
    # Test statistics
    print("\n4️⃣ Statistics info...")
    stats = agent.get_statistics()
    print(f"  ✅ Total predictions: {stats['total_predictions']}")
    print(f"  ✅ Average confidence: {stats['avg_confidence']:.2%}")
    
    print("\n✅ The Prophet (Predict Agent) test passed!")
    return agent


if __name__ == '__main__':
    asyncio.run(test_predict_agent())
