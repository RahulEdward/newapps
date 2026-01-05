"""
Trade Logger - Records detailed data for each position open/close
"""
import json
import os
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path
from src.utils.json_utils import safe_json_dump, safe_json_dumps


class TradeLogger:
    """Trade Logger"""
    
    def __init__(self, log_dir: str = "data/execution/tracking"):
        """
        Initialize trade logger
        
        Args:
            log_dir: Log directory
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.log_dir / "daily").mkdir(exist_ok=True)
        (self.log_dir / "positions").mkdir(exist_ok=True)
        (self.log_dir / "summary").mkdir(exist_ok=True)
    
    def log_open_position(
        self,
        symbol: str,
        side: str,  # LONG or SHORT
        decision: Dict,
        execution_result: Dict,
        market_state: Dict,
        account_info: Dict
    ) -> str:
        """
        Log position open information
        
        Args:
            symbol: Trading pair
            side: Direction (LONG/SHORT)
            decision: Decision information
            execution_result: Execution result
            market_state: Market state
            account_info: Account information
            
        Returns:
            Log file path
        """
        timestamp = datetime.now()
        trade_id = f"{symbol}_{side}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        # Build complete trade record
        trade_record = {
            # Basic info
            "trade_id": trade_id,
            "timestamp": timestamp.isoformat(),
            "date": timestamp.strftime('%Y-%m-%d'),
            "time": timestamp.strftime('%H:%M:%S'),
            
            # Trade info
            "symbol": symbol,
            "side": side,
            "action": "OPEN",
            
            # Decision info
            "decision": {
                "action": decision.get('action'),
                "position_size_pct": decision.get('position_size_pct'),
                "leverage": decision.get('leverage'),
                "stop_loss_pct": decision.get('stop_loss_pct'),
                "take_profit_pct": decision.get('take_profit_pct'),
            },
            
            # Execution result
            "execution": {
                "success": execution_result.get('success'),
                "entry_price": execution_result.get('entry_price'),
                "quantity": execution_result.get('quantity'),
                "stop_loss": execution_result.get('stop_loss'),
                "take_profit": execution_result.get('take_profit'),
                "order_id": execution_result.get('order_id'),
                "orders": execution_result.get('orders', [])
            },
            
            # Market state (summary)
            "market_state": self._extract_market_summary(market_state),
            
            # Account info
            "account": {
                "balance_before": account_info.get('available_balance'),
                "position_value": execution_result.get('entry_price', 0) * execution_result.get('quantity', 0),
                "margin_used": (execution_result.get('entry_price', 0) * execution_result.get('quantity', 0)) / decision.get('leverage', 1),
            },
            
            # Risk assessment
            "risk": {
                "max_loss_usd": self._calculate_max_loss(execution_result, decision),
                "max_loss_pct": decision.get('stop_loss_pct'),
                "potential_profit_usd": self._calculate_potential_profit(execution_result, decision),
                "potential_profit_pct": decision.get('take_profit_pct'),
                "risk_reward_ratio": decision.get('take_profit_pct', 0) / max(decision.get('stop_loss_pct', 1), 0.1),
            },
            
            # Status
            "status": "OPEN",
            "close_info": None
        }
        
        # Save to individual position file
        position_file = self.log_dir / "positions" / f"{trade_id}.json"
        with open(position_file, 'w', encoding='utf-8') as f:
            safe_json_dump(trade_record, f, indent=2, ensure_ascii=False)
        
        # Append to daily trade log
        daily_file = self.log_dir / "daily" / f"trades_{timestamp.strftime('%Y%m%d')}.jsonl"
        with open(daily_file, 'a', encoding='utf-8') as f:
            f.write(safe_json_dumps(trade_record, ensure_ascii=False) + '\n')
        
        print(f"✅ Trade log saved: {position_file}")
        
        return str(position_file)
    
    def log_close_position(
        self,
        trade_id: str,
        close_price: float,
        close_reason: str,  # STOP_LOSS, TAKE_PROFIT, MANUAL
        pnl: float,
        pnl_pct: float,
        account_balance_after: float
    ) -> str:
        """
        Log position close information
        
        Args:
            trade_id: Trade ID
            close_price: Close price
            close_reason: Close reason
            pnl: Profit/Loss amount
            pnl_pct: Profit/Loss percentage
            account_balance_after: Account balance after close
            
        Returns:
            Log file path
        """
        timestamp = datetime.now()
        
        # Read original position record
        position_file = self.log_dir / "positions" / f"{trade_id}.json"
        
        if not position_file.exists():
            print(f"⚠️  Warning: Position record not found {trade_id}")
            return ""
        
        with open(position_file, 'r', encoding='utf-8') as f:
            trade_record = json.load(f)
        
        # Update close info
        trade_record["status"] = "CLOSED"
        trade_record["close_info"] = {
            "close_timestamp": timestamp.isoformat(),
            "close_date": timestamp.strftime('%Y-%m-%d'),
            "close_time": timestamp.strftime('%H:%M:%S'),
            "close_price": close_price,
            "close_reason": close_reason,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "account_balance_after": account_balance_after,
            "holding_duration_seconds": (timestamp - datetime.fromisoformat(trade_record["timestamp"])).total_seconds()
        }
        
        # Update position file
        with open(position_file, 'w', encoding='utf-8') as f:
            safe_json_dump(trade_record, f, indent=2, ensure_ascii=False)
        
        # Append to daily trade log
        daily_file = self.log_dir / "daily" / f"trades_{timestamp.strftime('%Y%m%d')}.jsonl"
        with open(daily_file, 'a', encoding='utf-8') as f:
            f.write(safe_json_dumps(trade_record, ensure_ascii=False) + '\n')
        
        # Update trade summary
        self._update_summary(trade_record)
        
        print(f"✅ Close log saved: {position_file}")
        print(f"   PnL: ${pnl:+.2f} ({pnl_pct:+.2f}%)")
        
        return str(position_file)
    
    def _extract_market_summary(self, market_state: Dict) -> Dict:
        """Extract market state summary"""
        timeframes = market_state.get('timeframes', {})
        
        summary = {
            "current_price": market_state.get('current_price'),
            "timeframes": {}
        }
        
        for tf, data in timeframes.items():
            summary["timeframes"][tf] = {
                "price": data.get('price'),
                "rsi": data.get('rsi'),
                "macd": data.get('macd'),
                "trend": data.get('trend')
            }
        
        return summary
    
    def _calculate_max_loss(self, execution_result: Dict, decision: Dict) -> float:
        """Calculate maximum loss"""
        entry_price = execution_result.get('entry_price', 0)
        quantity = execution_result.get('quantity', 0)
        leverage = decision.get('leverage', 1)
        stop_loss_pct = decision.get('stop_loss_pct', 0)
        
        position_value = entry_price * quantity
        max_loss = position_value * leverage * (stop_loss_pct / 100)
        
        return max_loss
    
    def _calculate_potential_profit(self, execution_result: Dict, decision: Dict) -> float:
        """Calculate potential profit"""
        entry_price = execution_result.get('entry_price', 0)
        quantity = execution_result.get('quantity', 0)
        leverage = decision.get('leverage', 1)
        take_profit_pct = decision.get('take_profit_pct', 0)
        
        position_value = entry_price * quantity
        potential_profit = position_value * leverage * (take_profit_pct / 100)
        
        return potential_profit
    
    def _update_summary(self, trade_record: Dict):
        """Update trade summary statistics"""
        summary_file = self.log_dir / "summary" / "trading_summary.json"
        
        # Read existing summary
        if summary_file.exists():
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary = json.load(f)
        else:
            summary = {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_pnl": 0,
                "total_pnl_pct": 0,
                "best_trade": None,
                "worst_trade": None,
                "last_updated": None
            }
        
        # Only count closed trades
        if trade_record["status"] == "CLOSED" and trade_record["close_info"]:
            close_info = trade_record["close_info"]
            pnl = close_info["pnl"]
            
            summary["total_trades"] += 1
            summary["total_pnl"] += pnl
            
            if pnl > 0:
                summary["winning_trades"] += 1
            elif pnl < 0:
                summary["losing_trades"] += 1
            
            # Update best/worst trade
            if summary["best_trade"] is None or pnl > summary["best_trade"]["pnl"]:
                summary["best_trade"] = {
                    "trade_id": trade_record["trade_id"],
                    "pnl": pnl,
                    "pnl_pct": close_info["pnl_pct"],
                    "timestamp": close_info["close_timestamp"]
                }
            
            if summary["worst_trade"] is None or pnl < summary["worst_trade"]["pnl"]:
                summary["worst_trade"] = {
                    "trade_id": trade_record["trade_id"],
                    "pnl": pnl,
                    "pnl_pct": close_info["pnl_pct"],
                    "timestamp": close_info["close_timestamp"]
                }
            
            # Calculate win rate
            summary["win_rate"] = (summary["winning_trades"] / summary["total_trades"]) * 100 if summary["total_trades"] > 0 else 0
            
            # Calculate average PnL
            summary["avg_pnl"] = summary["total_pnl"] / summary["total_trades"] if summary["total_trades"] > 0 else 0
            
            summary["last_updated"] = datetime.now().isoformat()
        
        # Save updated summary
        with open(summary_file, 'w', encoding='utf-8') as f:
            safe_json_dump(summary, f, indent=2, ensure_ascii=False)
    
    def get_open_positions(self) -> list:
        """Get all open positions"""
        positions_dir = self.log_dir / "positions"
        open_positions = []
        
        for position_file in positions_dir.glob("*.json"):
            with open(position_file, 'r', encoding='utf-8') as f:
                trade_record = json.load(f)
                if trade_record["status"] == "OPEN":
                    open_positions.append(trade_record)
        
        return open_positions
    
    def get_daily_summary(self, date: Optional[str] = None) -> Dict:
        """
        Get daily trade summary
        
        Args:
            date: Date (YYYYMMDD), defaults to today
            
        Returns:
            Daily trade statistics
        """
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        daily_file = self.log_dir / "daily" / f"trades_{date}.jsonl"
        
        if not daily_file.exists():
            return {
                "date": date,
                "total_trades": 0,
                "trades": []
            }
        
        trades = []
        with open(daily_file, 'r', encoding='utf-8') as f:
            for line in f:
                trades.append(json.loads(line))
        
        return {
            "date": date,
            "total_trades": len(trades),
            "trades": trades
        }
    
    def export_to_csv(self, output_file: str):
        """
        Export trade records to CSV format for Excel analysis
        
        Args:
            output_file: Output file path
        """
        import csv
        
        positions_dir = self.log_dir / "positions"
        trades = []
        
        for position_file in positions_dir.glob("*.json"):
            with open(position_file, 'r', encoding='utf-8') as f:
                trade = json.load(f)
                trades.append(trade)
        
        # Sort by time
        trades.sort(key=lambda x: x["timestamp"])
        
        # Write CSV
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'Trade ID', 'Date', 'Time', 'Symbol', 'Side', 'Status',
                'Entry Price', 'Quantity', 'Leverage', 'Stop Loss', 'Take Profit',
                'Close Price', 'Close Reason', 'PnL', 'PnL%',
                'Holding Duration(s)', 'Max Loss', 'Potential Profit', 'Risk Reward Ratio'
            ])
            
            # Data rows
            for trade in trades:
                close_info = trade.get("close_info") or {}
                
                writer.writerow([
                    trade["trade_id"],
                    trade["date"],
                    trade["time"],
                    trade["symbol"],
                    trade["side"],
                    trade["status"],
                    trade["execution"]["entry_price"],
                    trade["execution"]["quantity"],
                    trade["decision"]["leverage"],
                    trade["execution"]["stop_loss"],
                    trade["execution"]["take_profit"],
                    close_info.get("close_price", ""),
                    close_info.get("close_reason", ""),
                    close_info.get("pnl", ""),
                    close_info.get("pnl_pct", ""),
                    close_info.get("holding_duration_seconds", ""),
                    trade["risk"]["max_loss_usd"],
                    trade["risk"]["potential_profit_usd"],
                    trade["risk"]["risk_reward_ratio"]
                ])
        
        print(f"✅ Trade records exported to: {output_file}")


# Global instance
trade_logger = TradeLogger()
