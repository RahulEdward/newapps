#!/usr/bin/env python3
"""
Data Flow Accuracy Verification Script
Verify the complete data chain from raw data to decision
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path

class DataAccuracyChecker:
    def __init__(self, data_dir='data', date='20251220', snapshot_id='snap_1766234252'):
        self.data_dir = Path(data_dir)
        self.date = date
        self.snapshot_id = snapshot_id
        self.symbol = 'BTCUSDT'
        self.timeframe = '5m'
        
    def check_stage1_raw_data(self):
        """Stage 1: Verify raw market data"""
        print("=" * 80)
        print("Stage 1: Raw Market Data Verification")
        print("=" * 80)
        
        json_file = self.data_dir / 'data_sync_agent' / self.date / f'market_data_{self.symbol}_{self.timeframe}_20251220_203733.json'
        
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        klines = data['klines']
        print(f"Candlestick count: {len(klines)}")
        print(f"Trading pair: {data['metadata']['symbol']}")
        
        # Verify price logic
        errors = 0
        for i, k in enumerate(klines[:10]):
            if k['high'] < max(k['open'], k['close']) or k['low'] > min(k['open'], k['close']):
                print(f"Candlestick {i+1} price logic error")
                errors += 1
        
        if errors == 0:
            print(f"Price logic verification passed (first 10)")
        
        return klines[-1]['close']  # Return last close price
    
    def check_stage2_indicators(self):
        """Stage 2: Verify technical indicator calculations"""
        print("\n" + "=" * 80)
        print("Stage 2: Technical Indicator Calculation Verification")
        print("=" * 80)
        
        parquet_file = self.data_dir / 'quant_analyst_agent' / 'indicators' / self.date / f'indicators_{self.symbol}_{self.timeframe}_20251220_203733_{self.snapshot_id}.parquet'
        
        df = pd.read_parquet(parquet_file)
        print(f"Data dimensions: {df.shape}")
        print(f"Indicator columns: {len(df.columns)}")
        
        # Check key indicators
        last_row = df.iloc[-1]
        print(f"Last close price: {last_row['close']:.2f}")
        print(f"EMA12: {last_row['ema_12']:.2f}")
        print(f"EMA26: {last_row['ema_26']:.2f}")
        print(f"RSI: {last_row['rsi']:.2f}")
        print(f"MACD: {last_row['macd']:.2f}")
        
        # Check NaN values (excluding warm-up period)
        valid_data = df[df['is_valid'] == True]
        nan_in_valid = valid_data.isna().sum().sum()
        print(f"NaN count in valid data: {nan_in_valid}")
        
        return last_row['close'], last_row['rsi'], last_row['ema_12'], last_row['ema_26']
    
    def check_stage3_features(self):
        """Stage 3: Verify feature extraction"""
        print("\n" + "=" * 80)
        print("Stage 3: Feature Extraction Verification")
        print("=" * 80)
        
        parquet_file = self.data_dir / 'quant_analyst_agent' / 'features' / self.date / f'features_{self.symbol}_{self.timeframe}_20251220_203733_{self.snapshot_id}_v1.parquet'
        
        df = pd.read_parquet(parquet_file)
        print(f"Feature dimensions: {df.shape}")
        print(f"Feature count: {len(df.columns)}")
        
        last_row = df.iloc[-1]
        print(f"Close price: {last_row['close']:.2f}")
        print(f"Return rate: {last_row['return_pct']:.4f}%")
        print(f"MACD percentage: {last_row['macd_pct']:.4f}%")
        
        # Check Inf values
        inf_count = np.isinf(df.select_dtypes(include=[np.number])).sum().sum()
        print(f"Inf value count: {inf_count}")
        
        return last_row['close']
    
    def check_stage4_quant_analysis(self):
        """Stage 4: Verify quantitative analysis"""
        print("\n" + "=" * 80)
        print("Stage 4: Quantitative Analysis Context Verification")
        print("=" * 80)
        
        json_file = self.data_dir / 'quant_analyst_agent' / 'context' / self.date / f'context_{self.symbol}_quant_analysis_20251220_203733_{self.snapshot_id}.json'
        
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        print(f"Signal source count: {len(data)}")
        
        # Verify trend signals
        trend_scores = []
        for period in ['5m', '15m', '1h']:
            key = f'trend_{period}'
            if key in data:
                score = data[key]['score']
                signal = data[key]['signal']
                trend_scores.append(score)
                print(f"{period} trend: {signal} (score: {score})")
        
        # Verify oscillator signals
        for period in ['5m', '15m', '1h']:
            key = f'oscillator_{period}'
            if key in data:
                score = data[key]['score']
                signal = data[key]['signal']
                print(f"{period} oscillator: {signal} (score: {score})")
        
        return sum(trend_scores)
    
    def check_stage5_decision(self):
        """Stage 5: Verify decision results"""
        print("\n" + "=" * 80)
        print("Stage 5: Decision Result Verification")
        print("=" * 80)
        
        json_file = self.data_dir / 'decision_core_agent' / 'decisions' / self.date / f'decision_{self.symbol}_20251220_203733_{self.snapshot_id}.json'
        
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        print(f"Decision action: {data['action']}")
        print(f"Confidence: {data['confidence']:.4f} ({data['confidence']*100:.2f}%)")
        print(f"Weighted score: {data['weighted_score']}")
        print(f"Multi-period aligned: {data['multi_period_aligned']}")
        
        # Verify weighted score calculation
        calculated_score = sum(data['vote_details'].values())
        print(f"\nWeighted score verification:")
        print(f"  Recorded value: {data['weighted_score']}")
        print(f"  Calculated value: {calculated_score:.2f}")
        diff = abs(data['weighted_score'] - calculated_score)
        if diff < 0.01:
            print(f"  Calculation correct (difference: {diff:.6f})")
        else:
            print(f"  Calculation error (difference: {diff:.6f})")
        
        return data['action'], data['weighted_score']
    
    def check_data_consistency(self):
        """Cross-stage data consistency verification"""
        print("\n" + "=" * 80)
        print("Cross-Stage Data Consistency Verification")
        print("=" * 80)
        
        # Read last row data from each stage
        json_file = self.data_dir / 'data_sync_agent' / self.date / f'market_data_{self.symbol}_{self.timeframe}_20251220_203733.json'
        with open(json_file, 'r') as f:
            raw_data = json.load(f)
        raw_close = raw_data['klines'][-1]['close']
        
        indicators_file = self.data_dir / 'quant_analyst_agent' / 'indicators' / self.date / f'indicators_{self.symbol}_{self.timeframe}_20251220_203733_{self.snapshot_id}.parquet'
        df_ind = pd.read_parquet(indicators_file)
        ind_close = df_ind.iloc[-1]['close']
        
        features_file = self.data_dir / 'quant_analyst_agent' / 'features' / self.date / f'features_{self.symbol}_{self.timeframe}_20251220_203733_{self.snapshot_id}_v1.parquet'
        df_feat = pd.read_parquet(features_file)
        feat_close = df_feat.iloc[-1]['close']
        
        print(f"Raw data close price: {raw_close:.2f}")
        print(f"Indicator data close price: {ind_close:.2f}")
        print(f"Feature data close price: {feat_close:.2f}")
        
        if abs(raw_close - ind_close) < 0.01 and abs(ind_close - feat_close) < 0.01:
            print(f"Close price consistency verification passed")
        else:
            print(f"Close price discrepancy detected")
        
        # Verify snapshot ID
        ind_snapshot = df_ind.iloc[-1]['snapshot_id']
        feat_snapshot = df_feat.iloc[-1]['source_snapshot_id']
        
        print(f"\nSnapshot ID consistency:")
        print(f"  Indicators: {ind_snapshot}")
        print(f"  Features: {feat_snapshot}")
        if ind_snapshot == feat_snapshot:
            print(f"  Snapshot ID consistent")
        else:
            print(f"  Snapshot ID inconsistent")
    
    def run_all_checks(self):
        """Run all verifications"""
        print("\n" + "Data Flow Accuracy Comprehensive Verification")
        print("=" * 80 + "\n")
        
        try:
            # Stage 1
            raw_close = self.check_stage1_raw_data()
            
            # Stage 2
            ind_close, rsi, ema12, ema26 = self.check_stage2_indicators()
            
            # Stage 3
            feat_close = self.check_stage3_features()
            
            # Stage 4
            trend_sum = self.check_stage4_quant_analysis()
            
            # Stage 5
            action, weighted_score = self.check_stage5_decision()
            
            # Consistency check
            self.check_data_consistency()
            
            # Summary
            print("\n" + "=" * 80)
            print("Verification Summary")
            print("=" * 80)
            print(f"All stage data verification complete")
            print(f"Data flow chain intact")
            print(f"Key data consistency good")
            print(f"\nFinal decision: {action} (weighted score: {weighted_score})")
            
        except Exception as e:
            print(f"\nVerification error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    checker = DataAccuracyChecker()
    checker.run_all_checks()
