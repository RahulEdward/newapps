"""
Data Flow Detailed Logger
Records each step of processing from raw data to final decision
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd


class DataFlowLogger:
    """Data Flow Logger"""
    
    def __init__(self, log_dir: str = "logs/data_flow"):
        """Initialize logger"""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Current session log
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_log = []
        
        print(f"\n{'='*100}")
        print(f"📊 Data Flow Detailed Logger Started")
        print(f"Session ID: {self.session_id}")
        print(f"Log Directory: {self.log_dir}")
        print(f"{'='*100}\n")
    
    def log_step(self, step_name: str, input_data: Any, processing: str, output_data: Any):
        """
        Record a single processing step
        
        Args:
            step_name: Step name
            input_data: Input data
            processing: Processing logic description
            output_data: Output data
        """
        timestamp = datetime.now().isoformat()
        
        step_log = {
            "timestamp": timestamp,
            "step": step_name,
            "input": self._serialize_data(input_data),
            "processing": processing,
            "output": self._serialize_data(output_data)
        }
        
        self.session_log.append(step_log)
        
        # Print to console
        print(f"\n{'='*100}")
        print(f"🔄 Step: {step_name}")
        print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*100}")
        
        print(f"\n📥 Input Data:")
        self._print_data(input_data)
        
        print(f"\n⚙️  Processing Logic:")
        print(f"   {processing}")
        
        print(f"\n📤 Output Data:")
        self._print_data(output_data)
        
        print(f"\n{'='*100}")
    
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
            # Convert DataFrame to serializable format
            # First convert index to string, then convert all values
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
                "tail_3": df_dict[-3:] if len(df_dict) > 0 else []
            }
        
        # Handle dict
        elif isinstance(data, dict):
            return {str(k): self._serialize_data(v) for k, v in data.items()}
        
        # Handle list
        elif isinstance(data, list) and len(data) > 0:
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
    
    def _print_data(self, data: Any, indent: int = 3):
        """Print data to console"""
        prefix = " " * indent
        
        if isinstance(data, pd.DataFrame):
            print(f"{prefix}Type: DataFrame")
            print(f"{prefix}Shape: {data.shape} (rows={data.shape[0]}, columns={data.shape[1]})")
            print(f"{prefix}Columns: {list(data.columns)}")
            
            if not data.empty:
                print(f"\n{prefix}First 3 rows:")
                print(data.head(3).to_string(index=False).replace('\n', f'\n{prefix}'))
                
                print(f"\n{prefix}Last 3 rows:")
                print(data.tail(3).to_string(index=False).replace('\n', f'\n{prefix}'))
                
                # Numeric column statistics
                numeric_cols = data.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    print(f"\n{prefix}Numeric column statistics:")
                    latest = data.iloc[-1]
                    for col in numeric_cols:
                        if col in latest:
                            print(f"{prefix}  - {col}: {latest[col]:.6f}")
        
        elif isinstance(data, dict):
            print(f"{prefix}Type: Dict")
            print(f"{prefix}Key count: {len(data)}")
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    print(f"{prefix}{key}: {type(value).__name__} (length={len(value)})")
                elif isinstance(value, (int, float)):
                    print(f"{prefix}{key}: {value:.6f}" if isinstance(value, float) else f"{prefix}{key}: {value}")
                else:
                    print(f"{prefix}{key}: {value}")
        
        elif isinstance(data, list):
            print(f"{prefix}Type: List")
            print(f"{prefix}Length: {len(data)}")
            if len(data) <= 5:
                for i, item in enumerate(data):
                    print(f"{prefix}[{i}]: {item}")
            else:
                print(f"{prefix}First 3: {data[:3]}")
                print(f"{prefix}Last 3: {data[-3:]}")
        
        else:
            print(f"{prefix}{data}")
    
    def save_session_log(self):
        """Save complete log for current session"""
        log_file = self.log_dir / f"session_{self.session_id}.json"
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump({
                "session_id": self.session_id,
                "timestamp": datetime.now().isoformat(),
                "total_steps": len(self.session_log),
                "steps": self.session_log
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*100}")
        print(f"💾 Data flow log saved: {log_file}")
        print(f"   Total steps: {len(self.session_log)}")
        print(f"{'='*100}\n")
        
        return str(log_file)
    
    def create_summary(self):
        """Create data flow summary"""
        summary = {
            "session_id": self.session_id,
            "total_steps": len(self.session_log),
            "steps_summary": []
        }
        
        for step in self.session_log:
            summary["steps_summary"].append({
                "step": step["step"],
                "timestamp": step["timestamp"],
                "processing": step["processing"]
            })
        
        print(f"\n{'='*100}")
        print(f"📋 Data Flow Summary")
        print(f"{'='*100}")
        print(f"Session ID: {self.session_id}")
        print(f"Total steps: {len(self.session_log)}")
        print(f"\nProcessing flow:")
        for i, step in enumerate(summary["steps_summary"], 1):
            print(f"  {i}. {step['step']}")
            print(f"     Processing: {step['processing']}")
        print(f"{'='*100}\n")
        
        return summary


# 全局实例
data_flow_logger = DataFlowLogger()
