# 🤖 LLM-TradeBot AngelOne Edition

AI-powered trading bot for **Indian Stock Market** using AngelOne SmartAPI. Features 12 AI agents, LLM decision making, and real-time market analysis.

## 🇮🇳 Indian Market Features

- **AngelOne Integration**: Full SmartAPI support with TOTP authentication
- **NSE/BSE/NFO/MCX**: Trade equities, futures, and options
- **Market Hours**: Automatic 9:15 AM - 3:30 PM IST trading window
- **Indian Taxes**: STT, GST, stamp duty calculations in backtesting

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required credentials:
- `ANGELONE_API_KEY` - SmartAPI key from AngelOne
- `ANGELONE_CLIENT_CODE` - Your client ID
- `ANGELONE_PASSWORD` - Your PIN
- `ANGELONE_TOTP_SECRET` - TOTP secret for 2FA
- `DEEPSEEK_API_KEY` - LLM API key (or OpenAI/Claude)

### 3. Run the Bot

```bash
python main.py
```

Web dashboard available at: `http://localhost:8000`

## 📊 Supported Instruments

| Exchange | Type | Example |
|----------|------|---------|
| NSE | Equity | RELIANCE, TCS, INFY |
| BSE | Equity | RELIANCE, TCS |
| NFO | Futures | NIFTY, BANKNIFTY |
| NFO | Options | NIFTY23DEC21000CE |
| MCX | Commodity | GOLD, SILVER |

## 🤖 AI Agents

All 12 original AI agents work unchanged:

1. **DataSyncAgent** - Market data collection
2. **QuantAnalystAgent** - Technical analysis
3. **PredictAgent** - Price prediction
4. **DecisionCoreAgent** - Trade decisions
5. **RiskAuditAgent** - Risk management
6. **RegimeDetector** - Market regime detection
7. **ReflectionAgent** - Performance analysis
8. **BullAgent** - Bullish perspective
9. **BearAgent** - Bearish perspective
10. **DebateAgent** - View synthesis
11. **PortfolioManager** - Portfolio management
12. **ExecutionAgent** - Order execution

## ⚙️ Configuration

Edit `config.example.yaml`:

```yaml
angelone:
  api_key: "${ANGELONE_API_KEY}"
  client_code: "${ANGELONE_CLIENT_CODE}"

trading:
  exchange: "NSE"
  symbols:
    - symbol: "RELIANCE"
      exchange: "NSE"
  product_type: "INTRADAY"

market:
  timezone: "Asia/Kolkata"
  market_open: "09:15"
  market_close: "15:30"
```

## 🧪 Testing

```bash
# Run all AngelOne tests
python -m pytest tests/test_angelone/ -v

# Run specific test
python -m pytest tests/test_angelone/test_integration.py -v
```

## 📁 Project Structure

```
LLM-TradeBot-AngelOne/
├── src/
│   ├── api/
│   │   └── angelone/          # AngelOne integration
│   │       ├── angelone_client.py
│   │       ├── auth_manager.py
│   │       ├── symbol_mapper.py
│   │       ├── market_hours.py
│   │       └── data_converter.py
│   ├── agents/                # 12 AI agents (unchanged)
│   ├── llm/                   # LLM integrations
│   └── strategy/              # Trading strategies
├── web/                       # Dashboard UI
├── tests/                     # Test suite
├── config.example.yaml        # Configuration template
└── main.py                    # Entry point
```

## ⚠️ Disclaimer

This software is for educational purposes only. Trading involves risk. Use at your own risk.

## 📄 License

MIT License
