# Tool Contracts V1

## 1. 文档目标

这份文档用于定义第一版系统中核心 Tool 的输入输出契约。

它回答的问题是：

- 每个 Tool 接收什么输入
- 每个 Tool 返回什么输出
- 哪些字段是必填
- 错误时应该返回什么结构
- 这些结果如何进入 Session State 和 Artifact

这份文档的目标是把前面的架构设计收敛成“可实现接口”，避免后续一边写代码一边重新发明数据结构。

## 2. 为什么要先定义 Tool Contract

当前我们已经有：

- 用户流程
- Strategy Schema
- 澄清规则
- 回测假设
- 结果页规则
- ADK 系统架构
- Agent 拓扑
- 数据访问架构

但如果 Tool 的输入输出不固定，后面依然会出现问题：

- Agent 不知道该如何稳定调用 Tool
- State 里存什么会反复变化
- Artifact 的格式无法统一
- 不同 Tool 之间难以组合

因此在编码前，把 Tool Contract 定下来非常关键。

## 3. 第一版设计原则

第一版 Tool Contract 建议遵守以下原则。

### 原则 1：输入输出优先结构化

尽量返回结构化对象，而不是长段自然语言。

### 原则 2：错误结构统一

每个 Tool 在失败时应使用统一错误格式。

### 原则 3：输出要适合进入 State / Artifact

Tool 的返回结果不只是给当前调用方看，还要能被持久化和复用。

### 原则 4：Tool 负责确定性结果，不负责开放式表达

解释类工作交给 Agent，确定性结构交给 Tool。

## 4. 第一版核心 Tool 清单

第一版建议正式定义以下 Tool 契约：

1. `InstrumentResolveTool`
2. `StrategyValidationTool`
3. `ClarificationDecisionTool`
4. `MarketDataQueryTool`
5. `BacktestRunTool`
6. `MetricsComputeTool`
7. `ArtifactStoreTool`
8. `ReportAssemblyTool`

## 5. 统一返回包装格式

第一版建议所有 Tool 都使用统一包装结构。

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {}
}
```

### 字段说明

- `ok`
  表示调用是否成功

- `data`
  成功时的结构化返回体

- `error`
  失败时的错误对象

- `meta`
  补充信息，例如耗时、默认值、数据来源等

## 6. 统一错误结构

第一版建议错误对象统一为：

```json
{
  "code": "instrument_not_found",
  "message": "无法唯一识别标的",
  "details": {
    "query": "平安银行"
  }
}
```

### 第一版常见错误码建议

- `instrument_not_found`
- `instrument_ambiguous`
- `strategy_schema_invalid`
- `strategy_schema_incomplete`
- `clarification_required`
- `market_data_not_found`
- `backtest_execution_failed`
- `metrics_compute_failed`
- `artifact_store_failed`
- `report_assembly_failed`

## 7. `InstrumentResolveTool`

## 7.1 作用

把自然语言标的描述解析成标准证券代码或候选列表。

## 7.2 输入契约

```json
{
  "query": "沪深300ETF",
  "allowed_asset_types": ["stock", "etf", "index", "fund"],
  "market": "CN"
}
```

### 输入字段

- `query`: 必填，用户提供的标的描述
- `allowed_asset_types`: 选填，允许的资产类型范围
- `market`: 选填，默认 `CN`

## 7.3 输出契约

```json
{
  "ok": true,
  "data": {
    "resolved": true,
    "is_ambiguous": false,
    "instrument": {
      "ts_code": "510300.SH",
      "name": "沪深300ETF",
      "asset_type": "etf",
      "market": "CN_A"
    },
    "candidates": []
  },
  "error": null,
  "meta": {
    "query": "沪深300ETF"
  }
}
```

### 失败场景

如果无法唯一识别：

```json
{
  "ok": false,
  "data": {
    "resolved": false,
    "is_ambiguous": true,
    "instrument": null,
    "candidates": [
      { "ts_code": "000001.SZ", "name": "平安银行", "asset_type": "stock" }
    ]
  },
  "error": {
    "code": "instrument_ambiguous",
    "message": "标的存在歧义，需要用户确认",
    "details": {
      "query": "平安"
    }
  },
  "meta": {}
}
```

## 8. `StrategyValidationTool`

## 8.1 作用

校验 `Strategy Schema V1` 的完整性和合法性。

## 8.2 输入契约

```json
{
  "strategy_schema": {}
}
```

## 8.3 输出契约

```json
{
  "ok": true,
  "data": {
    "is_valid": true,
    "is_complete": false,
    "missing_fields": ["signals.sell"],
    "invalid_fields": [],
    "warnings": []
  },
  "error": null,
  "meta": {
    "schema_version": "v1"
  }
}
```

### 字段说明

- `is_valid`
  字段结构是否符合 Schema

- `is_complete`
  是否已经具备执行条件

- `missing_fields`
  缺失但需要补齐的字段

- `invalid_fields`
  非法字段或非法值

- `warnings`
  不阻断执行的提醒项

## 9. `ClarificationDecisionTool`

## 9.1 作用

根据澄清规则，把缺失字段分成：

- 必须追问
- 可默认补全
- 可直接执行

## 9.2 输入契约

```json
{
  "strategy_draft": {},
  "validation_result": {
    "missing_fields": ["signals.sell", "period.start", "period.end"]
  },
  "context": {
    "user_query": "MACD 金叉买入效果怎么样？"
  }
}
```

## 9.3 输出契约

```json
{
  "ok": true,
  "data": {
    "must_ask_fields": ["signals.sell"],
    "defaultable_fields": ["period.start", "period.end"],
    "ready_to_execute": false,
    "next_question": "我还缺一个关键条件：你的卖出规则是什么？"
  },
  "error": null,
  "meta": {}
}
```

### 说明

- `next_question` 是为顶层 Agent 提供的候选澄清问题
- 是否直接原样发给用户，仍由 Agent 决定

## 10. `MarketDataQueryTool`

## 10.1 作用

以统一方式读取价格、截面、基准和交易日历数据。

## 10.2 输入契约

```json
{
  "query_type": "bar_frame",
  "instrument": "510300.SH",
  "price_mode": "raw",
  "start_date": "2018-01-01",
  "end_date": "2025-12-31"
}
```

### 第一版 `query_type` 建议值

- `bar_frame`
- `daily_basic_frame`
- `daily_basic_by_instrument`
- `benchmark_frame`
- `latest_trade_date`
- `trading_calendar`

## 10.3 输出契约

考虑到 DataFrame 不适合直接在所有 Tool 间裸传，第一版建议逻辑上输出标准化表对象引用或 records 结构。

建议抽象成：

```json
{
  "ok": true,
  "data": {
    "query_type": "bar_frame",
    "row_count": 484,
    "columns": ["ts_code", "trade_date", "open", "high", "low", "close"],
    "records": []
  },
  "error": null,
  "meta": {
    "source": "data/raw/fund_daily/510300.SH.parquet"
  }
}
```

### 工程实现建议

实现时内部当然可以直接返回 DataFrame 给 Python 调用栈；
但在文档契约层，建议把它理解为“标准化表结果”，便于未来跨边界复用。

## 11. `BacktestRunTool`

## 11.1 作用

接收完整策略对象，运行回测并返回标准化结果。

## 11.2 输入契约

```json
{
  "strategy_schema": {},
  "execution_options": {
    "persist_artifacts": true,
    "include_trade_log": true,
    "include_position_log": true
  }
}
```

### 必填输入

- `strategy_schema`

### 选填输入

- `execution_options.persist_artifacts`
- `execution_options.include_trade_log`
- `execution_options.include_position_log`

## 11.3 输出契约

```json
{
  "ok": true,
  "data": {
    "run_id": "bt_20260422_001",
    "strategy_id": "stg_macd_510300_v1",
    "date_range": {
      "start": "2018-01-01",
      "end": "2025-12-31"
    },
    "equity_curve": [],
    "drawdown_curve": [],
    "trade_log": [],
    "position_log": [],
    "summary": {
      "final_nav": 1.82,
      "total_return": 0.82,
      "benchmark_return": 0.56
    }
  },
  "error": null,
  "meta": {
    "assumptions_version": "v1"
  }
}
```

### 输出字段说明

- `run_id`
  本次回测唯一标识

- `equity_curve`
  回测收益曲线或净值曲线底层数据

- `drawdown_curve`
  回撤曲线底层数据

- `trade_log`
  交易记录

- `position_log`
  持仓记录

- `summary`
  基础回测摘要

## 12. `MetricsComputeTool`

## 12.1 作用

从回测结果中计算结果页必须展示的指标。

## 12.2 输入契约

```json
{
  "backtest_result": {},
  "metrics_profile": "default_v1"
}
```

## 12.3 输出契约

```json
{
  "ok": true,
  "data": {
    "return_metrics": {
      "total_return": 0.82,
      "annualized_return": 0.091,
      "average_yearly_return": 0.087
    },
    "risk_metrics": {
      "max_drawdown": 0.21,
      "sharpe": 1.03,
      "volatility": 0.18
    },
    "trading_metrics": {
      "trade_count": 34,
      "win_rate": 0.53,
      "avg_holding_days": 18,
      "turnover": 1.24
    },
    "period_breakdown": {
      "yearly_returns": []
    }
  },
  "error": null,
  "meta": {
    "metrics_profile": "default_v1"
  }
}
```

## 13. `ArtifactStoreTool`

## 13.1 作用

将策略、结果、图表或报告保存到 Artifact 层。

## 13.2 输入契约

```json
{
  "artifact_type": "strategy_schema",
  "name": "strategy_schema.json",
  "content": {},
  "content_type": "application/json",
  "session_id": "session_xxx"
}
```

### 第一版 `artifact_type` 建议值

- `strategy_draft`
- `strategy_card`
- `strategy_schema`
- `backtest_result`
- `equity_curve`
- `drawdown_curve`
- `report`

## 13.3 输出契约

```json
{
  "ok": true,
  "data": {
    "artifact_id": "artifact_strategy_schema_001",
    "artifact_type": "strategy_schema",
    "name": "strategy_schema.json",
    "uri": "artifact://session_xxx/strategy_schema.json"
  },
  "error": null,
  "meta": {}
}
```

## 14. `ReportAssemblyTool`

## 14.1 作用

把结果页需要的所有元素整合为一个最终响应对象。

## 14.2 输入契约

```json
{
  "strategy_schema": {},
  "backtest_result": {},
  "metrics": {},
  "explanations": {
    "summary_text": "",
    "risk_text": "",
    "limitations_text": ""
  }
}
```

## 14.3 输出契约

```json
{
  "ok": true,
  "data": {
    "result_page": {
      "summary": {},
      "metric_cards": {},
      "equity_curve": {},
      "drawdown_curve": {},
      "trade_stats": {},
      "risk_disclosures": []
    }
  },
  "error": null,
  "meta": {
    "result_schema_version": "v1"
  }
}
```

### 关键约束

这里必须保证：

- `equity_curve` 一定存在

因为结果页规范已经明确：

- 回测收益曲线是必需项

## 15. Tool 与 Session State 的关系

第一版建议把部分 Tool 输出直接映射到 State。

### `StrategyParsingAgent` 之后

- `strategy_draft`
- `problem_type`

### `StrategyValidationTool` 之后

- `missing_fields`
- `invalid_fields`

### `ClarificationDecisionTool` 之后

- `must_ask_fields`
- `defaultable_fields`
- `clarification_needed`

### `BacktestRunTool` 之后

- `backtest_status`
- `backtest_result_ref`

### `MetricsComputeTool` 之后

- `metrics_summary`

## 16. Tool 与 Artifact 的关系

第一版建议下列对象优先入 Artifact。

### 建议持久化

- `strategy_schema`
- `backtest_result`
- `equity_curve`
- `drawdown_curve`
- `report`

### 可选持久化

- `strategy_draft`
- `validation_result`
- `clarification_trace`

## 17. Tool 链路组合建议

第一版主链路中，推荐如下组合方式：

1. `InstrumentResolveTool`
2. `StrategyValidationTool`
3. `ClarificationDecisionTool`
4. `BacktestRunTool`
5. `MetricsComputeTool`
6. `ArtifactStoreTool`
7. `ReportAssemblyTool`

这条组合链应由 `ResearchOrchestratorAgent` 编排。

## 18. 一个完整示例链路

下面是一条简化的数据流示例：

```text
User Query
  -> StrategyParsingAgent
  -> StrategyValidationTool
  -> ClarificationDecisionTool
  -> Strategy Schema
  -> BacktestRunTool
  -> MetricsComputeTool
  -> ResultExplanationAgent
  -> ReportAssemblyTool
  -> Final Result Page
```

## 19. 第一版边界控制

第一版 Tool Contract 先不追求非常复杂的通用协议。

第一版建议：

- 输入字段尽量少而稳定
- 输出结构尽量清晰
- 把复杂度留给后续版本扩展

第一版暂不建议：

- 在 Tool 输出里混大量模型提示词痕迹
- 混入过多“半结构化自然语言”
- 同一个 Tool 负责太多不相关功能

## 20. 下一步建议

基于这份文档，下一步最适合继续写的是：

1. `adk_state_and_artifacts_v1.md`
2. `implementation_roadmap_v1.md`

因为现在我们已经把 Tool 契约定下来了，接下来最应该固定的是：

- Session State 字段结构
- Artifact 命名与生命周期
- 实现阶段的分步落地路线
