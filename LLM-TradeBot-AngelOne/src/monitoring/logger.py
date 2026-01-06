"""
Logging and Monitoring Module - Compatible with PostgreSQL (Railway) and SQLite (Local)
"""
import os
import json
from typing import Dict, List
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from src.utils.logger import log


class TradingLogger:
    """Trading Logger (supports Postgres & SQLite)"""
    
    def __init__(self, db_path: str = "logs/trading.db"):
        # 1. Try to get database URL from environment variable (Railway auto-injects DATABASE_URL)
        self.db_url = os.getenv("DATABASE_URL")
        self.is_postgres = False
        
        # 2. If no DATABASE_URL, fall back to local SQLite
        if not self.db_url:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.db_url = f"sqlite:///{self.db_path}"
            log.info(f"⚠️ DATABASE_URL not found, using local SQLite: {self.db_path}")
        else:
            # Fix URL format (SQLAlchemy requires postgresql://)
            if self.db_url.startswith("postgres://"):
                self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
            self.is_postgres = True
            log.info("✅ DATABASE_URL detected, connecting to PostgreSQL...")

        # 3. Initialize database engine
        try:
            self.engine = create_engine(self.db_url)
            self._init_database()
            log.info(f"Trading logger initialized, using: {'PostgreSQL' if self.is_postgres else 'SQLite'}")
        except Exception as e:
            log.error(f"❌ Database connection failed: {e}")
            raise e
    
    def _init_database(self):
        """Initialize database table structure"""
        # Check if tables exist
        insp = inspect(self.engine)
        
        # Auto-increment primary key syntax for different databases
        if self.is_postgres:
            id_type = "SERIAL"
        else:
            id_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
        
        # Define table creation SQL
        tables = {
            "decisions": f"""
                CREATE TABLE IF NOT EXISTS decisions (
                    id {id_type},
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence INTEGER,
                    leverage INTEGER,
                    position_size_pct REAL,
                    stop_loss_pct REAL,
                    take_profit_pct REAL,
                    reasoning TEXT,
                    market_context TEXT,
                    llm_raw_output TEXT,
                    risk_validated BOOLEAN,
                    risk_message TEXT
                    {', PRIMARY KEY (id)' if self.is_postgres else ''}
                )
            """,
            "executions": f"""
                CREATE TABLE IF NOT EXISTS executions (
                    id {id_type},
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    success BOOLEAN,
                    entry_price REAL,
                    quantity REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    orders_data TEXT,
                    message TEXT
                    {', PRIMARY KEY (id)' if self.is_postgres else ''}
                )
            """,
            "trades": f"""
                CREATE TABLE IF NOT EXISTS trades (
                    id {id_type},
                    open_time TEXT NOT NULL,
                    close_time TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL,
                    exit_price REAL,
                    quantity REAL,
                    leverage INTEGER,
                    pnl REAL,
                    pnl_pct REAL,
                    status TEXT
                    {', PRIMARY KEY (id)' if self.is_postgres else ''}
                )
            """,
            "performance": f"""
                CREATE TABLE IF NOT EXISTS performance (
                    id {id_type},
                    timestamp TEXT NOT NULL,
                    total_trades INTEGER,
                    winning_trades INTEGER,
                    losing_trades INTEGER,
                    win_rate REAL,
                    total_pnl REAL,
                    sharpe_ratio REAL,
                    max_drawdown_pct REAL,
                    account_balance REAL
                    {', PRIMARY KEY (id)' if self.is_postgres else ''}
                )
            """
        }

        # Execute table creation
        with self.engine.begin() as conn:
            for table_name, sql in tables.items():
                if not insp.has_table(table_name):
                    conn.execute(text(sql))

    def log_decision(self, decision: Dict, market_context: Dict, risk_result: tuple):
        """Record decision"""
        is_valid, modified_decision, risk_message = risk_result
        
        sql = text('''
            INSERT INTO decisions (
                timestamp, symbol, action, confidence, leverage,
                position_size_pct, stop_loss_pct, take_profit_pct,
                reasoning, market_context, llm_raw_output,
                risk_validated, risk_message
            ) VALUES (:timestamp, :symbol, :action, :confidence, :leverage,
                :position_size_pct, :stop_loss_pct, :take_profit_pct,
                :reasoning, :market_context, :llm_raw_output,
                :risk_validated, :risk_message)
        ''')
        
        with self.engine.begin() as conn:
            conn.execute(sql, {
                'timestamp': decision.get('timestamp'),
                'symbol': decision.get('symbol'),
                'action': decision.get('action'),
                'confidence': decision.get('confidence'),
                'leverage': decision.get('leverage'),
                'position_size_pct': decision.get('position_size_pct'),
                'stop_loss_pct': decision.get('stop_loss_pct'),
                'take_profit_pct': decision.get('take_profit_pct'),
                'reasoning': decision.get('reasoning'),
                'market_context': json.dumps(market_context),
                'llm_raw_output': decision.get('raw_response', ''),
                'risk_validated': is_valid,
                'risk_message': risk_message
            })
        
        log.info(f"Decision recorded: {decision.get('action')}")
    
    def log_execution(self, execution_result: Dict):
        """Record execution result"""
        sql = text('''
            INSERT INTO executions (
                timestamp, symbol, action, success,
                entry_price, quantity, stop_loss, take_profit,
                orders_data, message
            ) VALUES (:timestamp, :symbol, :action, :success,
                :entry_price, :quantity, :stop_loss, :take_profit,
                :orders_data, :message)
        ''')
        
        with self.engine.begin() as conn:
            conn.execute(sql, {
                'timestamp': execution_result.get('timestamp'),
                'symbol': execution_result.get('symbol', ''),
                'action': execution_result.get('action'),
                'success': execution_result.get('success'),
                'entry_price': execution_result.get('entry_price'),
                'quantity': execution_result.get('quantity'),
                'stop_loss': execution_result.get('stop_loss'),
                'take_profit': execution_result.get('take_profit'),
                'orders_data': json.dumps(execution_result.get('orders', [])),
                'message': execution_result.get('message')
            })
        
        log.info(f"Execution recorded: {execution_result.get('action')}")
    
    def open_trade(self, trade_info: Dict):
        """Open new trade"""
        sql = text('''
            INSERT INTO trades (
                open_time, symbol, side, entry_price, quantity, leverage, status
            ) VALUES (:open_time, :symbol, :side, :entry_price, :quantity, :leverage, :status)
        ''')
        
        with self.engine.begin() as conn:
            conn.execute(sql, {
                'open_time': trade_info.get('timestamp'),
                'symbol': trade_info.get('symbol'),
                'side': trade_info.get('side'),
                'entry_price': trade_info.get('entry_price'),
                'quantity': trade_info.get('quantity'),
                'leverage': trade_info.get('leverage', 1),
                'status': 'OPEN'
            })
    
    def close_trade(self, symbol: str, exit_price: float, pnl: float):
        """Close trade"""
        with self.engine.begin() as conn:
            # 1. Find the most recent unclosed trade
            select_sql = text('''
                SELECT id, entry_price FROM trades
                WHERE symbol = :symbol AND status = 'OPEN'
                ORDER BY id DESC LIMIT 1
            ''')
            result = conn.execute(select_sql, {'symbol': symbol}).fetchone()
            
            if result:
                trade_id, entry_price = result
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                
                # 2. Update trade status
                update_sql = text('''
                    UPDATE trades
                    SET close_time = :close_time, exit_price = :exit_price, 
                        pnl = :pnl, pnl_pct = :pnl_pct, status = 'CLOSED'
                    WHERE id = :id
                ''')
                
                conn.execute(update_sql, {
                    'close_time': datetime.now().isoformat(),
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'id': trade_id
                })
    
    def log_performance(self, performance: Dict):
        """Record performance metrics"""
        sql = text('''
            INSERT INTO performance (
                timestamp, total_trades, winning_trades, losing_trades,
                win_rate, total_pnl, sharpe_ratio, max_drawdown_pct, account_balance
            ) VALUES (:timestamp, :total_trades, :winning_trades, :losing_trades,
                :win_rate, :total_pnl, :sharpe_ratio, :max_drawdown_pct, :account_balance)
        ''')
        
        with self.engine.begin() as conn:
            conn.execute(sql, {
                'timestamp': datetime.now().isoformat(),
                'total_trades': performance.get('total_trades', 0),
                'winning_trades': performance.get('winning_trades', 0),
                'losing_trades': performance.get('losing_trades', 0),
                'win_rate': performance.get('win_rate', 0),
                'total_pnl': performance.get('total_pnl', 0),
                'sharpe_ratio': performance.get('sharpe_ratio', 0),
                'max_drawdown_pct': performance.get('max_drawdown_pct', 0),
                'account_balance': performance.get('account_balance', 0)
            })
    
    def get_recent_decisions(self, limit: int = 10) -> List[Dict]:
        """Get recent decisions"""
        sql = text('SELECT * FROM decisions ORDER BY id DESC LIMIT :limit')
        
        with self.engine.connect() as conn:
            result = conn.execute(sql, {'limit': limit})
            return [dict(row._mapping) for row in result]
    
    def get_trade_statistics(self) -> Dict:
        """Get trade statistics"""
        with self.engine.connect() as conn:
            total_trades = conn.execute(text("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED'")).scalar() or 0
            winning_trades = conn.execute(text("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED' AND pnl > 0")).scalar() or 0
            losing_trades = conn.execute(text("SELECT COUNT(*) FROM trades WHERE status = 'CLOSED' AND pnl < 0")).scalar() or 0
            total_pnl = conn.execute(text("SELECT SUM(pnl) FROM trades WHERE status = 'CLOSED'")).scalar() or 0
        
        win_rate = (winning_trades / total_trades * 100) if total_trades and total_trades > 0 else 0
        
        return {
            'total_trades': total_trades or 0,
            'winning_trades': winning_trades or 0,
            'losing_trades': losing_trades or 0,
            'win_rate': win_rate,
            'total_pnl': total_pnl
        }
