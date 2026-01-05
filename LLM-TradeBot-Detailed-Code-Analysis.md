# LLM-TradeBot - Complete Code Analysis Report
# LLM-TradeBot - संपूर्ण कोड विश्लेषण रिपोर्ट

---

## 📁 Project Structure Overview / प्रोजेक्ट संरचना अवलोकन

```
LLM-TradeBot/
├── main.py                          # 🚀 Entry Point / मुख्य प्रवेश बिंदु
├── backtest.py                      # 📊 Backtest CLI
├── config.example.yaml              # ⚙️ Configuration Template
├── .env.example                     # 🔐 Environment Variables Template
├── requirements.txt                 # 📦 Python Dependencies
├── Dockerfile                       # 🐳 Docker Configuration
│
├── config/                          # ⚙️ Configuration Files
│   ├── accounts.example.json        # Multi-account config
│   ├── custom_prompt.md             # Custom LLM prompt
│   ├── data_alignment.yaml          # Data alignment settings
│   └── logging_config.yaml          # Logging configuration
│
├── src/                             # 📂 Source Code
│   ├── agents/                      # 🤖 AI Agents (12 Agents)
│   ├── api/                         # 🔌 Exchange APIs
│   ├── backtest/                    # 📈 Backtesting Engine
│   ├── config/                      # ⚙️ Config Management
│   ├── data/                        # 📊 Data Processing
│   ├── exchanges/                   # 💱 Exchange Integrations
│   ├── execution/                   # 🎯 Order Execution
│   ├── features/                    # 🔧 Feature Engineering
│   ├── llm/                         # 🧠 LLM Providers
│   ├── models/                      # 🔮 ML Models
│   ├── monitoring/                  # 📡 Logging & Monitoring
│   ├── risk/                        # 🛡️ Risk Management
│   ├── server/                      # 🌐 FastAPI Server
│   ├── strategy/                    # 📋 Strategy Engine
│   └── utils/                       # 🔧 Utilities
│
├── web/                             # 🖥️ Frontend Dashboard
│   ├── index.html                   # Main dashboard
│   ├── backtest.html                # Backtest interface
│   ├── login.html                   # Login page
│   ├── app.js                       # Main JavaScript
│   ├── i18n.js                      # Internationalization
│   └── style.css                    # Styles
│
├── docs/                            # 📚 Documentation
├── models/                          # 🔮 Trained ML Models
├── reports/                         # 📊 Backtest Reports
├── research/                        # 🔬 Research Scripts
├── scripts/                         # 🛠️ Utility Scripts
└── tests/                           # 🧪 Test Files
```

---

## 🚀 1. main.py - Entry Point / मुख्य प्रवेश बिंदु

### English:
The main entry point that orchestrates the entire trading bot. It initializes all agents, manages the trading loop, and coordinates between components.

### Hindi:
यह मुख्य प्रवेश बिंदु है जो पूरे ट्रेडिंग बॉट को संचालित करता है। यह सभी एजेंट्स को इनिशियलाइज़ करता है, ट्रेडिंग लूप को मैनेज करता है, और कंपोनेंट्स के बीच समन्वय करता है।

### Key Components / मुख्य घटक:

```python
class MultiAgentTradingBot:
    """
    Multi-Agent Trading Robot (Refactored Version)
    
    Workflow:
    1. DataSyncAgent: Async fetch 5m/15m/1h data
    2. QuantAnalystAgent: Generate quant signals (trend + oscillator)
    3. DecisionCoreAgent: Weighted voting decision
    4. RiskAuditAgent: Risk audit interception
    5. ExecutionEngine: Execute trades
    """
```

### Features / विशेषताएं:
- **Multi-Symbol Support**: BTCUSDT, ETHUSDT, AI500_TOP5 (dynamic)
- **Test Mode**: Virtual $1000 balance for safe testing
- **Multi-Account**: Manage multiple exchange accounts
- **AI500 Dynamic Selection**: Auto-selects top 5 AI coins by volume every 6 hours

---

## 🤖 2. src/agents/ - AI Agents / एआई एजेंट्स

### 2.1 DataSyncAgent (The Oracle) / डेटा सिंक एजेंट

**File**: `src/agents/data_sync_agent.py`

```python
class DataSyncAgent:
    """
    Data Oracle - Async concurrent data fetching
    
    Optimizations:
    - Concurrent IO (saves 60% time)
    - Dual-view data (stable + live)
    - Time alignment verification
    """
```

**Functions / कार्य:**
- `fetch_all_timeframes()`: Fetches 5m, 15m, 1h K-lines concurrently
- `_to_dataframe()`: Converts raw klines to pandas DataFrame
- `_check_alignment()`: Verifies time alignment across timeframes

**Data Structure / डेटा संरचना:**
```python
@dataclass
class MarketSnapshot:
    stable_5m: pd.DataFrame   # Completed candles
    live_5m: Dict             # Current candle
    stable_15m: pd.DataFrame
    live_15m: Dict
    stable_1h: pd.DataFrame
    live_1h: Dict
    timestamp: datetime
    alignment_ok: bool
    quant_data: Dict          # External quant data
    binance_funding: Dict     # Funding rate
    binance_oi: Dict          # Open Interest
```

---

### 2.2 QuantAnalystAgent (The Strategist) / क्वांट एनालिस्ट एजेंट

**File**: `src/agents/quant_analyst_agent.py`

```python
class QuantAnalystAgent:
    """
    Quantitative Strategist - Technical Analysis
    
    Provides:
    - Trend analysis (EMA alignment)
    - Oscillator analysis (RSI, KDJ)
    - Sentiment analysis (Funding rate, Volume)
    - Market regime detection
    """
```

**Key Methods / मुख्य मेथड्स:**
- `analyze_trend()`: EMA-based trend scoring (-100 to +100)
- `analyze_oscillator()`: RSI/KDJ-based oscillator scoring
- `_analyze_sentiment()`: Funding rate & volume analysis
- `analyze_all_timeframes()`: Complete multi-timeframe analysis

**Indicators Calculated / गणना किए गए इंडिकेटर्स:**
- EMA (20, 60)
- RSI (14)
- KDJ (9, 3, 3)
- ATR (14)
- Bollinger Bands

---

### 2.3 PredictAgent (The Prophet) / प्रेडिक्ट एजेंट

**File**: `src/agents/predict_agent.py`

```python
class PredictAgent:
    """
    Prediction Prophet - ML-based price prediction
    
    Modes:
    - Rule-based scoring (default)
    - LightGBM ML model (if trained)
    """
```

**Features Used / उपयोग की गई विशेषताएं:**
```python
FEATURE_WEIGHTS = {
    'trend_confirmation_score': 0.15,
    'ema_cross_strength': 0.10,
    'rsi': 0.12,
    'bb_position': 0.10,
    'volume_ratio': 0.07,
    'momentum_acceleration': 0.05,
    ...
}
```

**Output / आउटपुट:**
```python
@dataclass
class PredictResult:
    probability_up: float      # 0.0 - 1.0
    probability_down: float
    confidence: float
    horizon: str               # '5m', '15m', '1h'
    factors: Dict[str, float]  # Factor contributions
    model_type: str            # 'rule_based' or 'ml_lightgbm'
```

---

### 2.4 DecisionCoreAgent (The Critic) / डिसीजन कोर एजेंट

**File**: `src/agents/decision_core_agent.py`

```python
class DecisionCoreAgent:
    """
    Adversarial Critic - Weighted voting decision maker
    
    Features:
    - Weighted voting mechanism
    - Multi-period alignment detection
    - Market regime awareness
    - Position-based confidence calibration
    """
```

**Signal Weights / सिग्नल वेट्स:**
```python
@dataclass
class SignalWeight:
    trend_5m: float = 0.05
    trend_15m: float = 0.10
    trend_1h: float = 0.20
    oscillator_5m: float = 0.05
    oscillator_15m: float = 0.07
    oscillator_1h: float = 0.08
    prophet: float = 0.15
    sentiment: float = 0.30
```

**Decision Output / निर्णय आउटपुट:**
```python
@dataclass
class VoteResult:
    action: str           # 'long', 'short', 'hold'
    confidence: float     # 0.0 ~ 1.0
    weighted_score: float # -100 ~ +100
    vote_details: Dict
    multi_period_aligned: bool
    reason: str
    regime: Dict
    position: Dict
    trade_params: Dict
```

---

### 2.5 RiskAuditAgent (The Guardian) / रिस्क ऑडिट एजेंट

**File**: `src/agents/risk_audit_agent.py`

```python
class RiskAuditAgent:
    """
    Risk Guardian - Safety enforcement with veto power
    
    Core Functions:
    - Stop-loss direction auto-correction
    - Capital pre-rehearsal
    - One-vote veto power
    - Physical isolation execution
    """
```

**Risk Checks / जोखिम जांच:**
1. **Reverse Position Block**: Prevents opening opposite position
2. **Stop-Loss Correction**: Auto-fixes wrong stop-loss direction
3. **Margin Sufficiency**: Validates available margin
4. **Leverage Check**: Enforces max leverage limits
5. **Position Size Check**: Validates position percentage
6. **Risk Exposure Check**: Total risk calculation

**Risk Levels / जोखिम स्तर:**
```python
class RiskLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    FATAL = "fatal"
```

---

### 2.6 RegimeDetector / रेजीम डिटेक्टर

**File**: `src/agents/regime_detector.py`

```python
class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    CHOPPY = "choppy"
    VOLATILE = "volatile"
    VOLATILE_DIRECTIONLESS = "volatile_directionless"
    UNKNOWN = "unknown"
```

**Detection Logic / डिटेक्शन लॉजिक:**
- **ADX > 25**: Strong trend
- **ADX < 20**: Choppy/Sideways
- **ATR% > 2%**: High volatility
- **TSS (Trend Strength Score)**: Combined metric

---

### 2.7 ReflectionAgent (The Philosopher) / रिफ्लेक्शन एजेंट

**File**: `src/agents/reflection_agent.py`

```python
class ReflectionAgent:
    """
    Trading Philosopher - Analyzes past trades for insights
    
    Triggers every 10 completed trades to provide:
    - Winning patterns
    - Losing patterns
    - Confidence calibration
    - Market insights
    """
```

**Output / आउटपुट:**
```python
@dataclass
class ReflectionResult:
    reflection_id: str
    trades_analyzed: int
    summary: str
    patterns: Dict[str, List[str]]
    recommendations: List[str]
    confidence_calibration: str
    market_insights: str
```

---

## 🧠 3. src/llm/ - LLM Integration / एलएलएम इंटीग्रेशन

### Supported Providers / समर्थित प्रोवाइडर्स:

**File**: `src/llm/factory.py`

```python
PROVIDERS = {
    "openai": OpenAIClient,
    "deepseek": DeepSeekClient,
    "claude": ClaudeClient,
    "qwen": QwenClient,
    "gemini": GeminiClient,
}
```

### LLM Configuration / एलएलएम कॉन्फ़िगरेशन:

```python
@dataclass
class LLMConfig:
    api_key: str
    base_url: Optional[str]
    model: str
    timeout: int = 120
    max_retries: int = 3
    temperature: float = 0.3
    max_tokens: int = 2000
```

---

## 📋 4. src/strategy/ - Strategy Engine / स्ट्रैटेजी इंजन

### StrategyEngine / स्ट्रैटेजी इंजन

**File**: `src/strategy/llm_engine.py`

```python
class StrategyEngine:
    """
    Multi-LLM Strategy Decision Engine
    
    Features:
    - Bull/Bear adversarial analysis
    - Custom prompt support
    - Decision validation
    - Fallback handling
    """
```

**Key Methods / मुख्य मेथड्स:**
- `make_decision()`: Main decision function
- `get_bull_perspective()`: 🐂 Bullish analysis
- `get_bear_perspective()`: 🐻 Bearish analysis
- `_build_system_prompt()`: Builds LLM system prompt
- `_build_user_prompt()`: Builds market context prompt

**Bull/Bear Adversarial System / बुल/बेयर विरोधी सिस्टम:**
```python
# Bull Agent Output
{
    "stance": "STRONGLY_BULLISH",
    "bullish_reasons": "Key bullish observations",
    "bull_confidence": 75
}

# Bear Agent Output
{
    "stance": "STRONGLY_BEARISH",
    "bearish_reasons": "Key bearish observations",
    "bear_confidence": 60
}
```

---

## 🔌 5. src/api/ - Exchange APIs / एक्सचेंज एपीआई

### BinanceClient / बिनेंस क्लाइंट

**File**: `src/api/binance_client.py`

```python
class BinanceClient:
    """
    Binance API Client Wrapper
    
    Features:
    - Spot & Futures support
    - Testnet support
    - Caching for funding rates
    - WebSocket support (optional)
    """
```

**Key Methods / मुख्य मेथड्स:**
- `get_klines()`: Fetch K-line data
- `get_ticker_price()`: Get current price
- `get_futures_account()`: Get futures account info
- `get_futures_position()`: Get position info
- `place_market_order()`: Place market order
- `set_stop_loss_take_profit()`: Set SL/TP orders
- `get_funding_rate()`: Get funding rate
- `get_open_interest()`: Get open interest

---

## 📈 6. src/backtest/ - Backtesting Engine / बैकटेस्टिंग इंजन

### BacktestEngine / बैकटेस्ट इंजन

**File**: `src/backtest/engine.py`

```python
@dataclass
class BacktestConfig:
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = 10000.0
    leverage: int = 1
    stop_loss_pct: float = 1.0
    take_profit_pct: float = 2.0
    slippage: float = 0.001
    commission: float = 0.0004
    step: int = 1  # 1=5min, 3=15min, 12=1hour
    strategy_mode: str = "agent"  # "technical" or "agent"
    use_llm: bool = False
```

**Workflow / वर्कफ्लो:**
1. Load historical data
2. Initialize virtual portfolio
3. Iterate through timestamps
4. Execute strategy decisions
5. Simulate trade execution
6. Record equity and trades
7. Calculate performance metrics
8. Generate report

**Metrics Calculated / गणना की गई मेट्रिक्स:**
- Total Return
- Max Drawdown
- Sharpe Ratio
- Win Rate
- Profit Factor
- Funding Fees
- Slippage Cost

---

## 🌐 7. src/server/ - Web Server / वेब सर्वर

### FastAPI Application / फास्टएपीआई एप्लिकेशन

**File**: `src/server/app.py`

```python
app = FastAPI(title="LLM-TradeBot Dashboard")

# Key Endpoints:
# GET  /api/status      - System status
# POST /api/control     - Start/Stop/Pause
# GET  /api/config      - Get configuration
# POST /api/config      - Update configuration
# POST /api/backtest/run - Run backtest
# GET  /api/accounts    - List accounts
```

**Authentication / प्रमाणीकरण:**
- Session-based authentication
- Admin vs User roles
- Cookie-based sessions

---

## 🖥️ 8. web/ - Frontend Dashboard / फ्रंटएंड डैशबोर्ड

### Main Dashboard / मुख्य डैशबोर्ड

**File**: `web/app.js`

**Features / विशेषताएं:**
- Real-time status updates
- Equity chart (Chart.js)
- Decision history table
- Trade history
- Position management
- Multi-language support (EN/ZH)

**Key Functions / मुख्य फंक्शन्स:**
```javascript
updateDashboard()      // Fetch and render all data
renderSystemStatus()   // System status display
renderMarketData()     // Market data display
renderDecisionTable()  // Decision history
renderTradeHistory()   // Trade history
renderChart()          // Equity curve chart
```

---

## 🔧 9. Configuration Files / कॉन्फ़िगरेशन फाइलें

### config.example.yaml

```yaml
binance:
  api_key: "BINANCE_API_KEY"
  api_secret: "BINANCE_API_SECRET"
  testnet: true

llm:
  provider: deepseek
  model: deepseek-chat
  temperature: 0.3
  max_tokens: 2000

trading:
  symbols: ["BTCUSDT"]
  primary_symbol: "BTCUSDT"
  leverage: 5

risk:
  max_risk_per_trade_pct: 1.5
  max_total_position_pct: 30.0
  max_leverage: 5
  max_consecutive_losses: 3
```

### .env.example

```bash
# Binance API
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# LLM APIs
DEEPSEEK_API_KEY=your_key
OPENAI_API_KEY=your_key
CLAUDE_API_KEY=your_key
QWEN_API_KEY=your_key
GEMINI_API_KEY=your_key

# Web Dashboard
WEB_PASSWORD=admin
```

---

## 🔄 10. Data Flow / डेटा फ्लो

```
┌─────────────────────────────────────────────────────────────────┐
│                         TRADING CYCLE                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. DataSyncAgent.fetch_all_timeframes()                        │
│     - Concurrent fetch: 5m, 15m, 1h K-lines                     │
│     - Returns: MarketSnapshot                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. QuantAnalystAgent.analyze_all_timeframes()                  │
│     - Trend analysis (EMA)                                       │
│     - Oscillator analysis (RSI, KDJ)                            │
│     - Sentiment analysis (Funding, Volume)                       │
│     - Returns: quant_analysis dict                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. PredictAgent.predict()                                       │
│     - Feature extraction                                         │
│     - ML/Rule-based prediction                                   │
│     - Returns: PredictResult (probability_up)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. StrategyEngine.make_decision()                               │
│     - get_bull_perspective() 🐂                                  │
│     - get_bear_perspective() 🐻                                  │
│     - LLM decision with adversarial context                      │
│     - Returns: decision dict                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. RiskAuditAgent.audit_decision()                              │
│     - Regime filter                                              │
│     - Position filter                                            │
│     - Stop-loss validation                                       │
│     - Margin check                                               │
│     - Returns: RiskCheckResult (passed/blocked)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. ExecutionEngine.execute()                                    │
│     - Place orders on Binance                                    │
│     - Set SL/TP                                                  │
│     - Update positions                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. ReflectionAgent.generate_reflection() (every 10 trades)     │
│     - Analyze patterns                                           │
│     - Generate recommendations                                   │
│     - Feed back to StrategyEngine                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 11. Key Algorithms / मुख्य एल्गोरिदम

### Trend Strength Score (TSS)

```python
# Components:
# - ADX (0-100): Weight 40%
# - EMA Alignment: Weight 30%
# - MACD Momentum: Weight 30%

if adx > 25:
    tss += 40
elif adx > 20:
    tss += 20

if trend_direction in ['up', 'down']:
    tss += 30

if macd_aligned:
    tss += 30

# Classification:
# TSS >= 70: Strong Trend
# TSS >= 30: Weak Trend
# TSS < 30: Choppy
```

### Weighted Voting Decision

```python
weighted_score = (
    (trend_5m * 0.05 + trend_15m * 0.10 + trend_1h * 0.20 +
     osc_5m * 0.05 + osc_15m * 0.07 + osc_1h * 0.08 +
     prophet * 0.15) * w_others +
    (sentiment * w_sentiment)
)

# Action Mapping:
# score > threshold + aligned → long/short (high confidence)
# score > threshold → long/short (medium confidence)
# else → hold
```

---

## 🛡️ 12. Safety Features / सुरक्षा विशेषताएं

1. **Stop-Loss Auto-Correction**: Fixes wrong SL direction
2. **Margin Pre-Check**: Validates before order
3. **Veto Power**: RiskAuditAgent can block any trade
4. **Position Limits**: Max position size enforcement
5. **Leverage Limits**: Max leverage enforcement
6. **Duplicate Position Block**: Prevents double entry
7. **Reverse Position Block**: Prevents opposite entry
8. **Demo Mode**: 20-minute limit with default API

---

## 📝 Summary / सारांश

### English:
LLM-TradeBot is a sophisticated multi-agent trading system that combines:
- 12 specialized AI agents working in collaboration
- Multiple LLM providers for intelligent decision making
- Adversarial Bull/Bear analysis for balanced perspectives
- Comprehensive risk management with veto power
- Professional backtesting with detailed metrics
- Real-time web dashboard for monitoring

### Hindi:
LLM-TradeBot एक परिष्कृत मल्टी-एजेंट ट्रेडिंग सिस्टम है जो जोड़ता है:
- 12 विशेष एआई एजेंट्स सहयोग में काम करते हैं
- बुद्धिमान निर्णय लेने के लिए कई एलएलएम प्रोवाइडर्स
- संतुलित दृष्टिकोण के लिए विरोधी बुल/बेयर विश्लेषण
- वीटो पावर के साथ व्यापक जोखिम प्रबंधन
- विस्तृत मेट्रिक्स के साथ पेशेवर बैकटेस्टिंग
- मॉनिटरिंग के लिए रियल-टाइम वेब डैशबोर्ड

---

*Report Generated: January 5, 2026*
*Source: https://github.com/EthanAlgoX/LLM-TradeBot*
