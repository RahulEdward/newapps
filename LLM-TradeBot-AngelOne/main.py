"""
🤖 LLM-TradeBot - Multi-Agent Architecture Main Loop
=====================================================

Integration:
1. 🕵️ DataSyncAgent - Async concurrent data collection
2. 👨‍🔬 QuantAnalystAgent - Quantitative signal analysis
3. ⚖️ DecisionCoreAgent - Weighted voting decision
4. 👮 RiskAuditAgent - Risk control audit interception

Optimizations:
- Async concurrent execution (60% reduction in wait time)
- Dual-view data structure (stable + live)
- Layered signal analysis (trend + oscillation)
- Multi-timeframe aligned decisions
- Auto-correction of stop-loss direction
- Veto-based risk control

Author: AI Trader Team
Date: 2025-12-19
"""

import asyncio
import sys
import os
from dotenv import load_dotenv
load_dotenv(override=True) # Ensure .env overrides shell environment

# Deployment mode detection: 'local' or 'railway'
# Railway deployment sets RAILWAY_ENVIRONMENT, use that as detection
DEPLOYMENT_MODE = os.environ.get('DEPLOYMENT_MODE', 'railway' if os.environ.get('RAILWAY_ENVIRONMENT') else 'local')

# Configure based on deployment mode
if DEPLOYMENT_MODE == 'local':
    # Local deployment: Prefer REST API for data fetching (more stable for local dev)
    if 'USE_WEBSOCKET' not in os.environ:
        os.environ['USE_WEBSOCKET'] = 'false'
    # Enable detailed LLM logging
    os.environ['ENABLE_DETAILED_LLM_LOGS'] = 'true'
else:
    # Railway deployment: Also use REST API for stability
    if 'USE_WEBSOCKET' not in os.environ:
        os.environ['USE_WEBSOCKET'] = 'false'
    # Disable detailed LLM logging to save disk space
    os.environ['ENABLE_DETAILED_LLM_LOGS'] = 'false'

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from typing import Dict, Optional, List
from datetime import datetime
import json
import time
import threading
import signal
from dataclasses import asdict

# AngelOne Integration - Replace Binance with AngelOne client
from src.api.angelone.angelone_client import AngelOneClient
from src.api.angelone.market_hours import MarketHoursManager
from src.execution.engine import ExecutionEngine
from src.risk.manager import RiskManager
from src.utils.logger import log, setup_logger
from src.utils.trade_logger import trade_logger
from src.utils.data_saver import DataSaver
from src.data.processor import MarketDataProcessor  # ✅ Corrected Import
from src.exchanges import AccountManager, ExchangeAccount, ExchangeType  # ✅ Multi-Account Support
from src.features.technical_features import TechnicalFeatureEngineer
from src.server.state import global_state
from src.utils.semantic_converter import SemanticConverter  # ✅ Global Import
from src.agents.regime_detector import RegimeDetector  # ✅ Market Regime Detection
from src.config import Config # Re-added Config as it's used later

# FastAPI dependencies
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import Multi-Agents
from src.agents import (
    DataSyncAgent,
    QuantAnalystAgent,
    DecisionCoreAgent,
    RiskAuditAgent,
    PositionInfo,
    SignalWeight,
    ReflectionAgent
)
from src.strategy.llm_engine import StrategyEngine
from src.agents.predict_agent import PredictAgent
from src.server.app import app
from src.server.state import global_state

# ✅ [NEW] Import TradingLogger for database initialization
from src.monitoring.logger import TradingLogger

class MultiAgentTradingBot:
    """
    Multi-Agent Trading Bot (Refactored Version)
    
    Workflow:
    1. DataSyncAgent: Async collection of 5m/15m/1h data
    2. QuantAnalystAgent: Generate quantitative signals (trend + oscillation)
    3. DecisionCoreAgent: Weighted voting decision
    4. RiskAuditAgent: Risk control audit interception
    5. ExecutionEngine: Execute trades
    """
    
    def __init__(
        self,
        max_position_size: float = 100.0,
        leverage: int = 1,
        stop_loss_pct: float = 1.0,
        take_profit_pct: float = 2.0,
        test_mode: bool = False
    ):
        """
        Initialize Multi-Agent Trading Bot
        
        Args:
            max_position_size: Maximum single trade amount (USDT)
            leverage: Leverage multiplier
            stop_loss_pct: Stop loss percentage
            take_profit_pct: Take profit percentage
            test_mode: Test mode (no real trades executed)
        """
        print("\n" + "="*80)
        print(f"🤖 AI Trader - DeepSeek LLM Decision Mode")
        print("="*80)
        
        self.config = Config()
        
        # Multi-symbol support: Priority order
        # 1. Environment variable TRADING_SYMBOLS (from .env, Dashboard settings update this)
        # 2. trading.symbols in config.yaml (list)
        # 3. trading.symbol in config.yaml (str/csv, backward compatible)
        env_symbols = os.environ.get('TRADING_SYMBOLS', '').strip()
        
        if env_symbols:
            # Dashboard configured symbols (comma separated)
            self.symbols = [s.strip() for s in env_symbols.split(',') if s.strip()]
        else:
            # Read from config.yaml
            symbols_config = self.config.get('trading.symbols', None)
            
            if symbols_config and isinstance(symbols_config, list):
                # Handle both string list and dict list formats
                self.symbols = []
                for s in symbols_config:
                    if isinstance(s, dict):
                        self.symbols.append(s.get('symbol', str(s)))
                    else:
                        self.symbols.append(str(s))
            else:
                # Backward compatible: Use legacy trading.symbol config (supports CSV string "BTCUSDT,ETHUSDT")
                symbol_str = self.config.get('trading.symbol', 'RELIANCE')  # Default to RELIANCE for Indian market
                if ',' in symbol_str:
                    self.symbols = [s.strip() for s in symbol_str.split(',') if s.strip()]
                else:
                    self.symbols = [symbol_str]

        # 🤖 AI500 Dynamic Resolution (disabled for Indian market)
        self.use_ai500 = False  # AI500 is crypto-specific
        self.ai500_last_update = None
        self.ai500_update_interval = 6 * 3600  # 6 hours in seconds
        
        if self.use_ai500:
            self.symbols.remove('AI500_TOP5')
            ai_top5 = self._resolve_ai500_symbols()
            # Merge and deduplicate
            self.symbols = list(set(self.symbols + ai_top5))
            # Sort to keep stable order
            self.symbols.sort()
            self.ai500_last_update = time.time()
            
            # Start background thread for periodic updates
            self._start_ai500_updater()
                
        # 🔧 Primary symbol must be in the symbols list
        configured_primary = self.config.get('trading.primary_symbol', 'BTCUSDT')
        if configured_primary in self.symbols:
            self.primary_symbol = configured_primary
        else:
            # Use first symbol if configured primary not in list
            self.primary_symbol = self.symbols[0]
            log.info(f"Primary symbol {configured_primary} not in symbols list, using {self.primary_symbol}")
        
        self.current_symbol = self.primary_symbol  # Currently processing trading pair
        self.test_mode = test_mode
        global_state.is_test_mode = test_mode  # Set test mode in global state
        global_state.symbols = self.symbols  # 🆕 Sync symbols to global state for API
        
        # Trading parameters
        self.max_position_size = max_position_size
        self.leverage = leverage
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        
        
        # Initialize clients - AngelOne for Indian market
        self.market_hours = MarketHoursManager()
        
        # AngelOne client - credentials from database (set via UI)
        # Client will be set when user connects via dashboard
        self._init_client = None  # Will be set from global_state.exchange_client when broker connects
        self.demo_mode = True  # Start in demo mode, switch when broker connects
        print("  💡 Connect to AngelOne broker from Dashboard to enable live trading")
        
        self.risk_manager = RiskManager()
        self.execution_engine = ExecutionEngine(self._init_client, self.risk_manager)
        self.saver = DataSaver() # ✅ Initialize Multi-Agent data saver

        # 💰 Persistent Virtual Account (Test Mode)
        if self.test_mode:
            saved_va = self.saver.load_virtual_account()
            if saved_va:
                global_state.virtual_balance = saved_va.get('balance', 1000.0)
                global_state.virtual_positions = saved_va.get('positions', {})
                log.info(f"💰 Loaded persistent virtual account: Bal=${global_state.virtual_balance:.2f}, Pos={list(global_state.virtual_positions.keys())}")
        global_state.saver = self.saver # ✅ Share saver to global state for use by all Agents
        
        
        # ✅ Initialize multi-account manager
        self.account_manager = AccountManager()
        self._init_accounts()
        # Initialize mtime for .env tracking (skip if not exists, e.g. Railway)
        self._env_mtime = 0
        self._env_path = os.path.join(os.path.dirname(__file__), '.env')
        self._env_exists = os.path.exists(self._env_path)  # 🔧 Railway fix
        
        # Initialize shared Agents (symbol-independent)
        print("\n🚀 Initializing agents...")
        self.data_sync_agent = DataSyncAgent(self.client)
        self.quant_analyst = QuantAnalystAgent()
        # self.decision_core = DecisionCoreAgent() # Deprecated in DeepSeek Mode
        self.risk_audit = RiskAuditAgent(
            max_leverage=10.0,
            max_position_pct=0.3,
            min_stop_loss_pct=0.005,
            max_stop_loss_pct=0.05
        )
        self.processor = MarketDataProcessor()  # ✅ Initialize data processor
        self.feature_engineer = TechnicalFeatureEngineer()  # 🔮 Feature engineer for Prophet
        # 🔧 FIX M4: Cache RegimeDetector to avoid per-cycle reinstantiation
        from src.agents.regime_detector import RegimeDetector
        self.regime_detector = RegimeDetector()  # 📊 Market regime detector
        
        # 🔮 Create independent PredictAgent for each symbol
        self.predict_agents = {}
        for symbol in self.symbols:
            self.predict_agents[symbol] = PredictAgent(horizon='30m', symbol=symbol)
        
        print("  ✅ DataSyncAgent ready")
        print("  ✅ QuantAnalystAgent ready")
        print(f"  ✅ PredictAgent ready ({len(self.symbols)} symbols)")
        print("  ✅ RiskAuditAgent ready")
        
        # 🧠 DeepSeek Decision Engine
        self.strategy_engine = StrategyEngine()
        if self.strategy_engine.is_ready:
            print("  ✅ DeepSeek StrategyEngine ready")
        else:
            print("  ⚠️ DeepSeek StrategyEngine not ready (Awaiting API Key)")
            
        # 🧠 Reflection Agent - Trade Reflection
        self.reflection_agent = ReflectionAgent()
        print("  ✅ ReflectionAgent ready")
        
        print(f"\n⚙️  Trading Config:")
        print(f"  - Symbols: {', '.join(self.symbols)}")
        print(f"  - Max Position: ${self.max_position_size:.2f} USDT")
        print(f"  - Leverage: {self.leverage}x")
        print(f"  - Stop Loss: {self.stop_loss_pct}%")
        print(f"  - Take Profit: {self.take_profit_pct}%")
        print(f"  - Test Mode: {'✅ Yes' if self.test_mode else '❌ No'}")
        
        # ✅ Load initial trade history (Only in Live Mode)
        if not self.test_mode:
            recent_trades = self.saver.get_recent_trades(limit=20)
            global_state.trade_history = recent_trades
            print(f"  📜 Loaded {len(recent_trades)} historical trades")
        else:
            global_state.trade_history = []
            print("  🧪 Test mode: No history loaded, showing only current session")

    @property
    def client(self):
        """Get active client - checks global_state.exchange_client if init client is None"""
        # If we have an init client, use it
        if self._init_client is not None:
            return self._init_client
        
        # Otherwise check global_state for broker client (set when user connects via UI)
        if global_state.exchange_client is not None:
            return global_state.exchange_client
        
        return None
    
    @client.setter
    def client(self, value):
        """Set the client"""
        self._init_client = value

    def _reload_symbols(self):
        """Reload trading symbols from environment/config without restart"""
        # Note: On Railway, os.environ is already updated by config_manager.
        # On local, load_dotenv refreshes from .env file.
        if self._env_exists:
            load_dotenv(override=True)
        
        env_symbols = os.environ.get('TRADING_SYMBOLS', '').strip()
        
        old_symbols = self.symbols.copy()
        
        if env_symbols:
            self.symbols = [s.strip() for s in env_symbols.split(',') if s.strip()]
        else:
            symbols_config = self.config.get('trading.symbols', None)
            if symbols_config and isinstance(symbols_config, list):
                self.symbols = symbols_config
            else:
                symbol_str = self.config.get('trading.symbol', 'AI500_TOP5')
                if ',' in symbol_str:
                    self.symbols = [s.strip() for s in symbol_str.split(',') if s.strip()]
                else:
                    self.symbols = [symbol_str]

        # 🤖 AI500 Dynamic Resolution
        if 'AI500_TOP5' in self.symbols:
            self.symbols.remove('AI500_TOP5')
            ai_top5 = self._resolve_ai500_symbols()
            self.symbols = list(set(self.symbols + ai_top5))
            self.symbols.sort()
            
        if set(self.symbols) != set(old_symbols):
            log.info(f"🔄 Trading symbols reloaded: {', '.join(self.symbols)}")
            global_state.add_log(f"[🔄 CONFIG] Symbols reloaded: {', '.join(self.symbols)}")
            # Update global state
            global_state.symbols = self.symbols
            # Initialize PredictAgent for any new symbols
            for symbol in self.symbols:
                if symbol not in self.predict_agents:
                    from src.agents.predict_agent import PredictAgent
                    self.predict_agents[symbol] = PredictAgent(symbol)
                    log.info(f"🆕 Initialized PredictAgent for {symbol}")

    def _resolve_ai500_symbols(self):
        """Dynamic resolution of AI500_TOP5 tag"""
        # AI Candidates List (30+ Major AI/Data/Compute Coins)
        AI_CANDIDATES = [
            "FETUSDT", "RENDERUSDT", "TAOUSDT", "NEARUSDT", "GRTUSDT", 
            "WLDUSDT", "ARKMUSDT", "LPTUSDT", "THETAUSDT", "ROSEUSDT",
            # Removed merged/renamed: AGIX, OCEAN, RNDR (now FET/RENDER)
            "PHBUSDT", "CTXCUSDT", "NMRUSDT", "RLCUSDT", "GLMUSDT",
            "IQUSDT", "MDTUSDT", "AIUSDT", "NFPUSDT", "XAIUSDT",
            "JASMYUSDT", "ICPUSDT", "FILUSDT", "VETUSDT", "LINKUSDT",
            "ACTUSDT", "GOATUSDT", "TURBOUSDT", "PNUTUSDT" 
        ]
        
        try:
            print("🤖 AI500 Dynamic Selection: Fetching 24h Volume Data...")
            # Use temporary client to fetch tickers
            temp_client = AngelOneClient()
            tickers = temp_client.get_all_tickers()
            
            # Filter and Sort
            ai_stats = []
            for t in tickers:
                if t['symbol'] in AI_CANDIDATES:
                    try:
                        quote_vol = float(t['quoteVolume'])
                        ai_stats.append((t['symbol'], quote_vol))
                    except (KeyError, ValueError, TypeError) as e:
                        log.debug(f"Skipped {t.get('symbol', 'unknown')}: {e}")
            
            # Sort by Volume desc
            ai_stats.sort(key=lambda x: x[1], reverse=True)
            
            # Take Top 5
            top_5 = [x[0] for x in ai_stats[:5]]
            
            print(f"✅ AI500 Top 5 Selected (by Vol): {', '.join(top_5)}")
            return top_5
            
        except Exception as e:
            log.error(f"Failed to resolve AI500 symbols: {e}")
            # Fallback to defaults (Top 5)
            return ["FETUSDT", "RENDERUSDT", "TAOUSDT", "NEARUSDT", "GRTUSDT"]
    
    def _start_ai500_updater(self):
        """Start AI500 scheduled update background thread"""
        def updater_loop():
            while True:
                try:
                    # Sleep for 6 hours
                    time.sleep(self.ai500_update_interval)
                    
                    if self.use_ai500:
                        log.info("🔄 AI500 Top5 - Starting scheduled update (every 6h)")
                        new_top5 = self._resolve_ai500_symbols()
                        
                        # Update symbols list
                        old_symbols = set(self.symbols)
                        # Remove old AI coins and add new ones
                        # Keep non-AI coins unchanged
                        major_coins = {'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'}
                        non_ai_symbols = [s for s in self.symbols if s in major_coins]
                        
                        # Merge with new AI top5
                        self.symbols = list(set(non_ai_symbols + new_top5))
                        self.symbols.sort()
                        
                        # Update global state
                        global_state.symbols = self.symbols
                        self.ai500_last_update = time.time()
                        
                        # Log changes
                        added = set(self.symbols) - old_symbols
                        removed = old_symbols - set(self.symbols)
                        if added or removed:
                            log.info(f"📊 AI500 Updated - Added: {added}, Removed: {removed}")
                            log.info(f"📋 Current symbols: {', '.join(self.symbols)}")
                        else:
                            log.info("✅ AI500 Updated - No changes in Top5")
                            
                except Exception as e:
                    log.error(f"AI500 updater error: {e}")
        
        # Start daemon thread
        updater_thread = threading.Thread(target=updater_loop, daemon=True, name="AI500-Updater")
        updater_thread.start()
        log.info(f"🚀 AI500 Auto-updater started (interval: 6 hours)")
    
    
    def _init_accounts(self):
        """
        Initialize trading accounts from config or legacy .env
        
        Priority:
        1. Load from config/accounts.json if exists
        2. Auto-create default account from legacy .env if no accounts loaded
        """
        import os
        from pathlib import Path
        
        config_path = Path(__file__).parent / "config" / "accounts.json"
        
        # Try to load from config file
        loaded = self.account_manager.load_from_file(str(config_path))
        
        if loaded == 0:
            # No accounts.json found - create default from legacy .env
            log.info("No accounts.json found, creating default account from .env")
            
            api_key = os.environ.get('BINANCE_API_KEY', '')
            secret_key = os.environ.get('BINANCE_SECRET_KEY', '')
            testnet = os.environ.get('BINANCE_TESTNET', 'true').lower() == 'true'
            
            if api_key:
                default_account = ExchangeAccount(
                    id='main-binance',
                    user_id='default',
                    exchange_type=ExchangeType.BINANCE,
                    account_name='Main Binance Account',
                    enabled=True,
                    api_key=api_key,
                    secret_key=secret_key,
                    testnet=testnet or self.test_mode
                )
                self.account_manager.add_account(default_account)
                log.info(f"✅ Created default account: {default_account.account_name}")
            else:
                log.warning("No API key found in .env - running in demo mode")
        
        # Log summary
        accounts = self.account_manager.list_accounts(enabled_only=True)
        if accounts:
            print(f"  📊 Loaded {len(accounts)} trading accounts:")
            for acc in accounts:
                print(f"     - {acc.account_name} ({acc.exchange_type.value}, testnet={acc.testnet})")
    
    def get_accounts(self):
        """Get list of enabled trading accounts."""
        return self.account_manager.list_accounts(enabled_only=True)
    
    async def get_trader(self, account_id: str):
        """Get trader instance for a specific account."""
        return await self.account_manager.get_trader(account_id)


    async def run_trading_cycle(self, analyze_only: bool = False) -> Dict:
        """
        Execute complete trading cycle (async version)
        Returns:
            {
                'status': 'success/failed/hold/blocked',
                'action': 'long/short/hold',
                'details': {...}
            }
        """
        print(f"\n{'='*80}")
        print(f"🔄 Starting trading audit cycle | {datetime.now().strftime('%H:%M:%S')} | {self.current_symbol}")
        print(f"{'='*80}")
        
        # 🇮🇳 Market Hours Check - Indian market (9:15 AM - 3:30 PM IST)
        if not self.market_hours.is_market_open():
            next_open = self.market_hours.get_next_market_open()
            print(f"⏰ Market is closed. Next open: {next_open.strftime('%Y-%m-%d %H:%M IST')}")
            global_state.add_log(f"[⏰ MARKET] Closed - Next open: {next_open.strftime('%H:%M IST')}")
            
            # Allow analysis but block live trading
            if not analyze_only:
                return {
                    'status': 'blocked',
                    'action': 'hold',
                    'details': {
                        'reason': 'Market closed',
                        'next_open': next_open.isoformat()
                    }
                }
        
        # Update Dashboard Status
        global_state.is_running = True
        # Removed verbose log: Starting trading cycle
        
        try:
            # ✅ Use cycle info already set in run_continuous
            cycle_num = global_state.cycle_counter
            cycle_id = global_state.current_cycle_id
            
            # Sub-log for each symbol
            global_state.add_log(f"[📊 SYSTEM] {self.current_symbol} analysis started")
            
            # ✅ Generate snapshot_id for this cycle (legacy compatibility)
            snapshot_id = f"snap_{int(time.time())}"

            # Step 1: Sampling - The Oracle (Data Prophet)
            print("\n[Step 1/4] 🕵️ The Oracle (Data Agent) - Fetching data...")
            global_state.oracle_status = "Fetching Data..." 
            market_snapshot = await self.data_sync_agent.fetch_all_timeframes(self.current_symbol)
            global_state.oracle_status = "Data Ready"
            
            # 💰 fetch_position_info logic (New Feature)
            # Create a unified position_info dict for Context
            current_position_info = None
            
            try:
                if self.test_mode:
                    if self.current_symbol in global_state.virtual_positions:
                        v_pos = global_state.virtual_positions[self.current_symbol]
                        # Calc PnL
                        current_price_5m = market_snapshot.live_5m['close']
                        entry_price = v_pos['entry_price']
                        qty = v_pos['quantity']
                        side = v_pos['side']
                        leverage = v_pos.get('leverage', 1)
                        
                        if side == 'LONG':
                            unrealized_pnl = (current_price_5m - entry_price) * qty
                        else:
                            unrealized_pnl = (entry_price - current_price_5m) * qty
                        
                        # Unified ROE (Return on Equity) calculation method
                        # ROE% = (unrealized_pnl / margin) * 100
                        # Where margin = (entry_price * qty) / leverage
                        margin = (entry_price * qty) / leverage if leverage > 0 else entry_price * qty
                        pnl_pct = (unrealized_pnl / margin) * 100 if margin > 0 else 0
                        
                        # Store in position_info
                        current_position_info = {
                            'symbol': self.current_symbol,
                            'side': side,
                            'quantity': qty,
                            'entry_price': entry_price,
                            'unrealized_pnl': unrealized_pnl,
                            'pnl_pct': pnl_pct,  # ROE percentage
                            'leverage': leverage,
                            'is_test': True
                        }
                        
                        # Also update local object for backward compatibility with display logic
                        v_pos['unrealized_pnl'] = unrealized_pnl
                        v_pos['pnl_pct'] = pnl_pct
                        v_pos['current_price'] = current_price_5m
                        log.info(f"💰 [Virtual Position] {side} {self.current_symbol} PnL: ${unrealized_pnl:.2f} (ROE: {pnl_pct:+.2f}%)")
                        
                else:
                    # Live Mode
                    try:
                        raw_pos = self.client.get_futures_position(self.current_symbol)
                        # raw_pos returns dict if specific symbol, or list if not?
                        # BinanceClient.get_futures_position returns Optional[Dict]
                        
                        if raw_pos and float(raw_pos.get('positionAmt', 0)) != 0:
                            amt = float(raw_pos.get('positionAmt', 0))
                            side = 'LONG' if amt > 0 else 'SHORT'
                            entry_price = float(raw_pos.get('entryPrice', 0))
                            unrealized_pnl = float(raw_pos.get('unRealizedProfit', 0))
                            qty = abs(amt)
                            leverage = int(raw_pos.get('leverage', 1))
                            
                            # Unified ROE (Return on Equity) calculation - consistent with test mode
                            margin = (entry_price * qty) / leverage if leverage > 0 else entry_price * qty
                            pnl_pct = (unrealized_pnl / margin) * 100 if margin > 0 else 0
                            
                            current_position_info = {
                                'symbol': self.current_symbol,
                                'side': side,
                                'quantity': qty,
                                'entry_price': entry_price,
                                'unrealized_pnl': unrealized_pnl,
                                'pnl_pct': pnl_pct,  # ROE percentage
                                'leverage': leverage,
                                'is_test': False
                            }
                            log.info(f"💰 [Real Position] {side} {self.current_symbol} Amt:{amt} PnL:${unrealized_pnl:.2f} (ROE: {pnl_pct:+.2f}%)")
                    except Exception as e:
                        log.error(f"Failed to fetch real position: {e}")

            except Exception as e:
                 log.error(f"Error processing position info: {e}")

            # ✅ Save Market Data & Process Indicators
            processed_dfs = {}
            for tf in ['5m', '15m', '1h']:
                raw_klines = getattr(market_snapshot, f'raw_{tf}')
                # Save raw data
                self.saver.save_market_data(raw_klines, self.current_symbol, tf, cycle_id=cycle_id)
                
                # Process and save indicators
                df_with_indicators = self.processor.extract_feature_snapshot(getattr(self.processor.process_klines(raw_klines, self.current_symbol, tf), "copy")())
                # Wait, process_klines returns df. Calling extract_feature_snapshot on it is for features.
                # The original code:
                # df_with_indicators = self.processor.process_klines(raw_klines, self.current_symbol, tf)
                # self.saver.save_indicators(df_with_indicators, self.current_symbol, tf, snapshot_id)
                # features_df = self.processor.extract_feature_snapshot(df_with_indicators)
                
                # Let's restore original lines carefully.
                df_with_indicators = self.processor.process_klines(raw_klines, self.current_symbol, tf)
                self.saver.save_indicators(df_with_indicators, self.current_symbol, tf, snapshot_id, cycle_id=cycle_id)
                features_df = self.processor.extract_feature_snapshot(df_with_indicators)
                self.saver.save_features(features_df, self.current_symbol, tf, snapshot_id, cycle_id=cycle_id)
                
                # Store in dictionary for reuse in subsequent steps
                processed_dfs[tf] = df_with_indicators
            
            # ✅ Important optimization: Update DataFrame in snapshot
            market_snapshot.stable_5m = processed_dfs['5m']
            market_snapshot.stable_15m = processed_dfs['15m']
            market_snapshot.stable_1h = processed_dfs['1h']
            
            current_price = market_snapshot.live_5m.get('close')
            print(f"  ✅ Data ready: ${current_price:,.2f} ({market_snapshot.timestamp.strftime('%H:%M:%S')})")
            
            # LOG 1: Oracle
            global_state.add_log(f"[🕵️ ORACLE] Data ready: ${current_price:,.2f}")
            global_state.current_price[self.current_symbol] = current_price  # Store as dict keyed by symbol
            
            # Step 2: Strategist
            print("[Step 2/4] 👨‍🔬 The Strategist (QuantAnalyst) - Analyzing data...")
            quant_analysis = await self.quant_analyst.analyze_all_timeframes(market_snapshot)
            
            # 💉 INJECT MACD DATA (Fix for Missing Data)
            try:
                df_15m = processed_dfs['15m']
                # Check for macd_diff or calculate it if missing (though processor handles it)
                if 'macd_diff' in df_15m.columns:
                    macd_val = float(df_15m['macd_diff'].iloc[-1])
                    if 'trend' not in quant_analysis: quant_analysis['trend'] = {}
                    if 'details' not in quant_analysis['trend']: quant_analysis['trend']['details'] = {}
                    quant_analysis['trend']['details']['15m_macd_diff'] = macd_val
            except Exception as e:
                log.warning(f"Failed to inject MACD data: {e}")
            
            # Save Context
            self.saver.save_context(quant_analysis, self.current_symbol, 'analytics', snapshot_id, cycle_id=cycle_id)
            
            # LOG 2: QuantAnalyst (The Strategist)
            trend_score = quant_analysis.get('trend', {}).get('total_trend_score', 0)
            osc_score = quant_analysis.get('oscillator', {}).get('total_osc_score', 0)
            sent_score = quant_analysis.get('sentiment', {}).get('total_sentiment_score', 0)
            global_state.add_log(f"[👨‍🔬 STRATEGIST] Trend={trend_score:+.0f} | Osc={osc_score:+.0f} | Sent={sent_score:+.0f}")
            
            # Step 2.5: Prophet
            print("[Step 2.5/5] 🔮 The Prophet (Predict Agent) - Calculating probability...")
            df_15m_features = self.feature_engineer.build_features(processed_dfs['15m'])
            if not df_15m_features.empty:
                latest = df_15m_features.iloc[-1].to_dict()
                predict_features = {k: v for k, v in latest.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
            else:
                 predict_features = {}
            
            predict_result = await self.predict_agents[self.current_symbol].predict(predict_features)
            global_state.prophet_probability = predict_result.probability_up
            
            # LOG 3: Prophet (The Prophet)
            p_up_pct = predict_result.probability_up * 100
            direction = "↗UP" if predict_result.probability_up > 0.55 else ("↘DN" if predict_result.probability_up < 0.45 else "➖NEU")
            global_state.add_log(f"[🔮 PROPHET] P(Up)={p_up_pct:.1f}% {direction}")
            
            # Save Prediction
            self.saver.save_prediction(asdict(predict_result), self.current_symbol, snapshot_id, cycle_id=cycle_id)
            
            # === 🎯 FOUR-LAYER STRATEGY FILTERING ===
            print("[Step 2.75/5] 🎯 Four-Layer Strategy Filter - Multi-layer validation...")
            
            # Extract timeframe data
            trend_6h = quant_analysis.get('timeframe_6h', {})
            trend_2h = quant_analysis.get('timeframe_2h', {})
            sentiment = quant_analysis.get('sentiment', {})
            oi_fuel = sentiment.get('oi_fuel', {})
            
            # 🆕 Get Funding Rate for crowding detection
            funding_rate = sentiment.get('details', {}).get('funding_rate', 0)
            if funding_rate is None: funding_rate = 0
            
            # 🆕 Get ADX from RegimeDetector for trend strength validation
            # 🔧 FIX M4: Use cached regime_detector instead of creating new instance
            df_1h = processed_dfs['1h']
            regime_result = self.regime_detector.detect_regime(df_1h) if len(df_1h) >= 20 else {'adx': 20, 'regime': 'unknown'}
            adx_value = regime_result.get('adx', 20)
            
            # Initialize filter results with enhanced fields
            four_layer_result = {
                'layer1_pass': False,
                'layer2_pass': False,
                'layer3_pass': False,
                'layer4_pass': False,
                'final_action': 'wait',
                'blocking_reason': None,
                'confidence_boost': 0,
                'tp_multiplier': 1.0,
                'sl_multiplier': 1.0,
                # 🆕 Enhanced indicators
                'adx': adx_value,
                'funding_rate': funding_rate,
                'regime': regime_result.get('regime', 'unknown')
            }
            
            # Layer 1: 1h Trend + OI Fuel (Specification: EMA 20/60 on 1h data)
            df_1h = processed_dfs['1h']
            
            # 🆕 Always extract and store EMA values for display (even if blocking)
            if len(df_1h) >= 20:
                close_1h = df_1h['close'].iloc[-1]
                ema20_1h = df_1h['ema_20'].iloc[-1] if 'ema_20' in df_1h.columns else close_1h
                ema60_1h = df_1h['ema_60'].iloc[-1] if 'ema_60' in df_1h.columns else close_1h
                
                # Store for user prompt display
                four_layer_result['close_1h'] = close_1h
                four_layer_result['ema20_1h'] = ema20_1h
                four_layer_result['ema60_1h'] = ema60_1h
            else:
                close_1h = current_price
                ema20_1h = current_price
                ema60_1h = current_price
                four_layer_result['close_1h'] = close_1h
                four_layer_result['ema20_1h'] = ema20_1h
                four_layer_result['ema60_1h'] = ema60_1h
            
            # Extract OI change and store immediately
            oi_change = oi_fuel.get('oi_change_24h', 0)
            if oi_change is None: oi_change = 0
            four_layer_result['oi_change'] = oi_change
            
            # 🆕 DATA SANITY CHECKS - Flag statistically impossible values
            data_anomalies = []
            
            # OI Change sanity check: > 200% is likely a data error
            if abs(oi_change) > 200:
                data_anomalies.append(f"OI_ANOMALY: {oi_change:.1f}% (>200% likely data error)")
                log.warning(f"⚠️ DATA ANOMALY: OI Change {oi_change:.1f}% is abnormally high")
                # Clamp to reasonable value for downstream logic
                oi_change = max(min(oi_change, 100), -100)
                four_layer_result['oi_change'] = oi_change
                four_layer_result['oi_change_raw'] = oi_fuel.get('oi_change_24h', 0)  # Keep original
            
            # ADX sanity check: < 5 is likely calculation error or extreme edge case
            if adx_value < 5:
                data_anomalies.append(f"ADX_ANOMALY: {adx_value:.0f} (<5 may be unreliable)")
                log.warning(f"⚠️ DATA ANOMALY: ADX {adx_value:.0f} is abnormally low")
            
            # Funding Rate sanity check: > 1% per 8h is extreme
            if abs(funding_rate) > 1.0:
                data_anomalies.append(f"FUNDING_ANOMALY: {funding_rate:.3f}% (extreme)")
                log.warning(f"⚠️ DATA ANOMALY: Funding Rate {funding_rate:.3f}% is extreme")
            
            # 🆕 LOGIC PARADOX DETECTION - Contradictory data patterns
            regime = regime_result.get('regime', 'unknown')
            # Real paradox: trending regime with very low ADX (ADX < 15 means no trend)
            if adx_value < 15 and regime in ['trending_up', 'trending_down']:
                data_anomalies.append(f"LOGIC_PARADOX: ADX={adx_value:.0f} (no trend) + Regime={regime} (trending)")
                log.warning(f"⚠️ LOGIC PARADOX: ADX={adx_value:.0f} indicates NO trend, but Regime={regime}. Forcing to choppy.")
                # Force regime to 'choppy' when ADX is extremely low but regime says trending
                four_layer_result['regime'] = 'choppy'
                four_layer_result['regime_override'] = True
            
            # Store anomalies for LLM awareness
            four_layer_result['data_anomalies'] = data_anomalies if data_anomalies else None
            
            # Now check if we have enough data for trend analysis
            if len(df_1h) < 60:
                log.warning(f"⚠️ Insufficient 1h data: {len(df_1h)} bars (need 60+)")
                four_layer_result['blocking_reason'] = 'Insufficient 1h data'
                trend_1h = 'neutral'
            else:
                # Specification: Close > EMA20 > EMA60 (long), Close < EMA20 < EMA60 (short)
                if close_1h > ema20_1h > ema60_1h:
                    trend_1h = 'long'
                elif close_1h < ema20_1h < ema60_1h:
                    trend_1h = 'short'
                else:
                    trend_1h = 'neutral'
                
                log.info(f"📊 1h EMA: Close=${close_1h:.2f}, EMA20=${ema20_1h:.2f}, EMA60=${ema60_1h:.2f} => {trend_1h.upper()}")
            
            if trend_1h == 'neutral':
                four_layer_result['blocking_reason'] = 'No clear 1h trend (EMA 20/60)'
                log.info("❌ Layer 1 FAIL: No clear trend")
            # 🆕 ADX Weak Trend Filter - Even if EMA aligned, weak trend is not tradeable
            elif adx_value < 15: # OPTIMIZATION (Phase 2): Lowered from 20
                four_layer_result['blocking_reason'] = f"Weak Trend Strength (ADX {adx_value:.0f} < 15)"
                log.info(f"❌ Layer 1 FAIL: ADX={adx_value:.0f} < 15, trend not strong enough")
            elif trend_1h == 'long' and oi_change < -5.0:
                four_layer_result['blocking_reason'] = f"OI Divergence: Trend UP but OI {oi_change:.1f}%"
                log.warning(f"🚨 Layer 1 FAIL: OI Divergence - Price up but OI {oi_change:.1f}%")
            elif trend_1h == 'short' and oi_change > 5.0:
                four_layer_result['blocking_reason'] = f"OI Divergence: Trend DOWN but OI +{oi_change:.1f}%"
                log.warning(f"🚨 Layer 1 FAIL: OI Divergence - Price down but OI +{oi_change:.1f}%")
            elif trend_1h == 'long' and oi_fuel.get('whale_trap_risk', False):
                four_layer_result['blocking_reason'] = f"Whale trap detected (OI {oi_change:.1f}%)"
                log.warning(f"🐋 Layer 1 FAIL: Whale exit trap")
            else:
                four_layer_result['layer1_pass'] = True
                
                # 🔴 Issue #3 Fix: Weak Fuel is WARNING, not BLOCK
                if abs(oi_change) < 1.0:
                    four_layer_result['fuel_warning'] = f"Weak Fuel (OI {oi_change:.1f}%)"
                    four_layer_result['confidence_penalty'] = -10
                    log.warning(f"⚠️ Layer 1 WARNING: Weak fuel - OI {oi_change:.1f}% (proceed with caution)")
                    fuel_strength = 'Weak'
                else:
                    # Specification: Strong Fuel > 3%, Moderate 1-3%
                    fuel_strength = 'Strong' if abs(oi_change) > 3.0 else 'Moderate'
                log.info(f"✅ Layer 1 PASS: {trend_1h.upper()} trend + {fuel_strength} Fuel (OI {oi_change:+.1f}%)")
                
                # Layer 2: AI Prediction Filter
                from src.agents.ai_filter import AIPredictionFilter
                ai_filter = AIPredictionFilter()
                ai_check = ai_filter.check_divergence(trend_1h, predict_result)
                
                four_layer_result['ai_check'] = ai_check
                
                # 🆕 AI PREDICTION INVALIDATION: When ADX < 5, any directional AI prediction is noise
                if adx_value < 5:
                    ai_check['ai_invalidated'] = True
                    ai_check['original_signal'] = ai_check.get('ai_signal', 'unknown')
                    ai_check['ai_signal'] = 'INVALID (ADX<5)'
                    four_layer_result['ai_prediction_note'] = f"AI prediction invalidated: ADX={adx_value:.0f} (<5), directional signals are statistically meaningless"
                    log.warning(f"⚠️ AI prediction invalidated: ADX={adx_value:.0f} is too low for any directional signal to be reliable")
                
                if ai_check['ai_veto']:
                    four_layer_result['blocking_reason'] = ai_check['reason']
                    log.warning(f"🚫 Layer 2 VETO: {ai_check['reason']}")
                else:
                    four_layer_result['layer2_pass'] = True
                    four_layer_result['confidence_boost'] = ai_check['confidence_boost']
                    log.info(f"✅ Layer 2 PASS: AI {ai_check['ai_signal']} (boost: {ai_check['confidence_boost']:+d}%)")
                    
                    # Layer 3: 15m Setup (Specification: KDJ + Bollinger Bands)
                    df_15m = processed_dfs['15m']
                    if len(df_15m) < 20:
                        log.warning(f"⚠️ Insufficient 15m data: {len(df_15m)} bars")
                        four_layer_result['blocking_reason'] = 'Insufficient 15m data'
                        setup_ready = False
                    else:
                        close_15m = df_15m['close'].iloc[-1]
                        bb_middle = df_15m['bb_middle'].iloc[-1]
                        bb_upper = df_15m['bb_upper'].iloc[-1]
                        bb_lower = df_15m['bb_lower'].iloc[-1]
                        kdj_j = df_15m['kdj_j'].iloc[-1]
                        kdj_k = df_15m['kdj_k'].iloc[-1]
                        
                        log.info(f"📊 15m Setup: Close=${close_15m:.2f}, BB[{bb_lower:.2f}/{bb_middle:.2f}/{bb_upper:.2f}], KDJ_J={kdj_j:.1f}")
                        
                        # 🆕 Store setup details for display
                        four_layer_result['setup_note'] = f"KDJ_J={kdj_j:.0f}, Close={'>' if close_15m > bb_middle else '<'}BB_mid"
                        four_layer_result['kdj_j'] = kdj_j
                        four_layer_result['bb_position'] = 'upper' if close_15m > bb_upper else 'lower' if close_15m < bb_lower else 'middle'
                        
                        # 🔴 Bug #3 Fix: Add explicit kdj_zone field
                        if kdj_j > 80 or close_15m > bb_upper:
                            four_layer_result['kdj_zone'] = 'overbought'
                        elif kdj_j < 20 or close_15m < bb_lower:
                            four_layer_result['kdj_zone'] = 'oversold'
                        else:
                            four_layer_result['kdj_zone'] = 'neutral'
                        
                        # 🔴 Issue #2 Fix: Pullback Strategy (Buy the Dip)
                        # Specification logic for long setup
                        if trend_1h == 'long':
                            # Filter: Too high (overbought) - WAIT for pullback
                            if close_15m > bb_upper or kdj_j > 80:
                                setup_ready = False
                                four_layer_result['blocking_reason'] = f"15m overbought (J={kdj_j:.0f}) - wait for pullback"
                                log.info(f"⏳ Layer 3 WAIT: Overbought - waiting for pullback")
                            # IDEAL: Pullback position (best entry in uptrend!)
                            elif close_15m < bb_middle or kdj_j < 50: # OPTIMIZATION (Phase 2): Relaxed from 40
                                setup_ready = True
                                four_layer_result['setup_quality'] = 'IDEAL'
                                log.info(f"✅ Layer 3 READY: IDEAL PULLBACK - J={kdj_j:.0f} < 50 or Close < BB_middle")
                            # Acceptable: Neutral/mid-range (not ideal but OK)
                            else:
                                setup_ready = True  # ✅ Changed from False
                                four_layer_result['setup_quality'] = 'ACCEPTABLE'
                                log.info(f"✅ Layer 3 READY: Acceptable mid-range entry (J={kdj_j:.0f})")
                        
                        # Specification logic for short setup
                        elif trend_1h == 'short':
                            # Filter: Too low (oversold) - WAIT for rally
                            if close_15m < bb_lower or kdj_j < 20:
                                setup_ready = False
                                four_layer_result['blocking_reason'] = f"15m oversold (J={kdj_j:.0f}) - wait for rally"
                                log.info(f"⏳ Layer 3 WAIT: Oversold - waiting for rally")
                            # IDEAL: Rally position (best entry in downtrend!)
                            elif close_15m > bb_middle or kdj_j > 50: # OPTIMIZATION (Phase 2): Relaxed from 60
                                setup_ready = True
                                four_layer_result['setup_quality'] = 'IDEAL'
                                log.info(f"✅ Layer 3 READY: IDEAL RALLY - J={kdj_j:.0f} > 60 or Close > BB_middle")
                            # Acceptable: Neutral/mid-range
                            else:
                                setup_ready = True  # ✅ Changed from False
                                four_layer_result['setup_quality'] = 'ACCEPTABLE'
                                log.info(f"✅ Layer 3 READY: Acceptable mid-range entry (J={kdj_j:.0f})")
                        else:
                            setup_ready = False
                    
                    if not setup_ready:
                        four_layer_result['blocking_reason'] = f"15m setup not ready"
                        log.info(f"⏳ Layer 3 WAIT: 15m setup not ready")
                    else:
                        four_layer_result['layer3_pass'] = True
                        log.info(f"✅ Layer 3 PASS: 15m setup ready")
                        
                        # Layer 4: 5min Trigger + Sentiment Risk (Specification Module 4)
                        from src.agents.trigger_detector import TriggerDetector
                        trigger_detector = TriggerDetector()
                        
                        df_5m = processed_dfs['5m']
                        trigger_result = trigger_detector.detect_trigger(df_5m, direction=trend_1h)
                        
                        # 🆕 Always store trigger data for LLM display
                        four_layer_result['trigger_pattern'] = trigger_result.get('pattern_type') or 'None'
                        rvol = trigger_result.get('rvol', 1.0)
                        four_layer_result['trigger_rvol'] = rvol
                        
                        # ⚠️ LOW VOLUME WARNING
                        if rvol < 0.5:
                            log.warning(f"⚠️ Low Volume Warning (RVOL {rvol:.1f}x < 0.5) - Trend validation may be unreliable")
                            if not four_layer_result.get('data_anomalies'): four_layer_result['data_anomalies'] = []
                            four_layer_result['data_anomalies'].append(f"Low Volume (RVOL {rvol:.1f}x)")
                        
                        if not trigger_result['triggered']:
                            four_layer_result['blocking_reason'] = f"5min trigger not confirmed (RVOL={trigger_result.get('rvol', 1.0):.1f}x)"
                            log.info(f"⏳ Layer 4 WAIT: No engulfing or breakout pattern (RVOL={trigger_result.get('rvol', 1.0):.1f}x)")
                        else:
                            log.info(f"🎯 Layer 4 TRIGGER: {trigger_result['pattern_type']} detected")
                            
                            # Sentiment Risk Adjustment (Specification: Score range -100 to +100)
                            # Normal zone: -60 to +60
                            # Extreme Greed: > +80 => Halve TP (prevent sudden crash)
                            # Extreme Fear: < -80 => Can increase position/TP
                            sentiment_score = sentiment.get('total_sentiment_score', 0)
                            
                            if sentiment_score > 80:  # Extreme Greed
                                four_layer_result['tp_multiplier'] = 0.5  # Halve take profit
                                four_layer_result['sl_multiplier'] = 1.0  # Stop loss unchanged
                                log.warning(f"🔴 Extreme Greed ({sentiment_score:.0f}): TP target halved")
                            elif sentiment_score < -80:  # Extreme Fear
                                four_layer_result['tp_multiplier'] = 1.5  # Can increase TP
                                four_layer_result['sl_multiplier'] = 0.8  # Reduce SL
                                log.info(f"🟢 Extreme Fear ({sentiment_score:.0f}): Be greedy when others are fearful")
                            else:
                                four_layer_result['tp_multiplier'] = 1.0
                                four_layer_result['sl_multiplier'] = 1.0
                            
                            # 🆕 Funding Rate Crowding Adjustment
                            if trend_1h == 'long' and funding_rate > 0.05:
                                four_layer_result['tp_multiplier'] *= 0.7
                                log.warning(f"💰 High Funding Rate ({funding_rate:.3f}%): Longs crowded, TP reduced")
                            elif trend_1h == 'short' and funding_rate < -0.05:
                                four_layer_result['tp_multiplier'] *= 0.7
                                log.warning(f"💰 Negative Funding Rate ({funding_rate:.3f}%): Shorts crowded, TP reduced")
                            
                            four_layer_result['layer4_pass'] = True
                            four_layer_result['final_action'] = trend_1h
                            four_layer_result['trigger_pattern'] = trigger_result['pattern_type']
                            log.info(f"✅ Layer 4 PASS: Sentiment {sentiment_score:.0f}, Trigger={trigger_result['pattern_type']}")
                            log.info(f"🎯 ALL LAYERS PASSED: {trend_1h.upper()} with {70 + four_layer_result['confidence_boost']}% confidence")
            
            # Store for LLM context
            global_state.four_layer_result = four_layer_result
            
            # 🆕 MULTI-AGENT SEMANTIC ANALYSIS
            print("[Step 2.5/5] 🤖 Multi-Agent Semantic Analysis...")
            try:
                from src.agents.trend_agent import TrendAgent
                from src.agents.setup_agent import SetupAgent
                from src.agents.trigger_agent import TriggerAgent
                
                # Initialize agents (cached after first use)
                if not hasattr(self, '_trend_agent'):
                    self._trend_agent = TrendAgent()
                    self._setup_agent = SetupAgent()
                    self._trigger_agent = TriggerAgent()
                
                # Prepare data for each agent
                trend_data = {
                    'symbol': self.current_symbol,
                    'close_1h': four_layer_result.get('close_1h', current_price),
                    'ema20_1h': four_layer_result.get('ema20_1h', current_price),
                    'ema60_1h': four_layer_result.get('ema60_1h', current_price),
                    'oi_change': four_layer_result.get('oi_change', 0),
                    'adx': four_layer_result.get('adx', 20),
                    'regime': four_layer_result.get('regime', 'unknown')
                }
                
                setup_data = {
                    'symbol': self.current_symbol,
                    'close_15m': processed_dfs['15m']['close'].iloc[-1] if len(processed_dfs['15m']) > 0 else current_price,
                    'kdj_j': four_layer_result.get('kdj_j', 50),
                    'kdj_k': processed_dfs['15m']['kdj_k'].iloc[-1] if 'kdj_k' in processed_dfs['15m'].columns else 50,
                    'bb_upper': processed_dfs['15m']['bb_upper'].iloc[-1] if 'bb_upper' in processed_dfs['15m'].columns else current_price * 1.02,
                    'bb_middle': processed_dfs['15m']['bb_middle'].iloc[-1] if 'bb_middle' in processed_dfs['15m'].columns else current_price,
                    'bb_lower': processed_dfs['15m']['bb_lower'].iloc[-1] if 'bb_lower' in processed_dfs['15m'].columns else current_price * 0.98,
                    'trend_direction': trend_1h,  # Use actual 1h trend instead of 'final_action'
                    'macd_diff': processed_dfs['15m']['macd_diff'].iloc[-1] if 'macd_diff' in processed_dfs['15m'].columns else 0  # 🆕 MACD for 15m analysis
                }
                
                trigger_data = {
                    'symbol': self.current_symbol,
                    'pattern': four_layer_result.get('trigger_pattern'),
                    'rvol': four_layer_result.get('trigger_rvol', 1.0),
                    'trend_direction': four_layer_result.get('final_action', 'neutral')
                }
                
                # Run agents in parallel using asyncio
                loop = asyncio.get_event_loop()
                trend_analysis, setup_analysis, trigger_analysis = await asyncio.gather(
                    loop.run_in_executor(None, self._trend_agent.analyze, trend_data),
                    loop.run_in_executor(None, self._setup_agent.analyze, setup_data),
                    loop.run_in_executor(None, self._trigger_agent.analyze, trigger_data)
                )
                
                # Store semantic analyses in global_state
                global_state.semantic_analyses = {
                    'trend': trend_analysis,
                    'setup': setup_analysis,
                    'trigger': trigger_analysis
                }
                
                # Log summary via global_state for dashboard
                global_state.add_log(f"[⚖️ CRITIC] 4-Layer Analysis: Trend={len(trend_analysis)>100 and '✓' or '○'} | Setup={len(setup_analysis)>100 and '✓' or '○'} | Trigger={len(trigger_analysis)>100 and '✓' or '○'}")
                
            except Exception as e:
                log.error(f"❌ Multi-Agent analysis failed: {e}")
                global_state.semantic_analyses = {
                    'trend': f"Trend analysis unavailable: {e}",
                    'setup': f"Setup analysis unavailable: {e}",
                    'trigger': f"Trigger analysis unavailable: {e}"
                }
            
            # Step 3: DeepSeek
            market_data = {
                'df_5m': processed_dfs['5m'],
                'df_15m': processed_dfs['15m'],
                'df_1h': processed_dfs['1h'],
                'current_price': current_price
            }
            regime_info = quant_analysis.get('regime', {})
            
            print("[Step 3/5] 🧠 DeepSeek LLM - Making decision...")
            
            # Build Context with POSITION INFO
            market_context_text = self._build_market_context(
                quant_analysis=quant_analysis,
                predict_result=predict_result,
                market_data=market_data,
                regime_info=regime_info,
                position_info=current_position_info  # ✅ Pass Position Info
            )
            
            market_context_data = {
                'symbol': self.current_symbol,
                'timestamp': datetime.now().isoformat(),
                'current_price': current_price
            }
            
            # 🧠 Check if reflection is needed (every 10 trades)
            reflection_text = None
            total_trades = len(global_state.trade_history)
            if self.reflection_agent.should_reflect(total_trades):
                log.info(f"🧠 Triggering reflection after {total_trades} trades...")
                trades_to_analyze = global_state.trade_history[-10:]
                reflection_result = await self.reflection_agent.generate_reflection(trades_to_analyze)
                if reflection_result:
                    reflection_text = reflection_result.to_prompt_text()
                    global_state.last_reflection = reflection_result.raw_response
                    global_state.last_reflection_text = reflection_text
                    global_state.reflection_count = self.reflection_agent.reflection_count
                    global_state.add_log(f"🧠 Reflection #{self.reflection_agent.reflection_count} generated")
            else:
                # Use cached reflection if available
                reflection_text = global_state.last_reflection_text
            
            # Call DeepSeek with optional reflection
            llm_decision = self.strategy_engine.make_decision(
                market_context_text=market_context_text,
                market_context_data=market_context_data,
                reflection=reflection_text
            )
            
            # ... Rest of logic stays similar ...
            
            # Convert to VoteResult compatible format
            # (Need to check if i need to include rest of the function)

            
            # Convert to VoteResult compatible format
            from src.agents.decision_core_agent import VoteResult
            
            # Extract scores for dashboard
            q_trend = quant_analysis.get('trend', {})
            q_osc = quant_analysis.get('oscillator', {})
            q_sent = quant_analysis.get('sentiment', {})
            q_comp = quant_analysis.get('comprehensive', {})
            
            # Construct vote_details similar to DecisionCore
            vote_details = {
                'deepseek': llm_decision.get('confidence', 0),
                'strategist_total': q_comp.get('score', 0),
                # Trend
                'trend_1h': q_trend.get('trend_1h_score', 0),
                'trend_15m': q_trend.get('trend_15m_score', 0),
                'trend_5m': q_trend.get('trend_5m_score', 0),
                # Oscillator
                'oscillator_1h': q_osc.get('osc_1h_score', 0),
                'oscillator_15m': q_osc.get('osc_15m_score', 0),
                'oscillator_5m': q_osc.get('osc_5m_score', 0),
                # Sentiment
                'sentiment': q_sent.get('total_sentiment_score', 0),
                # Prophet
                'prophet': predict_result.probability_up,
                # 🐂🐻 Bullish/Bearish Perspective Analysis
                'bull_confidence': llm_decision.get('bull_perspective', {}).get('bull_confidence', 50),
                'bear_confidence': llm_decision.get('bear_perspective', {}).get('bear_confidence', 50),
                'bull_stance': llm_decision.get('bull_perspective', {}).get('stance', 'UNKNOWN'),
                'bear_stance': llm_decision.get('bear_perspective', {}).get('stance', 'UNKNOWN'),
                'bull_reasons': llm_decision.get('bull_perspective', {}).get('bullish_reasons', ''),
                'bear_reasons': llm_decision.get('bear_perspective', {}).get('bearish_reasons', '')
            }
            
            # Determine Regime from Trend Score using Semantic Converter
            trend_score_total = quant_analysis.get('trend', {}).get('total_trend_score', 0)
            regime_desc = SemanticConverter.get_trend_semantic(trend_score_total)
            
            # Determine Position details from LLM Decision
            pos_pct = llm_decision.get('position_size_pct', 0)
            if not pos_pct and llm_decision.get('position_size_usd') and self.max_position_size:
                 # Fallback: estimate pct if usd is provided
                 pos_pct = (llm_decision.get('position_size_usd') / self.max_position_size) * 100
                 # Clamp to reasonable range (position size should not exceed 100%)
                 pos_pct = min(pos_pct, 100)
            
            # Get actual price position info (from regime_result - Python calculated)
            # Note: regime_info (from quant_analysis) is empty because we separated logic.
            # Use regime_result calculated in Step 2.75 instead for accurate Position Data.
            price_position_info = regime_result.get('position', {}) if regime_result else {}
            
            vote_result = VoteResult(
                action=llm_decision.get('action', 'wait'),
                confidence=llm_decision.get('confidence', 0) / 100.0,  # Convert to 0-1
                weighted_score=llm_decision.get('confidence', 0) - 50,  # -50 to +50
                vote_details=vote_details,
                multi_period_aligned=True,
                reason=llm_decision.get('reasoning', 'DeepSeek LLM decision'),
                regime={
                    'regime': regime_desc,
                    'confidence': llm_decision.get('confidence', 0)
                },
                position=price_position_info  # Use actual price position info
            )
            
            # Save complete LLM interaction log (Input, Process, Output)
            # Only save detailed logs in local mode to conserve disk space on Railway
            if os.environ.get('ENABLE_DETAILED_LLM_LOGS', 'false').lower() == 'true':
                full_log_content = f"""
================================================================================
🕐 Timestamp: {datetime.now().isoformat()}
💱 Symbol: {self.current_symbol}
🔄 Cycle: #{cycle_id}
================================================================================

--------------------------------------------------------------------------------
📤 INPUT (PROMPT)
--------------------------------------------------------------------------------
[SYSTEM PROMPT]
{llm_decision.get('system_prompt', '(Missing System Prompt)')}

[USER PROMPT]
{llm_decision.get('user_prompt', '(Missing User Prompt)')}

--------------------------------------------------------------------------------
🧠 PROCESSING (REASONING)
--------------------------------------------------------------------------------
{llm_decision.get('reasoning_detail', '(No reasoning detail)')}

--------------------------------------------------------------------------------
📥 OUTPUT (DECISION)
--------------------------------------------------------------------------------
{llm_decision.get('raw_response', '(No raw response)')}
"""
                self.saver.save_llm_log(
                    content=full_log_content,
                    symbol=self.current_symbol,
                    snapshot_id=snapshot_id,
                    cycle_id=cycle_id
                )
            
            # LOG: Bullish/Bearish Perspective (show first for adversarial context)
            bull_conf = llm_decision.get('bull_perspective', {}).get('bull_confidence', 50)
            bear_conf = llm_decision.get('bear_perspective', {}).get('bear_confidence', 50)
            bull_stance = llm_decision.get('bull_perspective', {}).get('stance', 'UNKNOWN')
            bear_stance = llm_decision.get('bear_perspective', {}).get('stance', 'UNKNOWN')
            bull_reasons = llm_decision.get('bull_perspective', {}).get('bullish_reasons', '')[:120]
            bear_reasons = llm_decision.get('bear_perspective', {}).get('bearish_reasons', '')[:120]
            global_state.add_log(f"[🐂 Long Case] [{bull_stance}] Conf={bull_conf}%")
            global_state.add_log(f"[🐻 Short Case] [{bear_stance}] Conf={bear_conf}%")
            
            # LOG: LLM Decision Engine (generic, not tied to DeepSeek)
            global_state.add_log(f"[⚖️ Final Decision] Action={vote_result.action.upper()} | Conf={llm_decision.get('confidence', 0)}%")
            
            # ✅ Decision Recording moved after Risk Audit for complete context
            # Saved to file still happens here for "raw" decision
            self.saver.save_decision(asdict(vote_result), self.current_symbol, snapshot_id, cycle_id=cycle_id)

            # If waiting, also need to update state
            if vote_result.action in ('hold', 'wait'):
                print(f"\n✅ Decision: Wait ({vote_result.action})")
                
                # GlobalState Logging of Logic
                regime_txt = vote_result.regime.get('regime', 'Unknown') if vote_result.regime else 'Unknown'
                pos_txt = f"{min(max(vote_result.position.get('position_pct', 0), 0), 100):.0f}%" if vote_result.position else 'N/A'
                
                # LOG 3: Critic (Wait Case)
                global_state.add_log(f"⚖️ DecisionCoreAgent (The Critic): Context(Regime={regime_txt}, Pos={pos_txt}) => Vote: WAIT ({vote_result.reason})")
                
                # Check if there's an active position
                # For now, we assume no position in test mode (can be enhanced with real position check)
                actual_action = 'wait'  # No position → wait
                # If we had a position, it would be 'hold'
                
                # Update State with WAIT/HOLD decision
                decision_dict = asdict(vote_result)
                decision_dict['action'] = actual_action  # ✅ Use 'wait' instead of 'hold'
                decision_dict['symbol'] = self.current_symbol
                decision_dict['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                decision_dict['cycle_number'] = global_state.cycle_counter
                decision_dict['cycle_id'] = global_state.current_cycle_id
                # Add implicit safe risk for Wait/Hold
                decision_dict['risk_level'] = 'safe'
                decision_dict['guardian_passed'] = True
                decision_dict['prophet_probability'] = predict_result.probability_up  # 🔮 Prophet
                
                # ✅ Add Semantic Analysis for Dashboard
                decision_dict['vote_analysis'] = SemanticConverter.convert_analysis_map(decision_dict.get('vote_details', {}))
                
                # 🆕 Add Four-Layer Status for Dashboard
                decision_dict['four_layer_status'] = global_state.four_layer_result
                
                # 🆕 Add OI Fuel and KDJ Zone to vote_details for Dashboard
                if 'vote_details' not in decision_dict:
                    decision_dict['vote_details'] = {}
                decision_dict['vote_details']['oi_fuel'] = quant_analysis.get('sentiment', {}).get('oi_fuel', {})
                
                # 🔴 Bug #6 Fix: Use explicit kdj_zone if available, else map bb_position
                kdj_zone = global_state.four_layer_result.get('kdj_zone')
                if not kdj_zone:
                    bb_position = global_state.four_layer_result.get('bb_position', 'unknown')
                    bb_to_zone_map = {
                        'upper': 'overbought',
                        'lower': 'oversold',
                        'middle': 'neutral',
                        'unknown': 'unknown'
                    }
                    kdj_zone = bb_to_zone_map.get(bb_position, 'unknown')
                decision_dict['vote_details']['kdj_zone'] = kdj_zone
                
                # 🔧 Fix: Inject ADX into regime object for Dashboard display
                if 'regime' in decision_dict and decision_dict['regime']:
                    decision_dict['regime']['adx'] = global_state.four_layer_result.get('adx', 20)
                
                # Update Market Context
                if vote_result.regime:
                    global_state.market_regime = vote_result.regime.get('regime', 'Unknown')
                if vote_result.position:
                    # Safety clamp: ensure position_pct is 0-100
                    pos_pct = min(max(vote_result.position.get('position_pct', 0), 0), 100)
                    global_state.price_position = f"{pos_pct:.1f}% ({vote_result.position.get('location', 'Unknown')})"
                    
                global_state.update_decision(decision_dict)

                return {
                    'status': actual_action,
                    'action': actual_action,
                    'details': {
                        'reason': vote_result.reason,
                        'confidence': vote_result.confidence
                    }
                }
            
            # Step 4: Audit - The Guardian (Risk Control)
            print(f"[Step 4/5] 👮 The Guardian (Risk Audit) - Final review...")
            
            # Critic Log for Action decision
            # Step 4: Audit - The Guardian (Risk Control)
            print(f"[Step 4/5] 👮 The Guardian (Risk Audit) - Final review...")
            
            # LOG 3: Critic (Action Case) - if not already logged (Wait case returns early)
            regime_txt = vote_result.regime.get('regime', 'Unknown') if vote_result.regime else 'Unknown'
            # Note: Wait case returns, so if we are here, it's an action.
            global_state.add_log(f"⚖️ DecisionCoreAgent (The Critic): Context(Regime={regime_txt}) => Vote: {vote_result.action.upper()} (Conf: {vote_result.confidence*100:.0f}%)")
            
            global_state.guardian_status = "Auditing..."
            global_state.guardian_status = "Auditing..."
            
            order_params = self._build_order_params(
                action=vote_result.action,
                current_price=current_price,
                confidence=vote_result.confidence
            )
            
            print(f"  ✅ Signal direction: {vote_result.action}")
            print(f"  ✅ Overall confidence: {vote_result.confidence:.1f}%")
            if vote_result.regime:
                print(f"  📊 Market regime: {vote_result.regime['regime']}")
            if vote_result.position:
                print(f"  📍 Price position: {min(max(vote_result.position['position_pct'], 0), 100):.1f}% ({vote_result.position['location']})")
            
            # Inject adversarial context into order params for risk audit use
            order_params['regime'] = vote_result.regime
            order_params['position'] = vote_result.position
            order_params['confidence'] = vote_result.confidence
            
            # Step 5 (Embedded in Step 4 for clean output)
            
            # Get account info
            # Using _get_full_account_info helper (we will create it or inline logic)
            # Fetch directly from client to get full details
            try:
                if self.test_mode:
                    # Test Mode: Use virtual balance
                    wallet_bal = global_state.virtual_balance
                    avail_bal = global_state.virtual_balance
                    unrealized_pnl = 0.0 # Updated at end of cycle
                    
                    # Log for debugging
                    # log.info(f"Test Mode: Using virtual balance ${avail_bal}")
                    
                    account_balance = avail_bal
                else:
                    acc_info = self.client.get_futures_account()
                    # acc_info keys: 'total_wallet_balance', 'total_unrealized_profit', 'available_balance', etc. (snake_case)
                    wallet_bal = float(acc_info.get('total_wallet_balance', 0))
                    unrealized_pnl = float(acc_info.get('total_unrealized_profit', 0))
                    avail_bal = float(acc_info.get('available_balance', 0))
                    total_equity = wallet_bal + unrealized_pnl
                    
                    # Update State
                    global_state.update_account(
                        equity=total_equity,
                        available=avail_bal,
                        wallet=wallet_bal,
                        pnl=unrealized_pnl
                    )
                    global_state.record_account_success()  # Track success
                    
                    account_balance = avail_bal # For backward compatibility with audit
            except Exception as e:
                log.error(f"Failed to fetch account info: {e}")
                global_state.record_account_failure()  # Track failure
                global_state.add_log(f"❌ Account info fetch failed: {str(e)}")  # Dashboard log
                account_balance = 0.0

            current_position = self._get_current_position()
            
            # Extract ATR percentage for dynamic stop loss calculation
            atr_pct = regime_result.get('atr_pct', None) if regime_result else None
            
            # Execute audit
            audit_result = await self.risk_audit.audit_decision(
                decision=order_params,
                current_position=current_position,
                account_balance=account_balance,
                current_price=current_price,
                atr_pct=atr_pct  # Pass ATR for dynamic stop-loss calculation
            )
            
            # Update Dashboard Guardian Status
            global_state.guardian_status = "PASSED" if audit_result.passed else "BLOCKED"
            
            # LOG 4: Guardian (Single Line)
            if not audit_result.passed:
                 global_state.add_log(f"[🛡️ GUARDIAN] ❌ BLOCKED ({audit_result.blocked_reason})")
            else:
                 global_state.add_log(f"[🛡️ GUARDIAN] ✅ PASSED (Risk: {audit_result.risk_level.value})")
            
            # ✅ Update Global State with FULL Decision info (Vote + Audit)
            decision_dict = asdict(vote_result)
            decision_dict['symbol'] = self.current_symbol
            decision_dict['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            decision_dict['cycle_number'] = global_state.cycle_counter
            decision_dict['cycle_id'] = global_state.current_cycle_id
            
            # Inject Risk Data
            decision_dict['risk_level'] = audit_result.risk_level.value
            decision_dict['guardian_passed'] = audit_result.passed
            decision_dict['guardian_reason'] = audit_result.blocked_reason
            decision_dict['prophet_probability'] = predict_result.probability_up  # 🔮 Prophet
            
            # ✅ Add Semantic Analysis for Dashboard
            decision_dict['vote_analysis'] = SemanticConverter.convert_analysis_map(decision_dict.get('vote_details', {}))
            
            # 🆕 Add Four-Layer Status for Dashboard
            decision_dict['four_layer_status'] = global_state.four_layer_result
            
            # 🆕 Add OI Fuel and KDJ Zone to vote_details for Dashboard
            if 'vote_details' not in decision_dict:
                decision_dict['vote_details'] = {}
            decision_dict['vote_details']['oi_fuel'] = quant_analysis.get('sentiment', {}).get('oi_fuel', {})
            
            # 🔴 Bug #6 Fix: Use explicit kdj_zone if available, else map bb_position
            kdj_zone = global_state.four_layer_result.get('kdj_zone')
            if not kdj_zone:
                bb_position = global_state.four_layer_result.get('bb_position', 'unknown')
                bb_to_zone_map = {
                    'upper': 'overbought',
                    'lower': 'oversold',
                    'middle': 'neutral',
                    'unknown': 'unknown'
                }
                kdj_zone = bb_to_zone_map.get(bb_position, 'unknown')
            decision_dict['vote_details']['kdj_zone'] = kdj_zone
            
            # 🔧 Fix: Inject ADX into regime object for Dashboard display
            if 'regime' in decision_dict and decision_dict['regime']:
                decision_dict['regime']['adx'] = global_state.four_layer_result.get('adx', 20)
            
            # Update Market Context
            if vote_result.regime:
                global_state.market_regime = vote_result.regime.get('regime', 'Unknown')
            if vote_result.position:
                # Safety clamp: ensure position_pct is 0-100
                pos_pct = min(max(vote_result.position.get('position_pct', 0), 0), 100)
                global_state.price_position = f"{pos_pct:.1f}% ({vote_result.position.get('location', 'Unknown')})"
                
            global_state.update_decision(decision_dict)
            
            # ✅ Save Risk Audit Report
            from dataclasses import asdict as dc_asdict
            self.saver.save_risk_audit(
                audit_result={
                    'passed': audit_result.passed,
                    'risk_level': audit_result.risk_level.value,
                    'blocked_reason': audit_result.blocked_reason,
                    'corrections': audit_result.corrections,
                    'warnings': audit_result.warnings,
                    'order_params': order_params,
                    'cycle_id': cycle_id
                },
                symbol=self.current_symbol,
                snapshot_id=snapshot_id,
                cycle_id=cycle_id
            )
            
            print(f"  ✅ Audit Result: {'✅ Passed' if audit_result.passed else '❌ Blocked'}")
            print(f"  ✅ Risk Level: {audit_result.risk_level.value}")
            
            # If there are corrections
            if audit_result.corrections:
                print(f"  ⚠️  Auto Corrections:")
                for key, value in audit_result.corrections.items():
                    print(f"     {key}: {order_params[key]} -> {value}")
                    order_params[key] = value  # Apply corrections
            
            # If there are warnings
            if audit_result.warnings:
                print(f"  ⚠️  Warning Messages:")
                for warning in audit_result.warnings:
                    print(f"     {warning}")
            
            # If blocked
            if not audit_result.passed:
                print(f"\n❌ Decision blocked by risk control: {audit_result.blocked_reason}")
                return {
                    'status': 'blocked',
                    'action': vote_result.action,
                    'details': {
                        'reason': audit_result.blocked_reason,
                        'risk_level': audit_result.risk_level.value
                    },
                    'current_price': current_price
                }

            # Decoupling: If analyze_only is True, skip execution for OPEN actions
            if analyze_only and vote_result.action in ('open_long', 'open_short'):
                log.info(f"🔍 [Analyze Only] Strategy suggests {vote_result.action.upper()} for {self.current_symbol}, skipping execution for selector")
                return {
                    'status': 'suggested',
                    'action': vote_result.action,
                    'confidence': vote_result.confidence,
                    'order_params': order_params,
                    'vote_result': vote_result,
                    'current_price': current_price
                }
            # Step 5: Execution Engine
            if self.test_mode:
                print("\n[Step 5/5] 🧪 TestMode - Simulated Execution...")
                print(f"  Simulated Order: {order_params['action']} {order_params['quantity']} @ {current_price}")
                
                # LOG 5: Executor (Test)
                global_state.add_log(f"[🚀 EXECUTOR] Test: {order_params['action'].upper()} {order_params['quantity']} @ {current_price:.2f}")

                 # ✅ Save Execution (Simulated)
                self.saver.save_execution({
                    'symbol': self.current_symbol,
                    'action': 'SIMULATED_EXECUTION',
                    'params': order_params,
                    'status': 'success',
                    'timestamp': datetime.now().isoformat(),
                    'cycle_id': cycle_id
                }, self.current_symbol, cycle_id=cycle_id)
                
                # 💰 Test Mode Logic: Calculate PnL and update state (Virtual Account)
                realized_pnl = 0.0
                exit_test_price = 0.0
                
                if self.test_mode:
                    action_lower = vote_result.action.lower()
                    
                    # Close Logic
                    if 'close' in action_lower:
                        if self.current_symbol in global_state.virtual_positions:
                            pos = global_state.virtual_positions[self.current_symbol]
                            entry_price = pos['entry_price']
                            qty = pos['quantity']
                            side = pos['side']
                            
                            # Calc Realized PnL
                            if side.upper() == 'LONG':
                                realized_pnl = (current_price - entry_price) * qty
                            else:
                                realized_pnl = (entry_price - current_price) * qty
                            
                            exit_test_price = current_price
                            # Update Virtual Balance
                            global_state.virtual_balance += realized_pnl
                            
                            # Remove position
                            del global_state.virtual_positions[self.current_symbol]
                            self._save_virtual_state()
                            
                            log.info(f"💰 [TEST] Closed {side} {self.current_symbol}: PnL=${realized_pnl:.2f}, Bal=${global_state.virtual_balance:.2f}")
                            
                            # Record trade to history -> MOVED TO UNIFIED BLOCK BELOW
                            # global_state.record_trade({ ... })
                        else:
                            log.warning(f"⚠️ [TEST] Close ignored - No position for {self.current_symbol}")
                    
                    # Open Logic
                    elif 'long' in action_lower or 'short' in action_lower:
                        side = 'LONG' if 'long' in action_lower else 'SHORT'
                        # Calculate position value
                        position_value = order_params['quantity'] * current_price
                        global_state.virtual_positions[self.current_symbol] = {
                            'entry_price': current_price,
                            'quantity': order_params['quantity'],
                            'side': side,
                            'entry_time': datetime.now().isoformat(),
                            'stop_loss': order_params.get('stop_loss_price', 0),
                            'take_profit': order_params.get('take_profit_price', 0),
                            'leverage': order_params.get('leverage', 1),
                            'position_value': position_value  # Used to calculate available balance
                        }
                        self._save_virtual_state()
                        log.info(f"💰 [TEST] Opened {side} {self.current_symbol} @ ${current_price:,.2f}")
                        
                        # Record trade to history -> MOVED TO UNIFIED BLOCK BELOW
                        # global_state.record_trade({ ... })

                # ✅ Save Trade in persistent history
                # Logic Update: If CLOSING, try to update previous OPEN record. If failing, save new.
                
                is_close_action = 'close' in vote_result.action.lower()
                update_success = False
                
                if is_close_action:
                    update_success = self.saver.update_trade_exit(
                        symbol=self.current_symbol,
                        exit_price=exit_test_price,
                        pnl=realized_pnl,
                        exit_time=datetime.now().strftime("%H:%M:%S"),
                        close_cycle=global_state.cycle_counter
                    )
                    
                    # ✅ Sync global_state.trade_history if CSV update succeeded
                    if update_success:
                        for trade in global_state.trade_history:
                            if trade.get('symbol') == self.current_symbol and trade.get('exit_price', 0) == 0:
                                trade['exit_price'] = exit_test_price
                                trade['pnl'] = realized_pnl
                                trade['close_cycle'] = global_state.cycle_counter
                                trade['status'] = 'CLOSED'
                                log.info(f"✅ Synced global_state.trade_history: {self.current_symbol} PnL ${realized_pnl:.2f}")
                                break
                
                # Only save NEW record if it's OPEN action OR if Update Failed (Fallback)
                if not update_success:
                    is_open_action = 'open' in order_params['action'].lower()
                    
                    # For CLOSE actions, find the original open_cycle from trade_history
                    original_open_cycle = 0
                    if not is_open_action:
                        for trade in global_state.trade_history:
                            if trade.get('symbol') == self.current_symbol and trade.get('exit_price', 0) == 0:
                                original_open_cycle = trade.get('open_cycle', 0)
                                break
                    
                    trade_record = {
                        'open_cycle': global_state.cycle_counter if is_open_action else original_open_cycle,
                        'close_cycle': 0 if is_open_action else global_state.cycle_counter,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'action': order_params['action'].upper(),
                        'symbol': self.current_symbol,
                        'entry_price': current_price, # ✅ Fixed field name (was price)
                        'quantity': order_params['quantity'],
                        'cost': current_price * order_params['quantity'],
                        'exit_price': exit_test_price,
                        'pnl': realized_pnl,
                        'confidence': order_params['confidence'],
                        'status': 'SIMULATED',
                        'cycle': cycle_id
                    }
                    if is_close_action:
                         trade_record['status'] = 'CLOSED (Fallback)'
                         
                    self.saver.save_trade(trade_record)
                    # Update Global State History
                    global_state.trade_history.insert(0, trade_record)
                    if len(global_state.trade_history) > 50:
                        global_state.trade_history.pop()

                # 🎯 Increment cycle position counter
                if 'open' in vote_result.action.lower():
                     global_state.cycle_positions_opened += 1
                     log.info(f"Positions opened this cycle: {global_state.cycle_positions_opened}/1")
                
                return {
                    'status': 'success',
                    'action': vote_result.action,
                    'details': order_params,
                    'current_price': current_price
                }
            else:
                # Live Execution
                print("\n[Step 5/5] 🚀 LiveTrade - Live Execution...")
                
                try:
                    # _execute_order returns bool
                    is_success = self._execute_order(order_params)
                    
                    status_icon = "✅" if is_success else "❌"
                    status_txt = "SENT" if is_success else "FAILED"
                    
                    # LOG 5: Executor (Live)
                    global_state.add_log(f"[🚀 EXECUTOR] Live: {order_params['action'].upper()} {order_params['quantity']} => {status_icon} {status_txt}")
                        
                    executed = {'status': 'filled' if is_success else 'failed', 'avgPrice': current_price, 'executedQty': order_params['quantity']}
                        
                except Exception as e:
                    log.error(f"Live order execution failed: {e}", exc_info=True)
                    global_state.add_log(f"[Execution] ❌ Live Order Failed: {e}")
                    return {
                        'status': 'failed',
                        'action': vote_result.action,
                        'details': {'error': str(e)}
                    }
            
            # ✅ Save Execution
            self.saver.save_execution({
                'symbol': self.current_symbol,
                'action': 'REAL_EXECUTION',
                'params': order_params,
                'status': 'success' if executed else 'failed',
                'timestamp': datetime.now().isoformat(),
                'cycle_id': cycle_id
            }, self.current_symbol, cycle_id=cycle_id)
            
            if executed:
                print("  ✅ Order executed successfully!")
                global_state.add_log(f"✅ Order: {order_params['action'].upper()} {order_params['quantity']} @ ${order_params['price']}")
                
                # Record trade log
                trade_logger.log_open_position(
                    symbol=self.current_symbol,
                    side=order_params['action'].upper(),
                    decision=order_params,
                    execution_result={
                        'success': True,
                        'entry_price': order_params['entry_price'],
                        'quantity': order_params['quantity'],
                        'stop_loss': order_params['stop_loss'],
                        'take_profit': order_params['take_profit'],
                        'order_id': 'real_order' # Placeholder if actual ID not captured
                    },
                    market_state=market_snapshot.live_5m,
                    account_info={'available_balance': account_balance}
                )
                
                # Calculate PnL (if closing position)
                pnl = 0.0
                exit_price = 0.0
                entry_price = order_params['entry_price']
                if order_params['action'] == 'close_position' and current_position:
                    exit_price = current_price
                    entry_price = current_position.entry_price
                    # PnL = (Exit - Entry) * Qty (Multiplied by 1 if long, -1 if short)
                    direction = 1 if current_position.side == 'long' else -1
                    pnl = (exit_price - entry_price) * current_position.quantity * direction
                
                # ✅ Save Trade in persistent history
                # Logic Update: If CLOSING, try to update previous OPEN record. If failing, save new.
                
                is_close_action = 'close' in order_params['action'].lower()
                update_success = False
                
                if is_close_action:
                    update_success = self.saver.update_trade_exit(
                        symbol=self.current_symbol,
                        exit_price=exit_price,
                        pnl=pnl,
                        exit_time=datetime.now().strftime("%H:%M:%S"),
                        close_cycle=global_state.cycle_counter
                    )
                    
                    # ✅ Sync global_state.trade_history if CSV update succeeded
                    if update_success:
                        for trade in global_state.trade_history:
                            if trade.get('symbol') == self.current_symbol and trade.get('exit_price', 0) == 0:
                                trade['exit_price'] = exit_price
                                trade['pnl'] = pnl
                                trade['close_cycle'] = global_state.cycle_counter
                                trade['status'] = 'CLOSED'
                                log.info(f"✅ Synced global_state.trade_history: {self.current_symbol} PnL ${pnl:.2f}")
                                break
                
                if not update_success:
                    is_open_action = 'open' in order_params['action'].lower()
                    
                    # For CLOSE actions, find the original open_cycle from trade_history
                    original_open_cycle = 0
                    if not is_open_action:
                        for trade in global_state.trade_history:
                            if trade.get('symbol') == self.current_symbol and trade.get('exit_price', 0) == 0:
                                original_open_cycle = trade.get('open_cycle', 0)
                                break
                    
                    trade_record = {
                        'open_cycle': global_state.cycle_counter if is_open_action else original_open_cycle,
                        'close_cycle': 0 if is_open_action else global_state.cycle_counter,
                        'action': order_params['action'].upper(),
                        'symbol': self.current_symbol,
                        'price': entry_price,
                        'quantity': order_params['quantity'],
                        'cost': entry_price * order_params['quantity'],
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'confidence': order_params['confidence'],
                        'status': 'EXECUTED',
                        'cycle': cycle_id
                    }
                    if is_close_action:
                         trade_record['status'] = 'CLOSED (Fallback)'
                         
                    self.saver.save_trade(trade_record)
                    
                    # Update Global State History
                    global_state.trade_history.insert(0, trade_record)
                    if len(global_state.trade_history) > 50:
                        global_state.trade_history.pop()
                
                return {
                    'status': 'success',
                    'action': vote_result.action,
                    'details': order_params,
                    'current_price': current_price
                }
            else:
                print("  ❌ Order execution failed")
                global_state.add_log(f"❌ Order Failed: {order_params['action'].upper()}")
                return {
                    'status': 'failed',
                    'action': vote_result.action,
                    'details': {'error': 'execution_failed'},
                    'current_price': current_price
                }
        
        except Exception as e:
            log.error(f"Trading cycle exception: {e}", exc_info=True)
            global_state.add_log(f"Error: {e}")
            return {
                'status': 'error',
                'details': {'error': str(e)}
            }
    
    def _build_order_params(
        self, 
        action: str, 
        current_price: float,
        confidence: float
    ) -> Dict:
        """
        Build order parameters
        
        Args:
            action: 'long' or 'short'
            current_price: Current price
            confidence: Decision confidence (0-1)
        
        Returns:
            Order parameters dictionary
        """
        # Get available balance
        if self.test_mode:
            available_balance = global_state.virtual_balance
        else:
            available_balance = self._get_account_balance()
        
        # Dynamic position sizing: At 100% confidence, use 30% of available balance
        # Formula: Position ratio = Base ratio (30%) × Confidence
        base_position_pct = 0.30  # Maximum position ratio 30%
        position_pct = base_position_pct * min(confidence, 1.0)  # Adjust based on confidence
        
        # Calculate position amount (fully based on available balance percentage)
        adjusted_position = available_balance * position_pct
        
        # Calculate quantity
        quantity = adjusted_position / current_price
        
        # Calculate stop-loss and take-profit
        if action == 'long':
            stop_loss = current_price * (1 - self.stop_loss_pct / 100)
            take_profit = current_price * (1 + self.take_profit_pct / 100)
        else:  # short
            stop_loss = current_price * (1 + self.stop_loss_pct / 100)
            take_profit = current_price * (1 - self.take_profit_pct / 100)
        
        return {
            'action': action,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'quantity': quantity,
            'position_value': adjusted_position,  # Added: Actual position amount
            'position_pct': position_pct * 100,   # Added: Position percentage
            'leverage': self.leverage,
            'confidence': confidence
        }
    
    def _get_account_balance(self) -> float:
        """Get account available balance"""
        try:
            return self.client.get_account_balance()
        except Exception as e:
            log.error(f"Failed to get balance: {e}")
            return 0.0
    
    def _get_current_position(self) -> Optional[PositionInfo]:
        """Get current position (supports Live + Test Mode)"""
        try:
            # 1. Test Mode Support
            if self.test_mode:
                if self.current_symbol in global_state.virtual_positions:
                    v_pos = global_state.virtual_positions[self.current_symbol]
                    return PositionInfo(
                        symbol=self.current_symbol,
                        side=v_pos['side'].lower(), # ensure lowercase 'long'/'short'
                        entry_price=v_pos['entry_price'],
                        quantity=v_pos['quantity'],
                        unrealized_pnl=v_pos.get('unrealized_pnl', 0)
                    )
                return None

            # 2. Live Mode Support
            pos = self.client.get_futures_position(self.current_symbol)
            if pos and abs(pos['position_amt']) > 0:
                return PositionInfo(
                    symbol=self.current_symbol,
                    side='long' if pos['position_amt'] > 0 else 'short',
                    entry_price=pos['entry_price'],
                    quantity=abs(pos['position_amt']),
                    unrealized_pnl=pos['unrealized_profit']
                )
            return None
        except Exception as e:
            log.error(f"Failed to get positions: {e}")
            return None
    
    def _execute_order(self, order_params: Dict) -> bool:
        """
        Execute order
        
        Args:
            order_params: Order parameters
        
        Returns:
            Whether successful
        """
        try:
            # Set leverage
            self.client.set_leverage(
                symbol=self.current_symbol,
                leverage=order_params['leverage']
            )
            
            # Market order entry
            side = 'BUY' if order_params['action'] == 'long' else 'SELL'
            order = self.client.place_futures_market_order(
                symbol=self.current_symbol,
                side=side,
                quantity=order_params['quantity']
            )
            
            if not order:
                return False
            
            # Set stop-loss and take-profit
            self.execution_engine.set_stop_loss_take_profit(
                symbol=self.current_symbol,
                position_side='LONG' if order_params['action'] == 'long' else 'SHORT',
                stop_loss=order_params['stop_loss'],
                take_profit=order_params['take_profit']
            )
            
            return True
            
        except Exception as e:
            log.error(f"Order execution failed: {e}", exc_info=True)
            return False
    
    
    

    def _build_market_context(self, quant_analysis: Dict, predict_result, market_data: Dict, regime_info: Dict = None, position_info: Dict = None) -> str:
        """
        Build market context text required by DeepSeek LLM
        """
        # Extract key data
        current_price = market_data['current_price']
        
        # Format trend analysis
        trend = quant_analysis.get('trend', {})
        trend_details = trend.get('details', {})
        
        oscillator = quant_analysis.get('oscillator', {})
        
        sentiment = quant_analysis.get('sentiment', {})
        
        # Prophet prediction (semantic conversion)
        prob_pct = predict_result.probability_up * 100
        prophet_signal = predict_result.signal
        
        # Semantic conversion logic (Prophet)
        if prob_pct >= 80:
            prediction_desc = f"Strong Uptrend Forecast (High Probability of Rising > 80%, Value: {prob_pct:.1f}%)"
        elif prob_pct >= 60:
            prediction_desc = f"Bullish Bias (Likely to Rise 60-80%, Value: {prob_pct:.1f}%)"
        elif prob_pct <= 20:
            prediction_desc = f"Strong Downtrend Forecast (High Probability of Falling > 80%, Value: {prob_pct:.1f}%)"
        elif prob_pct <= 40:
            prediction_desc = f"Bearish Bias (Likely to Fall 60-80%, Value: {prob_pct:.1f}%)"
        else:
            prediction_desc = f"Uncertain/Neutral (40-60%, Value: {prob_pct:.1f}%)"

        # Semantic conversion (Technical Indicators)
        t_score_total = trend.get('total_trend_score')  # Default to None
        t_semantic = SemanticConverter.get_trend_semantic(t_score_total)
        # Individual Trend Scores
        t_1h_score = trend.get('trend_1h_score') 
        t_15m_score = trend.get('trend_15m_score')
        t_5m_score = trend.get('trend_5m_score')
        t_1h_sem = SemanticConverter.get_trend_semantic(t_1h_score)
        t_15m_sem = SemanticConverter.get_trend_semantic(t_15m_score)
        t_5m_sem = SemanticConverter.get_trend_semantic(t_5m_score)
        
        o_score_total = oscillator.get('total_osc_score')
        o_semantic = SemanticConverter.get_oscillator_semantic(o_score_total)
        
        s_score_total = sentiment.get('total_sentiment_score')
        s_semantic = SemanticConverter.get_sentiment_score_semantic(s_score_total)

        rsi_15m = oscillator.get('oscillator_15m', {}).get('details', {}).get('rsi_value')
        rsi_1h = oscillator.get('oscillator_1h', {}).get('details', {}).get('rsi_value')
        rsi_15m_semantic = SemanticConverter.get_rsi_semantic(rsi_15m)
        rsi_1h_semantic = SemanticConverter.get_rsi_semantic(rsi_1h)
        
        # MACD
        macd_15m = trend.get('details', {}).get('15m_macd_diff')
        macd_semantic = SemanticConverter.get_macd_semantic(macd_15m)
        
        oi_change = sentiment.get('oi_change_24h_pct', 0)
        oi_semantic = SemanticConverter.get_oi_change_semantic(oi_change)
        
        # Market state and price position
        regime_type = "Unknown"
        regime_confidence = 0
        price_position = "Unknown"
        price_position_pct = 50
        if regime_info:
            regime_type = regime_info.get('regime', 'unknown')
            regime_confidence = regime_info.get('confidence', 0)
            position_info_regime = regime_info.get('position', {})
            price_position = position_info_regime.get('location', 'unknown')
            price_position_pct = position_info_regime.get('position_pct', 50)
        
        # Helper to format values safely
        def fmt_val(val, fmt="{:.2f}"):
            return fmt.format(val) if val is not None else "N/A"
            
        # Build position info text (New)
        position_section = ""
        if position_info:
            side_icon = "🟢" if position_info['side'] == 'LONG' else "🔴"
            pnl_icon = "💰" if position_info['unrealized_pnl'] > 0 else "💸"
            position_section = f"""
## 💼 CURRENT POSITION STATUS (Virtual Sub-Agent Logic)
> ⚠️ CRITICAL: YOU ARE HOLDING A POSITION. EVALUATE EXIT CONDITIONS FIRST.

- **Status**: {side_icon} {position_info['side']}
- **Entry Price**: ${position_info['entry_price']:,.2f}
- **Current Price**: ${current_price:,.2f}
- **PnL**: {pnl_icon} ${position_info['unrealized_pnl']:.2f} ({position_info['pnl_pct']:+.2f}%)
- **Quantity**: {position_info['quantity']}
- **Leverage**: {position_info['leverage']}x

**EXIT JUDGMENT INSTRUCTION**:
1. **Trend Reversal**: If current trend contradicts position side (e.g. Long but Trend turned Bearish), consider CLOSE.
2. **Profit/Risk**: Check if PnL is satisfactory or risk is increasing.
3. **If Closing**: Return `close_position` action.
"""
        
        context = f"""
## 1. Price & Position Overview
- Symbol: {self.current_symbol}
- Current Price: ${current_price:,.2f}

{position_section}

## 2. Four-Layer Strategy Status
"""
        # Build four-layer status summary with smart grouping
        blocking_reason = global_state.four_layer_result.get('blocking_reason', 'None')
        layer1_pass = global_state.four_layer_result.get('layer1_pass')
        layer2_pass = global_state.four_layer_result.get('layer2_pass')
        layer3_pass = global_state.four_layer_result.get('layer3_pass')
        layer4_pass = global_state.four_layer_result.get('layer4_pass')
        
        layer_status = []
        
        # Smart grouping: if both Layer 1 and 2 fail with same reason, merge them
        if not layer1_pass and not layer2_pass:
            layer_status.append(f"❌ **Layers 1-2 BLOCKED**: {blocking_reason}")
        else:
            if layer1_pass:
                layer_status.append("✅ **Trend/Fuel**: PASS")
            else:
                layer_status.append(f"❌ **Trend/Fuel**: FAIL - {blocking_reason}")
            
            if layer2_pass:
                layer_status.append("✅ **AI Filter**: PASS")
            else:
                layer_status.append(f"❌ **AI Filter**: VETO - {blocking_reason}")
        
        # Layer 3 & 4
        layer_status.append(f"{'✅' if layer3_pass else '⏳'} **Setup (15m)**: {'READY' if layer3_pass else 'WAIT'}")
        layer_status.append(f"{'✅' if layer4_pass else '⏳'} **Trigger (5m)**: {'CONFIRMED' if layer4_pass else 'WAITING'}")
        
        # Add risk adjustment
        tp_mult = global_state.four_layer_result.get('tp_multiplier', 1.0)
        sl_mult = global_state.four_layer_result.get('sl_multiplier', 1.0)
        if tp_mult != 1.0 or sl_mult != 1.0:
            layer_status.append(f"⚖️ **Risk Adjustment**: TP x{tp_mult} | SL x{sl_mult}")
        
        context += "\n".join(layer_status)
        
        # Add data anomaly warning
        if global_state.four_layer_result.get('data_anomalies'):
            anomalies = ', '.join(global_state.four_layer_result.get('data_anomalies', []))
            context += f"\n\n⚠️ **DATA ANOMALY**: {anomalies}"

        context += "\n\n## 3. Detailed Market Analysis\n"
        
        # Extract analysis results
        trend_result = getattr(global_state, 'semantic_analyses', {}).get('trend', {})
        setup_result = getattr(global_state, 'semantic_analyses', {}).get('setup', {})
        trigger_result = getattr(global_state, 'semantic_analyses', {}).get('trigger', {})
        
        # Trend Analysis (formerly TREND AGENT)
        if isinstance(trend_result, dict):
            trend_analysis = trend_result.get('analysis', 'Not available')
            trend_stance = trend_result.get('stance', 'UNKNOWN')
            trend_meta = trend_result.get('metadata', {})
            trend_header = f"### 🔮 Trend & Direction Analysis [{trend_stance}] (Strength: {trend_meta.get('strength', 'N/A')}, ADX: {trend_meta.get('adx', 'N/A')})"
        else:
            trend_analysis = trend_result if trend_result else 'Not available'
            trend_header = "🔮 Trend & Direction Analysis"
            
        # Entry Zone Analysis (formerly SETUP AGENT)
        if isinstance(setup_result, dict):
            setup_analysis = setup_result.get('analysis', 'Not available')
            setup_stance = setup_result.get('stance', 'UNKNOWN')
            setup_meta = setup_result.get('metadata', {})
            setup_header = f"### 📊 Entry Zone Analysis [{setup_stance}] (Zone: {setup_meta.get('zone', 'N/A')}, KDJ: {setup_meta.get('kdj_j', 'N/A')})"
        else:
            setup_analysis = setup_result if setup_result else 'Not available'
            setup_header = "### 📊 Entry Zone Analysis"

        # Entry Timing Signal (formerly TRIGGER AGENT)
        if isinstance(trigger_result, dict):
            trigger_analysis = trigger_result.get('analysis', 'Not available')
            trigger_stance = trigger_result.get('stance', 'UNKNOWN')
            trigger_meta = trigger_result.get('metadata', {})
            trigger_header = f"### ⚡ Entry Timing Signal [{trigger_stance}] (Pattern: {trigger_meta.get('pattern', 'NONE')}, RVOL: {trigger_meta.get('rvol', 'N/A')}x)"
        else:
            trigger_analysis = trigger_result if trigger_result else 'Not available'
            trigger_header = "### ⚡ Entry Timing Signal"

        context += f"\n{trend_header}\n{trend_analysis}\n"
        context += f"\n{setup_header}\n{setup_analysis}\n"
        context += f"\n{trigger_header}\n{trigger_analysis}\n"
        
        # Note: Market Regime and Price Position are already calculated by TREND and SETUP agents
        # and included in their respective analyses above, so we don't duplicate them here.
        
        return context

# ... locating where vote_result is processed to add semantic analysis


    def run_once(self) -> Dict:
        """Run one trading cycle (synchronous wrapper)"""
        result = asyncio.run(self.run_trading_cycle())
        self._display_recent_trades()
        return result

    def _display_recent_trades(self):
        """Display recent trade records (enhanced table)"""
        trades = self.saver.get_recent_trades(limit=10)
        if not trades:
            return
            
        print("\n" + "─"*100)
        print("📜 Last 10 Trade Audits (The Executor History)")
        print("─"*100)
        header = f"{'Time':<12} | {'Symbol':<8} | {'Action':<10} | {'Price':<10} | {'Cost':<10} | {'Exit':<10} | {'PnL':<10} | {'Status'}"
        print(header)
        print("─"*100)
        
        for t in trades:
            # Simplify time
            fmt_time = str(t.get('record_time', 'N/A'))[5:16]
            symbol = t.get('symbol', 'BTC')[:7]
            action = t.get('action', 'N/A')
            price = f"${float(t.get('price', 0)):,.1f}"
            cost = f"${float(t.get('cost', 0)):,.1f}"
            exit_p = f"${float(t.get('exit_price', 0)):,.1f}" if float(t.get('exit_price', 0)) > 0 else "-"
            
            pnl_val = float(t.get('pnl', 0))
            pnl_str = f"{'+' if pnl_val > 0 else ''}${pnl_val:,.2f}" if pnl_val != 0 else "-"
            
            status = t.get('status', 'N/A')
            
            row = f"{fmt_time:<12} | {symbol:<8} | {action:<10} | {price:<10} | {cost:<10} | {exit_p:<10} | {pnl_str:<10} | {status}"
            print(row)
        print("─"*100)
    
    def get_statistics(self) -> Dict:
        """Get statistics"""
        stats = {
            'risk_audit': self.risk_audit.get_audit_report(),
        }
        # DeepSeek mode doesn't have decision_core
        if hasattr(self, 'strategy_engine'):
            # self.strategy_engine currently doesn't have get_statistics method, but can return basic info
            stats['strategy_engine'] = {
                'provider': self.strategy_engine.provider,
                'model': self.strategy_engine.model
            }
        return stats

    def start_account_monitor(self):
        """Start a background thread to monitor account equity in real-time"""
        def _monitor():
            if self.test_mode:
                log.info("💰 Account Monitor Thread: Disabled in Test Mode")
                return
                
            log.info("💰 Account Monitor Thread Started")
            while True:
                # Check Control State
                if global_state.execution_mode == "Stopped":
                    break
                
                # We update even if Paused, to see PnL of open positions
                try:
                    # Get client from property (checks global_state.exchange_client)
                    active_client = self.client
                    if active_client is None:
                        time.sleep(5)
                        continue
                    
                    # Check if client has get_account method (BrokerClientWrapper)
                    if hasattr(active_client, 'get_account'):
                        acc = active_client.get_account()
                        wallet = float(acc.get('totalBalance', 0))
                        pnl = float(acc.get('totalUnrealizedProfit', 0))
                        avail = float(acc.get('availableBalance', 0))
                        equity = wallet + pnl
                    # Check if client has get_futures_account method (Binance)
                    elif hasattr(active_client, 'get_futures_account'):
                        acc = active_client.get_futures_account()
                        wallet = float(acc.get('total_wallet_balance', 0))
                        pnl = float(acc.get('total_unrealized_profit', 0))
                        avail = float(acc.get('available_balance', 0))
                        equity = wallet + pnl
                    else:
                        time.sleep(5)
                        continue
                    
                    global_state.update_account(equity, avail, wallet, pnl)
                    global_state.record_account_success()  # Track success
                except Exception as e:
                    log.error(f"Account Monitor Error: {e}")
                    global_state.record_account_failure()  # Track failure
                    global_state.add_log(f"❌ Account info fetch failed: {str(e)}")  # Dashboard log
                    time.sleep(5) # Backoff on error
                
                time.sleep(3) # Update every 3 seconds

        t = threading.Thread(target=_monitor, daemon=True)
        t.start()

    def run_continuous(self, interval_minutes: int = 3):
        """
        Continuous running mode
        
        Args:
            interval_minutes: Running interval (minutes)
        """
        log.info(f"🚀 Starting continuous mode (interval: {interval_minutes}min)")
        global_state.is_running = True
        
        # Logger is configured in src.utils.logger, no need to override here.
        # Dashboard logging is handled via global_state.add_log -> log.bind(dashboard=True)

        # Start Real-time Monitors
        self.start_account_monitor()
        
        # 🔮 Start Prophet auto-trainer (retrain every 2 hours)
        # Only start if broker is connected (not in demo mode)
        from src.models.prophet_model import ProphetAutoTrainer, HAS_LIGHTGBM
        
        # Check if client is available AND connected
        client_ready = (
            self.client is not None and 
            not self.demo_mode and 
            hasattr(self.client, 'is_connected') and 
            self.client.is_connected
        )
        
        if HAS_LIGHTGBM and client_ready:
            # Create auto-trainer for primary trading pair
            primary_agent = self.predict_agents[self.primary_symbol]
            self.auto_trainer = ProphetAutoTrainer(
                predict_agent=primary_agent,
                binance_client=self.client,
                interval_hours=2.0,  # Train every 2 hours
                training_days=70,    # Use last 70 days of data (10x samples)
                symbol=self.primary_symbol
            )
            self.auto_trainer.start()
        else:
            self.auto_trainer = None
            log.info("🔮 Prophet auto-trainer disabled (broker not connected)")
        
        # Set initial interval (CLI parameter takes priority, API can override later)
        global_state.cycle_interval = interval_minutes
        
        log.info(f"🚀 Starting continuous trading mode (interval: {global_state.cycle_interval}m)")
        
        # 🧪 Test Mode: Initialize Virtual Account for Chart
        if self.test_mode:
            log.info("🧪 Test Mode: Initializing Virtual Account...")
            initial_balance = global_state.virtual_balance
            global_state.init_balance(initial_balance)  # Initialize balance tracking
            global_state.update_account(
                equity=initial_balance,
                available=initial_balance,
                wallet=initial_balance,
                pnl=0.0
            )
        
        try:
            while global_state.is_running:
                # 🔄 Check for configuration changes
                # Method 1: .env file changed (Local mode)
                if self._env_exists:
                    try:
                        current_mtime = os.path.getmtime(self._env_path)
                        if current_mtime > self._env_mtime:
                            if self._env_mtime > 0: # Avoid reload on first pass as it's already loaded
                                log.info("📝 .env file change detected, reloading symbols...")
                                self._reload_symbols()
                            self._env_mtime = current_mtime
                    except Exception as e:
                        log.warning(f"Error checking .env mtime: {e}")
                
                # Method 2: Runtime config changed (Railway mode)
                if global_state.config_changed:
                    log.info("⚙️ Runtime config change detected, reloading symbols...")
                    self._reload_symbols()
                    global_state.config_changed = False  # Reset flag

                # Check stop state FIRST - must break before continue
                if global_state.execution_mode == 'Stopped':
                    # Fix: Do not break, just wait.
                    if not hasattr(self, '_stop_logged') or not self._stop_logged:
                        print("\n⏹️ System stopped (waiting for start)")
                        global_state.add_log("⏹️ System STOPPED - Waiting for Start...")
                        self._stop_logged = True
                    time.sleep(1)
                    continue
                else:
                    self._stop_logged = False
                
                # Check pause state - continue waiting
                if global_state.execution_mode == 'Paused':
                    # Print log when first entering pause state
                    if not hasattr(self, '_pause_logged') or not self._pause_logged:
                        print("\n⏸️ System paused, waiting to resume...")
                        global_state.add_log("⏸️ System PAUSED - waiting for resume...")
                        self._pause_logged = True
                    time.sleep(1)
                    continue
                else:
                    self._pause_logged = False  # Reset pause log flag

                # ✅ Unified cycle counter: Increment once before iterating symbols
                global_state.cycle_counter += 1
                cycle_num = global_state.cycle_counter
                cycle_id = f"cycle_{cycle_num:04d}_{int(time.time())}"
                global_state.current_cycle_id = cycle_id
                
                # 🧹 Clear initialization logs when Cycle 1 starts (sync with Recent Decisions)
                if cycle_num == 1:
                    global_state.clear_init_logs()
                
                # 🧪 Test Mode: Record start of cycle account state (for Net Value Curve)
                if self.test_mode:
                    # Re-log current state with new cycle number so chart shows start of cycle
                    global_state.update_account(
                        equity=global_state.account_overview['total_equity'],
                        available=global_state.account_overview['available_balance'],
                        wallet=global_state.account_overview['wallet_balance'],
                        pnl=global_state.account_overview['total_pnl']
                    )
                
                print(f"\n{'='*80}")
                print(f"🔄 Cycle #{cycle_num} | Analyzing {len(self.symbols)} trading pairs")
                print(f"{'='*80}")
                global_state.add_log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                global_state.add_log(f"[📊 SYSTEM] Cycle #{cycle_num} | {', '.join(self.symbols)}")

                # 🔌 Check if broker is connected before starting cycle
                if self.client is None:
                    print("⚠️ Broker not connected - waiting for connection...")
                    global_state.add_log("[⚠️ SYSTEM] Broker not connected - please connect from Settings > Accounts")
                    time.sleep(5)
                    continue

                # 🎯 Reset cycle position counter
                global_state.cycle_positions_opened = 0
                
                # 🔄 Multi-symbol sequential processing: Analyze each trading pair in order
                # Step 1: Collect decisions from all trading pairs
                all_decisions = []
                latest_prices = {}  # Store latest prices for PnL calculation
                for symbol in self.symbols:
                    self.current_symbol = symbol  # Set current trading pair being processed
                    
                    # Analyze each symbol first without executing OPEN actions
                    result = asyncio.run(self.run_trading_cycle(analyze_only=True))
                    
                    # Get latest price for this symbol
                    latest_prices[symbol] = global_state.current_price.get(symbol, 0)
                    
                    print(f"  [{symbol}] Result: {result['status']}")
                    
                    # Collect viable open opportunities
                    if result.get('status') == 'suggested':
                        all_decisions.append({
                            'symbol': symbol,
                            'result': result,
                            'confidence': result.get('confidence', 0)
                        })
                
                # Step 2: Select the highest confidence decision from all open decisions
                if all_decisions:
                    # Sort by confidence
                    all_decisions.sort(key=lambda x: x['confidence'], reverse=True)
                    best_decision = all_decisions[0]
                    
                    print(f"\n🎯 Best open opportunity this cycle: {best_decision['symbol']} (Confidence: {best_decision['confidence']:.1f}%)")
                    global_state.add_log(f"[🎯 SYSTEM] Best: {best_decision['symbol']} (Conf: {best_decision['confidence']:.1f}%)")
                    
                    # Only execute the best one
                    # Note: Actual execution is already done in run_trading_cycle
                    # This is just for logging and notification
                    
                    # If other open opportunities were skipped, log them
                    if len(all_decisions) > 1:
                        skipped = [f"{d['symbol']}({d['confidence']:.1f}%)" for d in all_decisions[1:]]
                        print(f"  ⏭️  Skipped other opportunities: {', '.join(skipped)}")
                        global_state.add_log(f"⏭️  Skipped opportunities: {', '.join(skipped)} (1 position per cycle limit)")
                
                        global_state.add_log(f"⏭️  Skipped opportunities: {', '.join(skipped)} (1 position per cycle limit)")
                
                # 💰 Update Virtual Account PnL (Mark-to-Market)
                if self.test_mode:
                    self._update_virtual_account_stats(latest_prices)
                
                # Dynamic Interval: specific to new requirement
                current_interval = global_state.cycle_interval
                
                # Wait for next check
                print(f"\n⏳ Waiting {current_interval} minutes...")
                
                # Sleep in chunks to allow responsive PAUSE/STOP and INTERVAL changes
                # Check every 1 second during the wait interval
                elapsed_seconds = 0
                while True:
                    # Check current interval setting every second (supports dynamic adjustment)
                    current_interval = global_state.cycle_interval
                    wait_seconds = current_interval * 60
                    
                    # If waited long enough, end waiting
                    if elapsed_seconds >= wait_seconds:
                        break
                    
                    # Check execution mode
                    if global_state.execution_mode != "Running":
                        break
                    
                    # Heartbeat every 60s
                    if elapsed_seconds > 0 and elapsed_seconds % 60 == 0:
                        remaining = int((wait_seconds - elapsed_seconds) / 60)
                        if remaining > 0:
                             print(f"⏳ Next cycle in {remaining}m...")
                             global_state.add_log(f"[📊 SYSTEM] Waiting next cycle... ({remaining}m)")

                    time.sleep(1)
                    elapsed_seconds += 1
                
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Received stop signal, exiting...")
            global_state.is_running = False

    def _update_virtual_account_stats(self, latest_prices: Dict[str, float]):
        """
        [Test Mode] Update virtual account statistics (equity, PnL) and push to Global State
        """
        if not self.test_mode:
            return

        total_unrealized_pnl = 0.0
        
        # Iterate positions to calculate unrealized PnL
        for symbol, pos in global_state.virtual_positions.items():
            current_price = latest_prices.get(symbol)
            if not current_price:
                 # Fallback to stored price if current not available
                 current_price = pos.get('current_price', pos['entry_price'])
                
            entry_price = pos['entry_price']
            quantity = pos['quantity']
            side = pos['side']  # LONG or SHORT
            
            # PnL Calc
            if side.upper() == 'LONG':
                pnl = (current_price - entry_price) * quantity
            else:
                pnl = (entry_price - current_price) * quantity
                
            pos['unrealized_pnl'] = pnl
            pos['current_price'] = current_price
            total_unrealized_pnl += pnl

        # Update equity
        # Equity = Balance (Realized) + Unrealized PnL
        total_equity = global_state.virtual_balance + total_unrealized_pnl
        
        # Calculate real total PnL (compared to initial capital)
        # Total PnL = Current Equity - Initial Balance
        real_total_pnl = total_equity - global_state.virtual_initial_balance
        
        # Update Global State
        global_state.update_account(
            equity=total_equity,
            available=global_state.virtual_balance,
            wallet=global_state.virtual_balance,
            pnl=real_total_pnl  # ✅ Fix: Pass total profit/loss from start
        )


    def _save_virtual_state(self):
        """Helper to persist virtual account state"""
        if self.test_mode:
            self.saver.save_virtual_account(
                balance=global_state.virtual_balance,
                positions=global_state.virtual_positions
            )

def start_server():
    """Start FastAPI server in a separate thread"""
    import os
    port = int(os.getenv("PORT", 8000))
    print(f"\n🌍 Starting Web Dashboard at http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="error")

# ============================================
# Main Entry
# ============================================
def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-Agent Trading Bot')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--max-position', type=float, default=100.0, help='Maximum single position amount')
    parser.add_argument('--leverage', type=int, default=1, help='Leverage multiplier')
    parser.add_argument('--stop-loss', type=float, default=1.0, help='Stop-loss percentage')
    parser.add_argument('--take-profit', type=float, default=2.0, help='Take-profit percentage')
    parser.add_argument('--mode', choices=['once', 'continuous'], default='continuous', help='Running mode')
    parser.add_argument('--interval', type=float, default=3.0, help='Continuous running interval (minutes)')
    
    args = parser.parse_args()
    
    # [NEW] Check RUN_MODE from .env (Config Manager integration)
    import os
    env_run_mode = os.getenv('RUN_MODE', 'test').lower()
    
    # Priority: Command line > Env Var
    if not args.test and env_run_mode == 'test':
        args.test = True
    elif args.test and env_run_mode == 'live':
        pass # Command line override to force test? or live? Let's say explicit CLI wins.
        
    print(f"🔧 Startup Mode: {'TEST' if args.test else 'LIVE'} (Env: {env_run_mode})")
    
    # ==============================================================================
    # 🛠️ [Core Fix]: Force initialize database table structure
    # Just instantiating TradingLogger will automatically execute _init_database() to create PostgreSQL tables
    # ==============================================================================
    try:
        log.info("🛠️ Checking/initializing database tables...")
        # This step is crucial: it connects to the database and runs CREATE TABLE statements
        _db_init = TradingLogger()
        log.info("✅ Database tables ready")
    except Exception as e:
        log.error(f"❌ Database init failed (non-fatal, continuing): {e}")
        # Note: We catch the exception but don't exit to avoid affecting main program startup, but please pay attention to logs
    # ==============================================================================
    
    # Set default cycle interval based on deployment mode
    # Local: 1 minute (for development testing)
    # Railway: 5 minutes (production environment)
    if args.interval == 3.0:  # If user didn't specify interval via CLI
        if DEPLOYMENT_MODE == 'local':
            args.interval = 1.0
            print(f"🏠 Local mode: Cycle interval set to 1 minute")
        else:
            args.interval = 5.0
            print(f"☁️ Railway mode: Cycle interval set to 5 minutes")
    
    
    # Create bot
    bot = MultiAgentTradingBot(
        max_position_size=args.max_position,
        leverage=args.leverage,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        test_mode=args.test
    )
    
    # Start Dashboard Server (Only if in continuous mode or if explicitly requested, but let's do it always for now if deps exist)
    try:
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
    except Exception as e:
        print(f"⚠️ Failed to start Dashboard: {e}")
    
    # Run
    if args.mode == 'once':
        result = bot.run_once()
        print(f"\nFinal Result: {json.dumps(result, indent=2)}")
        
        # Display statistics
        stats = bot.get_statistics()
        print(f"\nStatistics:")
        print(json.dumps(stats, indent=2))
        
        # Keep alive briefly for server to be reachable if desired, 
        # or exit immediately. Usually 'once' implies run and exit.
        
    else:
        # [CHANGE] Default to Stopped - Always require user to click START from Dashboard
        global_state.execution_mode = "Stopped"
        log.info("⏸️ System ready (Stopped). Waiting for user to START from Dashboard.")
        bot.run_continuous(interval_minutes=args.interval)

if __name__ == '__main__':
    main()
