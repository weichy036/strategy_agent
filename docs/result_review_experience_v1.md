# Result Review Experience V1

## 背景

BigQuant 的回测结果页把策略运行后的信息拆成几个清晰入口：

- 策略代码
- 收益概况
- 交易详情
- 持仓详情
- 运行日志

这类结构很适合专业复盘：用户不仅看收益曲线，还能追溯“为什么有这个收益”“每期选了哪些股票”“实际买卖了什么”“运行过程中发生了什么”。

TradeX 的定位不同：用户通过自然语言提出策略，Agent 负责补全、执行、解释。因此结果页不能变成很重的专业控制台，但需要吸收 BigQuant 的复盘结构，让普通投资者看得懂、查得到、能追问。

## 设计目标

1. 让用户知道策略结果来自哪些动作，而不是只看到收益率。
2. 让对话结果保持简洁，细节通过 tab 和 artifact 展开。
3. 让选股、交易、持仓、日志都可追溯。
4. 结果页与 ADK artifact / session state 对齐，后续支持继续追问、导出、复跑。
5. 不把 TradeX 做成传统量化 IDE，保持“自然语言 + 研究报告”的产品气质。

## 信息架构

每次回测完成后，Assistant 消息下方生成一个 `BacktestResultCard`。

默认展示 `概况`，用户可以切换：

- `概况`：核心指标、收益曲线、风险提示。
- `选股`：每次调仓选出的股票，展示最近几期，完整明细进 artifact。
- `交易`：实际成交记录，包括买卖方向、数量、价格、成交金额。
- `持仓`：每日或每次调仓后的持仓快照。
- `日志`：Agent 执行路径、数据检查、回测假设、异常或警告。

第一版先做前三个 tab：

- `概况`
- `选股`
- `交易`

`持仓` 和 `日志` 可以在 V2 继续补。

## 页面结构

```text
用户问题气泡

Agent 简短结论
Agent · completed

[概况] [选股] [交易] [持仓] [日志]

概况 Tab:
  - 策略名称
  - 指标：累计收益 / 年化收益 / 最大回撤 / 夏普 / 胜率 / 交易次数
  - 收益曲线 artifact
  - 结果解释和风险提示

选股 Tab:
  - 最近调仓选股列表
  - 每行：调仓日期 + 股票 chips
  - 完整明细 artifact 链接

交易 Tab:
  - 最近交易记录表
  - 列：日期 / 股票 / 方向 / 数量 / 成交价 / 成交金额
  - 完整交易日志 artifact 链接
```

## 数据结构

`result_page` 保持作为前端唯一消费入口。

```json
{
  "summary": {
    "strategy_name": "成交额 TOP10 月度轮动策略",
    "summary_text": "回测完成，年化收益约 ...",
    "risk_text": "..."
  },
  "metric_cards": {},
  "equity_curve": {
    "series": [],
    "artifact": {}
  },
  "drawdown_curve": {
    "series": []
  },
  "trade_stats": {
    "trade_log_size": 120,
    "position_log_size": 750,
    "selection_snapshots": [],
    "selection_artifact": {},
    "trade_snapshots": [],
    "trade_artifact": {},
    "position_snapshots": [],
    "position_artifact": {}
  },
  "risk_disclosures": []
}
```

## Artifact 设计

页面只展示摘要，完整数据都进入 artifact。

| Artifact | 内容 | 格式 | 用途 |
|---|---|---|---|
| `equity_curve` | 收益曲线图 | `svg` | 页面展示 |
| `selection_log` | 每次调仓选股结果 | `json` | 选股复盘 |
| `trade_log` | 每笔买卖成交 | `json` | 交易复盘 |
| `position_log` | 每日或调仓后持仓 | `json` | 持仓复盘 |
| `backtest_result` | 完整回测结果 | `json` | 后续继续追问 / 复跑 |

第一版已经有：

- `equity_curve.svg`
- `selection_log.json`

下一步补：

- `trade_log.json`
- `position_log.json`
- 可选的 `backtest_result.json`

## Tab 行为

### 概况

默认打开。

展示内容：

- 策略名称和一句话结论。
- 指标卡片。
- 收益曲线。
- 风险提示。

指标建议：

- 累计收益
- 年化收益
- 最大回撤
- 夏普比率
- 胜率
- 交易次数
- 基准收益
- 相对收益

第一版可先展示已有指标，不强行补全所有指标。

### 选股

适用于轮动、选股策略。

展示内容：

- 最近 6 次调仓。
- 每次最多展示 20 只股票。
- 右上角提供 `完整明细` 链接。

如果不是选股策略，则 tab 隐藏。

### 交易

适用于所有有交易日志的策略。

展示内容：

- 最近 20 条交易。
- 买入用红色，卖出用灰黑色或绿色，避免过度刺激。
- 提供 `完整交易日志` artifact 链接。

表格列：

- 日期
- 股票
- 方向
- 数量
- 成交价
- 成交金额

如果当前日志没有股票名称，先展示代码；后续可接入基础信息表补名称。

### 持仓

V2 实现。

展示内容：

- 最近调仓后的持仓。
- 持仓数量、权重、现金比例。
- 完整持仓 artifact。

### 日志

V2 实现。

展示内容：

- 当前 run 的简化 trace。
- 数据检查结果。
- 回测假设。
- 警告和异常。

工程态完整 trace 仍保留在顶部 `Trace` 页面。

## UX 原则

1. 对话内结果卡片只展示用户最关心的内容。
2. 细节不要常驻铺满页面，通过 tab 逐层展开。
3. artifact 链接用轻量文字，不做很重的下载按钮。
4. 专业信息要保留，但表达要面向普通投资者。
5. 如果策略不可回测或数据缺失，不展示空 tab。

## 实现顺序

### Step 1：结果卡片 tab 框架

- 在 `turn_result_view.js` 中为 completed result 增加 tab 容器。
- 默认 tab 为 `概况`。
- `选股` tab 使用现有 `selection_snapshots`。
- 保持无 JS 框架、无复杂状态。

### Step 2：交易日志 artifact

- 在 `report_assembly.py` 中持久化 `trade_log.json`。
- 增加 `trade_snapshots`，展示最近 20 条。
- 前端增加 `交易` tab。

### Step 3：持仓日志 artifact

- 持久化 `position_log.json`。
- 增加 `position_snapshots`。
- 前端增加 `持仓` tab。

### Step 4：更丰富收益概况

- 增加胜率、基准收益、相对收益。
- 收益曲线支持策略收益 / 基准收益 / 相对收益。
- 当前先不做复杂 tooltip，避免拖慢 MVP。

### Step 5：日志 tab

- 复用 `observability.spans`。
- 展示简化版 run steps。
- 完整调试仍跳转顶部 `Trace`。

## 第一版验收标准

1. MACD 单标的策略只展示 `概况` 和 `交易`。
2. 月度选股轮动策略展示 `概况`、`选股`、`交易`。
3. `选股` tab 有最近调仓列表和完整明细 artifact 链接。
4. `交易` tab 有最近交易表和完整交易 artifact 链接。
5. 结果页面仍保持简洁，不出现大面积空白或信息堆叠。
6. 所有 artifact 链接可打开。

## 关键决策

- `Trace` 页面定位工程观测，不替代结果复盘。
- 对话结果卡片定位用户复盘，不展示完整原始日志。
- Artifact 是连接二者的桥：页面看摘要，artifact 看完整数据。
- 第一版不做代码展示 tab，避免把产品推向量化 IDE。

