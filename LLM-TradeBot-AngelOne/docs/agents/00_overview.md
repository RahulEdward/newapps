# 🤖 Multi-Agent Trading Framework

> LLM-TradeBot 多 Agent 协作架构概览

## 架构概览

LLM-TradeBot 采用 5 个专业化 Agent 的协作架构，各司其职，形成完整的交易决策流水线。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         交易决策流水线                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐          │
│  │   🕵️ Data     │      │   👨‍🔬 Quant   │      │   🔮 Predict  │          │
│  │  SyncAgent   │─────▶│ AnalystAgent │─────▶│    Agent     │          │
│  │ (The Oracle) │      │(The Strategist)│    │(The Prophet) │          │
│  └──────────────┘      └──────────────┘      └──────────────┘          │
│         │                      │                     │                  │
│         │                      └──────────┬──────────┘                  │
│         │                                 ▼                             │
│         │                      ┌──────────────┐                         │
│         │                      │  ⚖️ Decision  │                         │
│         │                      │  CoreAgent   │                         │
│         │                      │ (The Critic) │                         │
│         │                      └──────────────┘                         │
│         │                                 │                             │
│         │                                 ▼                             │
│         │                      ┌──────────────┐                         │
│         │                      │  🛡️ RiskAudit │                         │
│         └─────────────────────▶│    Agent     │                         │
│              (market_data)     │(The Guardian)│                         │
│                                └──────────────┘                         │
│                                        │                                │
│                                        ▼                                │
│                                ┌──────────────┐                         │
│                                │  🚀 Executor  │                         │
│                                │   Engine     │                         │
│                                └──────────────┘                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Agent 概览

| Agent | 别名 | 职责 | 输入 | 输出 |
|-------|------|------|------|------|
| [DataSyncAgent](01_data_sync_agent.md) | The Oracle | 数据采集 | symbol, limit | MarketSnapshot |
| [QuantAnalystAgent](02_quant_analyst_agent.md) | The Strategist | 信号分析 | MarketSnapshot | quant_analysis |
| [PredictAgent](03_predict_agent.md) | The Prophet | ML 预测 | features | PredictResult |
| [DecisionCoreAgent](04_decision_core_agent.md) | The Critic | 决策融合 | quant_analysis, predict_result | VoteResult |
| [RiskAuditAgent](05_risk_audit_agent.md) | The Guardian | 风控审计 | decision, position, balance | RiskCheckResult |

## 数据流详解

### Step 1: 数据采集 (DataSyncAgent)

```python
snapshot = await data_sync_agent.fetch_all_timeframes("BTCUSDT")
```

- 并发获取 5m/15m/1h K 线数据
- 获取资金费率、OI、机构资金流
- 构建双视图：stable (已完成) + live (当前)

### Step 2: 量化分析 (QuantAnalystAgent)

```python
quant_analysis = await quant_analyst_agent.analyze_all_timeframes(snapshot)
```

- 趋势分析：EMA 金叉/死叉，MACD 动量
- 震荡分析：多周期 RSI
- 情绪分析：资金流、资金费率、OI 变化

### Step 2.5: ML 预测 (PredictAgent)

```python
predict_result = await predict_agent.predict(features)
```

- 特征工程：80+ 技术特征
- LightGBM 模型预测 30 分钟上涨概率
- 自动回退到规则评分

### Step 3: 决策融合 (DecisionCoreAgent)

```python
vote_result = await decision_core_agent.make_decision(
    quant_analysis, predict_result, market_data
)
```

- 加权投票：整合 8 个信号维度
- 多周期对齐检测
- 对抗式审计：信号与资金流背离

### Step 4: 风控审计 (RiskAuditAgent)

```python
risk_result = await risk_audit_agent.audit_decision(
    decision, current_position, account_balance, current_price
)
```

- 止损方向自动修正
- 仓位/杠杆/保证金检查
- 一票否决权

### Step 5: 执行 (ExecutorEngine)

```python
if risk_result.passed:
    await executor.execute(decision)
```

## 配置文件

### config.yaml

```yaml
trading:
  symbols:
    - BTCUSDT
    - ETHUSDT
    - SOLUSDT
    - BNBUSDT
  primary_symbol: BTCUSDT
  max_trade_amount: 100
  leverage: 1
  stop_loss_pct: 0.01
  take_profit_pct: 0.02
  test_mode: true
```

## 日志输出示例

```
🔄 Cycle #1 | 分析 4 个交易对
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 [BTCUSDT] 开始分析...
🕵️ DataSyncAgent (The Oracle): Action=Fetch[5m,15m,1h] | Snapshot=$96000.00
👨‍🔬 QuantAnalystAgent (The Strategist): Trend(上涨,20) | Osc(RSI:55,0) | Sent(OI:0.5%,10) => Score: 12/100
🔮 PredictAgent (The Prophet): 📈 P(Up)=56.5% | Signal: bullish | Conf: 65%
⚖️ DecisionCoreAgent (The Critic): Context(Regime=trending, Pos=45%) => Vote: WAIT
🛡️ RiskAuditAgent (The Guardian): Result: ✅ PASSED (Risk: safe)
```

## 扩展性

### 添加新 Agent

1. 创建 Agent 类文件 `src/agents/new_agent.py`
2. 定义输入/输出数据结构
3. 在 `main.py` 中初始化并集成到流水线
4. 添加 Dashboard 日志输出

### 信号权重调优

修改 `DecisionCoreAgent.SignalWeight` 配置：

```python
SignalWeight(
    trend_1h=0.25,   # 增加 1h 趋势权重
    prophet=0.20,    # 增加 ML 预测权重
    sentiment=0.15   # 降低情绪权重
)
```

## 相关文档

- [DataSyncAgent 详解](01_data_sync_agent.md)
- [QuantAnalystAgent 详解](02_quant_analyst_agent.md)
- [PredictAgent 详解](03_predict_agent.md)
- [DecisionCoreAgent 详解](04_decision_core_agent.md)
- [RiskAuditAgent 详解](05_risk_audit_agent.md)
