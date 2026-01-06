// Lightweight i18n Configuration for LLM-TradeBot Dashboard (English Only)
const i18n = {
    en: {
        // Header
        'header.mode': 'MODE',
        'header.environment': 'ENVIRONMENT',
        'header.cycle': 'CYCLE',
        'header.equity': 'EQUITY',

        // Buttons
        'btn.settings': 'Settings',
        'btn.backtest': 'Backtest',
        'btn.logout': 'Exit',
        'btn.start': 'Start Trading',
        'btn.pause': 'Pause Trading',
        'btn.stop': 'Stop System',

        // Main Sections
        'section.kline': '📉 Real-time K-Line',
        'section.netvalue': '📈 Net Value Curve',
        'section.decisions': '📋 Recent Decisions',
        'section.trades': '📜 Trade History',
        'section.logs': '📡 Live Log Output',

        // Net Value Chart
        'chart.initial': 'Initial Balance',
        'chart.current': 'Current Funds',
        'chart.available': 'Available',
        'chart.profit': 'Total Profit',

        // Decision Table - Agent Groups
        'group.system': '📊 System',
        'group.strategist': '📈 Strategy',
        'group.trend': '🔮 TREND',
        'group.setup': '📊 SETUP',
        'group.trigger': '⚡ TRIGGER',
        'group.prophet': '🔮 Prophet',
        'group.bullbear': '🐂🐻 Bull/Bear',
        'group.critic': '⚖️ Critic',
        'group.guardian': '🛡️ Guard',

        // Decision Table Headers
        'table.time': 'Time',
        'table.cycle': 'Cycle',
        'table.symbol': 'Symbol',
        'table.layers': 'Layers',
        'table.adx': 'ADX',
        'table.oi': 'OI',
        'table.regime': 'Regime',
        'table.position': 'Position',
        'table.zone': 'Zone',
        'table.signal': 'Signal',
        'table.pup': 'P(Up)',
        'table.bull': '🐂Bull',
        'table.bear': '🐻Bear',
        'table.result': 'Result',
        'table.conf': 'Conf',
        'table.reason': 'Reason',
        'table.guard': 'Guard',

        // Trade History Headers
        'trade.time': 'Time',
        'trade.open': 'Open',
        'trade.close': 'Close',
        'trade.symbol': 'Symbol',
        'trade.entry': 'Entry Price',
        'trade.posvalue': 'Pos Value',
        'trade.exit': 'Exit Price',
        'trade.pnl': 'PnL',
        'trade.pnlpct': 'PnL %',
        'trade.notrades': 'No trades yet',

        // Filters
        'filter.all.symbols': 'All Symbols',
        'filter.all.results': 'All Results',
        'filter.wait': 'Wait',
        'filter.long': 'Long',
        'filter.short': 'Short',

        // Position Info
        'position.count': 'Positions',
        'position.none': 'No open positions',

        // Log Mode
        'log.simplified': 'Simplified',
        'log.detailed': 'Detailed',

        // Settings Modal
        'settings.title': '⚙️ Settings',
        'settings.tab.keys': 'API Keys',
        'settings.tab.accounts': 'Accounts',
        'settings.tab.trading': 'Trading',
        'settings.tab.strategy': 'Strategy',
        'settings.save': 'Save Changes',

        // Trading Config
        'config.mode': 'Trading Mode',
        'config.mode.test': 'Test Mode (Paper Trading)',
        'config.mode.live': 'Live Trading (Real Money)',
        'config.symbols': 'Trading Symbols',
        'config.leverage': 'Leverage',

        // Common
        'common.loading': 'Loading...',
        'common.refresh': 'Refresh',

        // Agent Documentation
        'agent.oracle.title': '🕵️ Oracle (DataSync)',
        'agent.oracle.role': 'Unified Data Provider. Multi-dimensional market snapshot.',
        'agent.oracle.feat1': 'Multi-timeframe data (5m/15m/1h) + Funding Rates',
        'agent.oracle.feat2': 'Time-slice alignment to prevent data drift',
        'agent.oracle.feat3': 'Dual View: Stable (Closed) + Real-time (Ticking)',

        'agent.strategist.title': '👨‍🔬 Strategist (QuantAnalyst)',
        'agent.strategist.role': 'Multi-dimensional Signal Generator. Core of Quant Analysis.',
        'agent.strategist.feat1': 'Trend Agent: EMA/MACD Direction Judgment',
        'agent.strategist.feat2': 'Oscillator Agent: RSI/BB Overbought/Oversold',
        'agent.strategist.feat3': 'Sentiment Agent: Funding Rate/Flow Anomalies',

        'agent.prophet.title': '🔮 Prophet (Predict)',
        'agent.prophet.role': 'ML Prediction Engine. Probabilistic Decision Support.',
        'agent.prophet.feat1': 'LightGBM 50+ Features. Auto-retrain every 2h',
        'agent.prophet.feat2': '30-min Price Direction Probability (0-100%)',
        'agent.prophet.feat3': 'SHAP Feature Importance Analysis',

        'agent.critic.title': '⚖️ Critic (DecisionCore)',
        'agent.critic.role': 'LLM Adversarial Judge. Final Decision Hub.',
        'agent.critic.feat1': 'Market Regime: Trend / Chop / Chaos',
        'agent.critic.feat2': 'Price Position: High / Mid / Low',
        'agent.critic.feat3': '🐂🐻 Bull/Bear Debate → Weighted Voting',

        'agent.guardian.title': '🛡️ Guardian (RiskAudit)',
        'agent.guardian.role': 'Independent Risk Audit. Has Veto Power.',
        'agent.guardian.feat1': 'R/R Check: Min 2:1 Risk-Reward',
        'agent.guardian.feat2': 'Drawdown Protection: Auto-pause on threshold',
        'agent.guardian.feat3': 'Twisted Protection: Block counter-trend trades',

        'agent.mentor.title': '🪞 Mentor (Reflection)',
        'agent.mentor.role': 'Trade Review Analysis. Continuous Evolution.',
        'agent.mentor.feat1': 'Triggers LLM Deep Review every 10 trades',
        'agent.mentor.feat2': 'Pattern Recognition: Success/Failure summary',
        'agent.mentor.feat3': 'Insight Injection: Feedback to Critic for optimization',

        // Backtest Page
        'backtest.title': '🔬 Backtesting',
        'backtest.config': '⚙️ Configuration',
        'backtest.symbols': 'Symbols',
        'backtest.daterange': '📅 Date Range',
        'backtest.start': 'Start',
        'backtest.end': 'End',
        'backtest.capital': '💰 Capital',
        'backtest.timestep': '⏱ Step',
        'backtest.stoploss': '🔻 SL%',
        'backtest.takeprofit': '🔺 TP%',
        'backtest.advanced': '⚙️ Advanced Settings',
        'backtest.leverage': 'Leverage',
        'backtest.margin': 'Margin Mode',
        'backtest.contract': 'Contract Type',
        'backtest.feetier': 'Fee Tier',
        'backtest.strategy': 'Strategy Mode',
        'backtest.strategy.technical': '📊 Technical (EMA)',
        'backtest.strategy.agent': '🤖 Multi-Agent (Simulated)',
        'backtest.funding': 'Include Funding Rate',
        'backtest.run': '▶️ Run Backtest',
        'backtest.running': '⏳ Running...',
        'backtest.results': '📊 Results',
        'backtest.history': '📜 Recent Backtests',
        'backtest.equity': '📈 Equity Curve',
        'backtest.drawdown': '📉 Drawdown',
        'backtest.trades': '📋 Trade History',
        'backtest.back': '← Back to Dashboard',
        'backtest.nohistory': 'No backtest history yet',
        'backtest.clickview': 'Click to view details',
        // Metrics
        'metric.return': 'Total Return',
        'metric.annual': 'Annual Return',
        'metric.maxdd': 'Max Drawdown',
        'metric.sharpe': 'Sharpe Ratio',
        'metric.winrate': 'Win Rate',
        'metric.trades': 'Total Trades',
        'metric.pf': 'Profit Factor',
        'metric.avgtrade': 'Avg Trade',
        // Trade Table
        'trade.time': 'Time',
        'trade.side': 'Side',
        'trade.entry': 'Entry',
        'trade.exit': 'Exit',
        'trade.pnl': 'PnL',
        'trade.pnlpct': 'PnL%',
        'trade.duration': 'Duration',
        'trade.reason': 'Reason',

        // Backtest Symbol Buttons
        'backtest.symbol.major': 'Major',
        'backtest.symbol.ai500': 'AI500',
        'backtest.symbol.alts': 'Alts',
        'backtest.symbol.all': 'All',
        'backtest.symbol.clear': 'Clear',
        'backtest.symbol.selected': 'Selected',

        // Backtest Date Range Buttons
        'backtest.date.1day': '1 Day',
        'backtest.date.3days': '3 Days',
        'backtest.date.7days': '7 Days',
        'backtest.date.14days': '14 Days',
        'backtest.date.30days': '30 Days',

        // Backtest Form Labels
        'backtest.label.capital': 'Capital',
        'backtest.label.step': 'Step',
        'backtest.label.sl': 'SL%',
        'backtest.label.tp': 'TP%',

        // Backtest Advanced Settings
        'backtest.funding.settlement': 'Include Funding Rate Settlement',

        // Backtest History Metrics (Short Form)
        'metric.winrate.short': 'WIN RATE',
        'metric.trades.short': 'TRADES',
        'metric.maxdd.short': 'MAX DD',

        // Backtest Results Sections
        'metric.section.risk': 'RISK METRICS',
        'metric.section.trading': 'TRADING',
        'metric.section.longshort': 'LONG/SHORT',

        // Detailed Metrics
        'metric.sortino': 'Sortino Ratio',
        'metric.volatility': 'Volatility',
        'metric.longtrades': 'Long Trades',
        'metric.shorttrades': 'Short Trades',
        'metric.avghold': 'Avg Hold Time',

        // Backtest Live Metrics
        'metric.currentequity': 'Current Equity:',
        'metric.currentprofit': 'Profit:',
        'metric.tradecount': 'Trades:',
        'metric.livewrate': 'Win Rate:',
        'metric.livemaxdd': 'Max DD:',
        'metric.finalequity': 'Final Equity',
        'metric.profit': 'Profit/Loss',
        'backtest.liveequity': '📈 Live Equity Curve',
        'backtest.livedrawdown': '📉 Live Drawdown',
        'backtest.livetrades': '💼 Recent Trades',
        'trade.price': 'Price'
    }
};

// Export for use in app.js
if (typeof window !== 'undefined') {
    window.i18n = i18n;
}
