"""
Simple Logger - Only shows key trading information
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

class SimpleLogger:
    """Simplified logger - only outputs key information"""
    
    def __init__(self):
        self.logger = logging.getLogger('llm_tradebot')
        self.logger.setLevel(logging.INFO)
        
        # Muted patterns list
        self.muted_patterns = [
            "Save JSON", "Save CSV", "Save Parquet",
            "Step1 data saved", "Step2 data saved", "Step3 data saved",
            "Feature engineering complete", "Starting feature engineering",
            "Warm-up flag", "Starting validation", "Data validation passed",
            "Snapshot generated", "Processing K-lines"
        ]
        
    def should_mute(self, message: str) -> bool:
        """Check if message should be muted"""
        return any(pattern in message for pattern in self.muted_patterns)
    
    def info(self, message: str, force: bool = False):
        """Output INFO level log (key info will be forced to show)"""
        if force or not self.should_mute(message):
            print(f"{datetime.now().strftime('%H:%M:%S')} | {message}")
    
    def warning(self, message: str):
        """Output WARNING level log"""
        print(f"⚠️  {datetime.now().strftime('%H:%M:%S')} | {message}")
    
    def error(self, message: str):
        """Output ERROR level log"""
        print(f"❌ {datetime.now().strftime('%H:%M:%S')} | {message}")
    
    def success(self, message: str):
        """Output success message"""
        print(f"✅ {datetime.now().strftime('%H:%M:%S')} | {message}")
    
    def section(self, title: str):
        """Output section title"""
        print(f"\n{'='*80}")
        print(f"🔄 {title} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
    
    def step(self, step_name: str, details: Optional[dict] = None):
        """Output step information (simplified)"""
        print(f"\n📊 {step_name}")
        if details:
            for key, value in details.items():
                print(f"   {key}: {value}")

# Global instance
simple_log = SimpleLogger()
