#!/usr/bin/env python3
"""
Prophet ML Model Training Script
============================

Fetch historical data from Binance, generate features and labels, train ML model

Usage:
    python scripts/train_prophet.py --symbol BTCUSDT --days 30

Author: AI Trader Team
Date: 2025-12-21
"""

import os
import sys
import argparse
from datetime import datetime, timedelta

# Add project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

from src.api.binance_client import BinanceClient
from src.features.technical_features import TechnicalFeatureEngineer
from src.models.prophet_model import ProphetMLModel, LabelGenerator, HAS_LIGHTGBM
from src.utils.logger import log


def fetch_historical_data(
    client: BinanceClient,
    symbol: str,
    interval: str = '5m',
    days: int = 30
) -> pd.DataFrame:
    """
    Fetch historical candlestick data
    
    Args:
        client: Binance client
        symbol: Trading pair
        interval: Candlestick interval
        days: Number of historical days
    
    Returns:
        Candlestick DataFrame
    """
    log.info(f"Fetching {symbol} historical data ({days} days, {interval})...")
    
    # Calculate required number of candlesticks
    if interval == '5m':
        limit = days * 24 * 12  # 288 5-minute candles per day
    elif interval == '15m':
        limit = days * 24 * 4
    elif interval == '1h':
        limit = days * 24
    else:
        limit = 1000
    
    # Fetch data in batches (Binance limits to 1000 per request)
    all_klines = []
    remaining = limit
    end_time = None
    
    while remaining > 0:
        batch_size = min(remaining, 1000)
        klines = client.client.futures_klines(
            symbol=symbol,
            interval=interval,
            limit=batch_size,
            endTime=end_time
        )
        
        if not klines:
            break
        
        all_klines = klines + all_klines
        end_time = klines[0][0] - 1  # End time for next batch
        remaining -= batch_size
        
        log.info(f"   Fetched {len(all_klines)} candlesticks...")
    
    # Convert to DataFrame
    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    # Data type conversion
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    
    df.set_index('timestamp', inplace=True)
    df = df.sort_index()
    
    log.info(f"Fetch complete: {len(df)} candlesticks")
    log.info(f"   Time range: {df.index[0]} ~ {df.index[-1]}")
    
    return df


def prepare_training_data(
    df: pd.DataFrame,
    feature_engineer: TechnicalFeatureEngineer,
    label_generator: LabelGenerator
) -> tuple:
    """
    Prepare training data
    
    Args:
        df: Candlestick data
        feature_engineer: Feature engineer
        label_generator: Label generator
    
    Returns:
        (X, y) tuple
    """
    log.info("Calculating base indicators...")
    
    # Use MarketDataProcessor to calculate base indicators
    from src.data.processor import MarketDataProcessor
    processor = MarketDataProcessor()
    
    # Call internal method to calculate indicators
    df_with_indicators = processor._calculate_indicators(df.copy())
    
    log.info("Building advanced features...")
   
    # Generate features
    features_df = feature_engineer.build_features(df_with_indicators)
    
    # Remove non-numeric columns
    numeric_features = features_df.select_dtypes(include=[np.number])
    
    log.info(f"   Feature count: {len(numeric_features.columns)}")
    
    # Generate labels
    log.info("Generating labels...")
    X, y = label_generator.prepare_training_data(
        features_df=numeric_features,
        price_df=df,
        price_col='close'
    )
    
    return X, y


def train_model(
    X: pd.DataFrame,
    y: pd.Series,
    val_ratio: float = 0.2,
    output_path: str = 'models/prophet_lgb.pkl'
) -> dict:
    """
    Train model
    
    Args:
        X: Features
        y: Labels
        val_ratio: Validation set ratio
        output_path: Model output path
    
    Returns:
        Training metrics
    """
    # Split training and validation sets (time series, no random split)
    split_idx = int(len(X) * (1 - val_ratio))
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
    
    log.info(f"Data split:")
    log.info(f"   Training set: {len(X_train)} samples")
    log.info(f"   Validation set: {len(X_val)} samples")
    
    # Create and train model
    model = ProphetMLModel()
    metrics = model.train(X_train, y_train, X_val, y_val)
    
    # Save model
    model.save(output_path)
    
    # Output feature importance
    importance = model.get_feature_importance()
    top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
    
    log.info("Top 10 Feature Importance:")
    for name, imp in top_features:
        log.info(f"   {name}: {imp:.4f}")
    
    return metrics


def main():
    parser = argparse.ArgumentParser(description='Train Prophet ML Model')
    parser.add_argument('--symbol', type=str, default='BTCUSDT', help='Trading pair')
    parser.add_argument('--days', type=int, default=30, help='Historical days')
    parser.add_argument('--interval', type=str, default='5m', help='Candlestick interval')
    parser.add_argument('--output', type=str, default='models/prophet_lgb.pkl', help='Model output path')
    parser.add_argument('--horizon', type=int, default=30, help='Prediction horizon (minutes)')
    parser.add_argument('--threshold', type=float, default=0.001, help='Rise threshold')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("Prophet ML Model Training")
    print("="*60)
    
    if not HAS_LIGHTGBM:
        print("Error: LightGBM not installed")
        print("   Please run: pip install lightgbm scikit-learn")
        sys.exit(1)
    
    # Initialize components
    client = BinanceClient()
    feature_engineer = TechnicalFeatureEngineer()
    label_generator = LabelGenerator(
        horizon_minutes=args.horizon,
        up_threshold=args.threshold
    )
    
    # Fetch historical data
    df = fetch_historical_data(
        client=client,
        symbol=args.symbol,
        interval=args.interval,
        days=args.days
    )
    
    if len(df) < 500:
        print(f"Insufficient data: Need at least 500 candlesticks, currently have {len(df)}")
        sys.exit(1)
    
    # Prepare training data
    X, y = prepare_training_data(df, feature_engineer, label_generator)
    
    if len(X) < 100:
        print(f"Insufficient valid samples: Need at least 100, currently have {len(X)}")
        sys.exit(1)
    
    # Train model
    metrics = train_model(X, y, output_path=args.output)
    
    print("\n" + "="*60)
    print("Training Complete!")
    print("="*60)
    print(f"   Training samples: {metrics.get('train_samples', 0)}")
    print(f"   Validation samples: {metrics.get('val_samples', 0)}")
    print(f"   Training AUC: {metrics.get('train_auc', 0):.4f}")
    print(f"   Validation AUC: {metrics.get('val_auc', 0):.4f}")
    print(f"   Model path: {args.output}")
    print()


if __name__ == '__main__':
    main()
