"""
Complete Trading Pipeline Logger
Records the entire process from raw data fetching -> data processing -> feature extraction -> LLM decision -> trade execution
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from src.utils.json_utils import safe_json_dump


class TradingPipelineLogger:
    """Complete trading pipeline logger"""
    
    def __init__(self, log_dir: str = "logs/pipeline"):
        """Initialize pipeline logger"""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Current session info
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_start = datetime.now()
        
        # Pipeline records
        self.pipeline_steps = []
        self.current_cycle = 0
        
        print(f"\n{'='*100}")
        print(f"📊 Trading Pipeline Logger Started")
        print(f"Session ID: {self.session_id}")
        print(f"Log Directory: {self.log_dir}")
        print(f"{'='*100}\n")
    
    def start_new_cycle(self, symbol: str):
        """Start a new trading cycle"""
        self.current_cycle += 1
        self.current_cycle_data = {
            "cycle_id": self.current_cycle,
            "symbol": symbol,
            "start_time": datetime.now().isoformat(),
            "steps": []
        }
        
        print(f"\n{'='*100}")
        print(f"🔄 Starting New Trading Cycle #{self.current_cycle} - {symbol}")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*100}\n")
    
    def log_step(self, 
                 step_name: str, 
                 step_type: str,
                 input_data: Any, 
                 processing: str, 
                 output_data: Any,
                 metadata: Optional[Dict] = None):
        """
        Record a single processing step
        
        Args:
            step_name: Step name
            step_type: Step type (data_fetch|data_process|feature_extract|llm_decision|risk_check|execution)
            input_data: Input data
            processing: Processing logic description
            output_data: Output data
            metadata: Additional metadata
        """
        timestamp = datetime.now().isoformat()
        
        step_log = {
            "timestamp": timestamp,
            "step_name": step_name,
            "step_type": step_type,
            "input": self._serialize_data(input_data),
            "processing": processing,
            "output": self._serialize_data(output_data),
            "metadata": metadata or {}
        }
        
        self.current_cycle_data["steps"].append(step_log)
        
        # Print to console
        self._print_step(step_name, step_type, input_data, processing, output_data)
    
    def log_raw_data(self, timeframe: str, klines: List[Dict], metadata: Optional[Dict] = None):
        """Record raw candlestick data"""
        self.log_step(
            step_name=f"1. Fetch {timeframe} Raw Candlestick Data",
            step_type="data_fetch",
            input_data={
                "symbol": self.current_cycle_data["symbol"],
                "interval": timeframe,
                "limit": len(klines)
            },
            processing=f"Call AngelOne API to fetch the latest {len(klines)} {timeframe} candlesticks",
            output_data={
                "data_type": "List[Dict]",
                "count": len(klines),
                "first_kline": klines[0] if klines else None,
                "last_kline": klines[-1] if klines else None,
                "fields": list(klines[0].keys()) if klines else []
            },
            metadata=metadata
        )
    
    def log_data_processing(self, timeframe: str, raw_count: int, df: pd.DataFrame, 
                           anomalies: int, metadata: Optional[Dict] = None):
        """Record data processing step"""
        self.log_step(
            step_name=f"2. Process {timeframe} Data and Calculate Technical Indicators",
            step_type="data_process",
            input_data={
                "raw_kline_count": raw_count,
                "timeframe": timeframe
            },
            processing=f"""
Data Processing Pipeline:
1. Convert candlestick list to DataFrame
2. Anomaly detection (Z-score method)
3. Anomaly cleaning (detected {anomalies} anomalies)
4. Calculate technical indicators:
   - Moving Averages: SMA(20, 50), EMA(12, 26)
   - Momentum Indicators: RSI(14), MACD(12, 26, 9)
   - Volatility Indicators: Bollinger Bands(20, 2), ATR(14)
   - Volume Indicators: Volume SMA(20), Volume Ratio
5. Data validation and snapshot generation
            """.strip(),
            output_data={
                "dataframe": df,
                "shape": df.shape,
                "columns": list(df.columns),
                "anomaly_count": anomalies
            },
            metadata=metadata
        )
    
    def log_feature_extraction(self, timeframe: str, features: Dict, metadata: Optional[Dict] = None):
        """Record feature extraction step"""
        self.log_step(
            step_name=f"3. Extract {timeframe} Key Features",
            step_type="feature_extract",
            input_data={
                "timeframe": timeframe,
                "data_source": "processed_dataframe"
            },
            processing=f"""
Extract key features from the last row of {timeframe} DataFrame:
- Price data: open, high, low, close
- Volume: volume, volume_ratio
- Trend indicators: SMA20, SMA50, EMA12, EMA26
- Momentum indicators: RSI, MACD, MACD_signal
- Volatility indicators: Bollinger Bands (upper, middle, lower), ATR
- Calculated indicators: trend, momentum, volatility
            """.strip(),
            output_data=features,
            metadata=metadata
        )
    
    def log_multi_timeframe_context(self, context: Dict, metadata: Optional[Dict] = None):
        """Record multi-timeframe context building"""
        self.log_step(
            step_name="4. Build Multi-Timeframe Market Context",
            step_type="feature_extract",
            input_data={
                "timeframes": list(context.keys()),
                "features_per_tf": [len(context[tf]) for tf in context.keys()]
            },
            processing="""
Merge features from multiple timeframes:
1. Integrate price, indicators, and trends from each timeframe
2. Calculate cross-timeframe consistency
3. Determine multi-timeframe trend direction
4. Evaluate market state (trending/ranging/volatile)
            """.strip(),
            output_data=context,
            metadata=metadata
        )
    
    def log_llm_input(self, prompt_text: str, context_data: Dict, metadata: Optional[Dict] = None):
        """Record LLM input"""
        self.log_step(
            step_name="5. Prepare LLM Input Data",
            step_type="llm_decision",
            input_data={
                "market_context": context_data,
                "prompt_length": len(prompt_text),
                "timeframes_analyzed": list(context_data.keys()) if isinstance(context_data, dict) else None
            },
            processing="""
Build LLM input:
1. Format market data as text
2. Add system prompt (trading rules, risk management)
3. Add user prompt (current market state)
4. Set response format to JSON
            """.strip(),
            output_data={
                "prompt_preview": prompt_text[:500] + "..." if len(prompt_text) > 500 else prompt_text,
                "full_prompt_length": len(prompt_text)
            },
            metadata=metadata
        )
    
    def log_llm_output(self, decision: Dict, raw_response: str, metadata: Optional[Dict] = None):
        """Record LLM output"""
        self.log_step(
            step_name="6. LLM Decision Result",
            step_type="llm_decision",
            input_data={
                "model": decision.get('model', 'unknown'),
                "response_length": len(raw_response)
            },
            processing="""
Parse LLM response:
1. Receive JSON format decision result
2. Validate decision format completeness
3. Extract key decision fields:
   - action (trade action)
   - confidence (confidence level)
   - position_size_pct (position size percentage)
   - leverage (leverage)
   - stop_loss_pct / take_profit_pct (stop loss/take profit)
   - reasoning (decision reasoning)
   - analysis (detailed analysis)
            """.strip(),
            output_data={
                "decision": decision,
                "action": decision.get('action'),
                "confidence": decision.get('confidence'),
                "reasoning": decision.get('reasoning', '')[:200]  # Truncate to first 200 characters
            },
            metadata=metadata
        )
    
    def log_risk_check(self, decision: Dict, risk_result: Dict, metadata: Optional[Dict] = None):
        """Record risk check"""
        self.log_step(
            step_name="7. Risk Management Validation",
            step_type="risk_check",
            input_data={
                "original_decision": decision.get('action'),
                "position_size_pct": decision.get('position_size_pct'),
                "leverage": decision.get('leverage')
            },
            processing="""
Risk management checks:
1. Verify position size does not exceed limits
2. Verify leverage is compliant
3. Calculate actual risk exposure
4. Check if account balance is sufficient
5. Verify stop loss/take profit settings are reasonable
6. Check for risk control rule violations
            """.strip(),
            output_data=risk_result,
            metadata=metadata
        )
    
    def log_execution(self, action: str, result: Dict, metadata: Optional[Dict] = None):
        """Record trade execution"""
        self.log_step(
            step_name="8. Trade Execution",
            step_type="execution",
            input_data={
                "action": action,
                "timestamp": datetime.now().isoformat()
            },
            processing=f"""
Execute trade operation: {action}
1. Call AngelOne API to place order
2. Set stop loss/take profit orders
3. Record trade log
4. Update position status
            """.strip(),
            output_data=result,
            metadata=metadata
        )
    
    def end_cycle(self, final_result: Optional[Dict] = None):
        """End current trading cycle"""
        self.current_cycle_data["end_time"] = datetime.now().isoformat()
        self.current_cycle_data["duration_seconds"] = (
            datetime.fromisoformat(self.current_cycle_data["end_time"]) - 
            datetime.fromisoformat(self.current_cycle_data["start_time"])
        ).total_seconds()
        self.current_cycle_data["final_result"] = final_result
        
        # Save to pipeline records
        self.pipeline_steps.append(self.current_cycle_data)
        
        # Save individual cycle log
        self._save_cycle_log(self.current_cycle_data)
        
        print(f"\n{'='*100}")
        print(f"✅ Trading Cycle #{self.current_cycle} Completed")
        print(f"⏱️  Duration: {self.current_cycle_data['duration_seconds']:.2f} seconds")
        print(f"📊 Total Steps: {len(self.current_cycle_data['steps'])}")
        print(f"{'='*100}\n")
    
    def _serialize_data(self, data: Any) -> Any:
        """Serialize data for JSON storage"""
        import numpy as np
        
        # Handle pandas.Timestamp
        if isinstance(data, pd.Timestamp):
            return str(data)
        
        # Handle numpy types (must be before other checks)
        if hasattr(data, 'item'):
            return data.item()
        
        # Handle DataFrame
        if isinstance(data, pd.DataFrame):
            df_copy = data.copy()
            df_copy.index = df_copy.index.astype(str)
            
            # Convert all numpy types to Python native types
            for col in df_copy.columns:
                if df_copy[col].dtype == 'object':
                    continue
                df_copy[col] = df_copy[col].apply(lambda x: x.item() if hasattr(x, 'item') else x)
            
            df_dict = df_copy.reset_index().to_dict('records')
            return {
                "type": "DataFrame",
                "shape": list(data.shape),
                "columns": list(data.columns),
                "head_3": df_dict[:3] if len(df_dict) > 0 else [],
                "tail_3": df_dict[-3:] if len(df_dict) > 0 else [],
                "summary": {
                    "row_count": len(data),
                    "column_count": len(data.columns),
                    "latest_values": self._get_latest_row_values(data)
                }
            }
        
        # Handle dict
        elif isinstance(data, dict):
            return {str(k): self._serialize_data(v) for k, v in data.items()}
        
        # Handle list
        elif isinstance(data, list):
            if len(data) <= 5:
                return [self._serialize_data(item) for item in data]
            else:
                return {
                    "type": "list",
                    "length": len(data),
                    "first_3": [self._serialize_data(item) for item in data[:3]],
                    "last_3": [self._serialize_data(item) for item in data[-3:]]
                }
        
        # Other types
        else:
            return data
    
    def _get_latest_row_values(self, df: pd.DataFrame) -> Dict:
        """Get key values from the last row of DataFrame"""
        if df.empty:
            return {}
        
        latest = df.iloc[-1]
        result = {}
        
        # Only keep numeric columns
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                val = latest[col]
                if hasattr(val, 'item'):
                    result[col] = val.item()
                else:
                    result[col] = val
        
        return result
    
    def _print_step(self, step_name: str, step_type: str, input_data: Any, 
                    processing: str, output_data: Any):
        """Print step information to console"""
        
        # Step type icons
        type_icons = {
            "data_fetch": "🔽",
            "data_process": "⚙️",
            "feature_extract": "📊",
            "llm_decision": "🤖",
            "risk_check": "🛡️",
            "execution": "⚡"
        }
        
        icon = type_icons.get(step_type, "📌")
        
        print(f"\n{'='*100}")
        print(f"{icon} Step: {step_name}")
        print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*100}")
        
        print(f"\n📥 Input Data:")
        self._print_data_summary(input_data, indent=3)
        
        print(f"\n⚙️  Processing Logic:")
        for line in processing.split('\n'):
            print(f"   {line}")
        
        print(f"\n📤 Output Data:")
        self._print_data_summary(output_data, indent=3)
        
        print(f"\n{'='*100}")
    
    def _print_data_summary(self, data: Any, indent: int = 3):
        """Print data summary"""
        prefix = " " * indent
        
        if isinstance(data, pd.DataFrame):
            print(f"{prefix}Type: DataFrame")
            print(f"{prefix}Shape: {data.shape}")
            print(f"{prefix}Columns: {len(data.columns)}")
            
        elif isinstance(data, dict):
            print(f"{prefix}Type: Dict")
            print(f"{prefix}Key Count: {len(data)}")
            for key, value in list(data.items())[:10]:  # Only show first 10
                if isinstance(value, (dict, list)):
                    print(f"{prefix}{key}: {type(value).__name__} (length={len(value)})")
                elif isinstance(value, (int, float)):
                    if isinstance(value, float):
                        print(f"{prefix}{key}: {value:.6f}")
                    else:
                        print(f"{prefix}{key}: {value}")
                else:
                    val_str = str(value)
                    if len(val_str) > 100:
                        val_str = val_str[:100] + "..."
                    print(f"{prefix}{key}: {val_str}")
        
        elif isinstance(data, list):
            print(f"{prefix}Type: List")
            print(f"{prefix}Length: {len(data)}")
        
        else:
            print(f"{prefix}{data}")
    
    def _save_cycle_log(self, cycle_data: Dict):
        """Save individual cycle log"""
        cycle_file = self.log_dir / f"cycle_{self.session_id}_{cycle_data['cycle_id']:03d}.json"
        
        with open(cycle_file, 'w', encoding='utf-8') as f:
            safe_json_dump(cycle_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Cycle log saved: {cycle_file}")
    
    def save_session_summary(self):
        """Save session summary"""
        summary = {
            "session_id": self.session_id,
            "start_time": self.session_start.isoformat(),
            "end_time": datetime.now().isoformat(),
            "total_cycles": len(self.pipeline_steps),
            "total_duration_seconds": (datetime.now() - self.session_start).total_seconds(),
            "cycles": self.pipeline_steps
        }
        
        summary_file = self.log_dir / f"session_{self.session_id}_summary.json"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            safe_json_dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*100}")
        print(f"💾 Session summary saved: {summary_file}")
        print(f"   Total cycles: {summary['total_cycles']}")
        print(f"   Total duration: {summary['total_duration_seconds']:.2f} seconds")
        print(f"{'='*100}\n")
        
        return str(summary_file)
