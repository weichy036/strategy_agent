# ADK State 与 Artifacts V1

## 1. 文档目标

这份文档用于定义第一版系统在 Google ADK 中如何使用：

- `Session`
- `State`
- `Artifacts`

它回答的问题是：

- Session State 到底存哪些字段
- 各阶段状态如何流转
- Artifact 应保存哪些对象
- Artifact 如何命名、更新和引用
- 多轮研究如何基于 State 与 Artifact 恢复上下文

这份文档的目标是把前面的架构、Agent 拓扑和 Tool 契约真正落到 ADK 的状态与产物管理上。

## 2. 为什么这一步很关键

如果没有明确的 State 与 Artifact 设计，系统很容易出现以下问题：

- 多轮对话时丢失研究上下文
- 澄清做到一半无法恢复
- Strategy Schema 生成了但没有稳定保存
- 回测收益曲线生成了但无法可靠复用
- 结果页只能依赖临时内存对象，不能沉淀为研究资产

而我们的产品目标恰恰不是一次性问答，而是一个“研究工作台”。

所以第一版必须把：

- 状态如何保存
- 产物如何沉淀

设计清楚。

## 3. 第一版设计原则

### 原则 1：State 存“当前会话运行状态”

State 更适合保存：

- 当前问题
- 当前策略草案
- 当前缺失字段
- 当前回测状态

也就是“当前流程执行到哪一步了”。

### 原则 2：Artifact 存“可复用研究资产”

Artifact 更适合保存：

- 策略卡
- Strategy Schema
- 回测结果
- 收益曲线
- 报告

也就是“这个会话产出了什么可以被复用的对象”。

### 原则 3：State 应轻量、结构化、可恢复

不要把大块原始表格、整份报告文本、完整交易日志都塞进 State。

State 里更适合放：

- 摘要
- 标识
- 引用
- 当前控制信息

### 原则 4：Artifact 应可追踪、可版本化

至少在第一版命名层面，就要让人能看出：

- 这个 Artifact 属于哪个 Session
- 属于哪个策略
- 属于哪个回测运行

### 原则 5：多轮研究优先恢复状态，而不是重新推理一切

当用户问：

- “如果改成季度调仓呢？”

系统应优先从已有 State 和 Artifact 恢复上一个研究对象，而不是重新从聊天记录猜测。

## 4. State 与 Artifact 的分工

第一版建议明确分工如下。

## 4.1 State 负责

- 当前用户问题
- 当前问题类型
- 当前策略草案
- 当前缺失字段
- 当前默认补全字段
- 当前是否需要澄清
- 当前回测是否完成
- 当前结果摘要
- 当前 Artifact 引用

## 4.2 Artifact 负责

- 策略草案快照
- 策略卡
- 最终 Strategy Schema
- 回测原始结果
- 收益曲线
- 回撤曲线
- 结果摘要报告

## 5. Session State 顶层结构建议

第一版建议 Session State 采用统一结构：

```json
{
  "workflow_version": "v1",
  "current_query": "",
  "problem_type": null,
  "stage": "intake",
  "clarification": {},
  "strategy": {},
  "backtest": {},
  "result": {},
  "artifacts": {},
  "context": {}
}
```

## 6. State 字段设计

## 6.1 `workflow_version`

作用：

- 标识当前状态结构版本

建议值：

- `v1`

## 6.2 `current_query`

作用：

- 当前用户这轮研究问题的原始表达

示例：

```json
{
  "current_query": "如果每个月买入市值最大的20只股票，持有到下个月，收益是多少？"
}
```

## 6.3 `problem_type`

作用：

- 记录当前识别出的策略问题类型

建议值：

- `signal_trading`
- `cross_sectional_rotation`
- `screen_and_hold`
- `rule_based_timing`

## 6.4 `stage`

作用：

- 表示当前会话运行阶段

第一版建议值：

- `intake`
- `parsing`
- `clarifying`
- `schema_ready`
- `running_backtest`
- `computing_metrics`
- `explaining`
- `assembled`
- `completed`
- `failed`

这个字段非常重要，因为它能帮助系统恢复“流程跑到哪里了”。

## 6.5 `clarification`

作用：

- 保存澄清流程当前状态

建议结构：

```json
{
  "needed": true,
  "must_ask_fields": [],
  "defaultable_fields": [],
  "asked_questions": [],
  "resolved_fields": [],
  "defaulted_fields": []
}
```

### 字段说明

- `needed`
  当前是否还需要澄清

- `must_ask_fields`
  当前必须追问字段

- `defaultable_fields`
  当前可默认补全字段

- `asked_questions`
  已经问过的问题列表

- `resolved_fields`
  已经通过用户回答解决的字段

- `defaulted_fields`
  已由系统补默认值的字段

## 6.6 `strategy`

作用：

- 保存当前策略对象相关状态

建议结构：

```json
{
  "draft": {},
  "card": {},
  "schema": {},
  "strategy_id": null,
  "is_ready": false
}
```

### 字段说明

- `draft`
  解析 Agent 当前输出的草案

- `card`
  面向用户展示的策略卡对象

- `schema`
  最终可执行 Strategy Schema

- `strategy_id`
  当前策略的系统标识

- `is_ready`
  是否已达到可执行状态

## 6.7 `backtest`

作用：

- 保存回测执行状态

建议结构：

```json
{
  "status": "idle",
  "run_id": null,
  "date_range": null,
  "summary": null,
  "metrics_ready": false
}
```

### 第一版 `status` 建议值

- `idle`
- `queued`
- `running`
- `completed`
- `failed`

## 6.8 `result`

作用：

- 保存结果页摘要级状态

建议结构：

```json
{
  "summary_text": null,
  "risk_text": null,
  "limitations_text": null,
  "result_page_ready": false
}
```

说明：

- 这里放摘要级解释
- 完整结果页对象可以放 Artifact，也可以在必要时保留引用

## 6.9 `artifacts`

作用：

- 保存当前会话已生成 Artifact 的引用

建议结构：

```json
{
  "strategy_draft": null,
  "strategy_card": null,
  "strategy_schema": null,
  "backtest_result": null,
  "equity_curve": null,
  "drawdown_curve": null,
  "report": null
}
```

这里存的是引用信息，而不是 Artifact 全量内容。

## 6.10 `context`

作用：

- 保存会话级额外上下文

建议内容：

- 当前使用的默认假设版本
- 当前使用的指标配置版本
- 相关基准信息
- 相关用户偏好快照

## 7. 第一版推荐完整 State 示例

```json
{
  "workflow_version": "v1",
  "current_query": "对于沪深300ETF，MACD 日线金叉买入、死叉卖出，每年的平均收益是多少？",
  "problem_type": "signal_trading",
  "stage": "schema_ready",
  "clarification": {
    "needed": false,
    "must_ask_fields": [],
    "defaultable_fields": ["period.start", "period.end", "costs.commission_bps", "costs.slippage_bps"],
    "asked_questions": [],
    "resolved_fields": [],
    "defaulted_fields": ["period.start", "period.end", "costs.commission_bps", "costs.slippage_bps"]
  },
  "strategy": {
    "draft": {},
    "card": {},
    "schema": {},
    "strategy_id": "stg_macd_510300_v1",
    "is_ready": true
  },
  "backtest": {
    "status": "idle",
    "run_id": null,
    "date_range": {
      "start": "2018-01-01",
      "end": "2025-12-31"
    },
    "summary": null,
    "metrics_ready": false
  },
  "result": {
    "summary_text": null,
    "risk_text": null,
    "limitations_text": null,
    "result_page_ready": false
  },
  "artifacts": {
    "strategy_draft": null,
    "strategy_card": "artifact://session_xxx/strategy_card.json",
    "strategy_schema": "artifact://session_xxx/strategy_schema.json",
    "backtest_result": null,
    "equity_curve": null,
    "drawdown_curve": null,
    "report": null
  },
  "context": {
    "backtest_assumptions_version": "v1",
    "metrics_profile": "default_v1"
  }
}
```

## 8. State 生命周期

第一版建议把 State 生命周期明确成以下阶段。

## 8.1 初始化阶段

触发条件：

- 用户首次提问

主要动作：

- 创建 Session
- 初始化 State
- 写入 `current_query`
- `stage = intake`

## 8.2 解析阶段

触发条件：

- 进入 `StrategyParsingAgent`

主要动作：

- 更新 `problem_type`
- 写入 `strategy.draft`
- 更新 `stage = parsing`

## 8.3 澄清阶段

触发条件：

- Validation / Clarification Tool 发现必须追问字段

主要动作：

- 更新 `clarification.*`
- 更新 `stage = clarifying`

## 8.4 Strategy Schema 固化阶段

触发条件：

- 所有必需字段已经齐全

主要动作：

- 写入 `strategy.schema`
- `strategy.is_ready = true`
- 更新 `stage = schema_ready`

## 8.5 回测执行阶段

触发条件：

- 调用 `BacktestRunTool`

主要动作：

- `backtest.status = running`
- `stage = running_backtest`

## 8.6 指标计算与解释阶段

触发条件：

- 回测完成

主要动作：

- 写入 `backtest.summary`
- 更新 `result.*`
- `stage = computing_metrics` / `explaining`

## 8.7 结果组装完成阶段

触发条件：

- `ReportAssemblyTool` 完成

主要动作：

- `result.result_page_ready = true`
- `stage = completed`

## 9. Artifact 设计目标

第一版 Artifact 需要做到三件事：

1. 可恢复
2. 可复用
3. 可展示

也就是说，Artifact 不是日志文件堆放区，而是研究资产仓库。

## 10. 第一版 Artifact 清单

第一版建议正式定义以下 Artifact 类型。

## 10.1 `strategy_draft`

作用：

- 保存解析阶段的结构化草案

建议格式：

- JSON

## 10.2 `strategy_card`

作用：

- 保存面向用户展示的策略卡对象

建议格式：

- JSON

## 10.3 `strategy_schema`

作用：

- 保存最终可执行 Strategy Schema

建议格式：

- JSON

这是第一版最关键的 Artifact 之一。

## 10.4 `backtest_result`

作用：

- 保存回测原始输出结果

建议格式：

- JSON

内容可包含：

- summary
- equity_curve
- drawdown_curve
- trade_log
- position_log

## 10.5 `equity_curve`

作用：

- 保存回测收益曲线数据或可视化产物

建议格式：

- JSON 数据对象
- 或 PNG / SVG 图像

第一版建议优先保存结构化曲线数据，再视需要生成图像。

## 10.6 `drawdown_curve`

作用：

- 保存回撤曲线数据或图像

## 10.7 `report`

作用：

- 保存结果页摘要或导出报告

建议格式：

- Markdown
- JSON

## 11. Artifact 命名建议

第一版建议命名结构保持简单但可追踪。

### 建议命名模板

```text
{artifact_type}_{session_id}_{strategy_id}_{run_id}.{ext}
```

### 示例

```text
strategy_schema_session123_stg_macd_510300_v1.json
backtest_result_session123_stg_macd_510300_v1_bt_20260422_001.json
equity_curve_session123_stg_macd_510300_v1_bt_20260422_001.json
report_session123_stg_macd_510300_v1_bt_20260422_001.md
```

## 12. Artifact 与 State 的关系

State 应保存 Artifact 的引用，而不是完整内容。

例如：

```json
{
  "artifacts": {
    "strategy_schema": "artifact://session123/strategy_schema_session123_stg_macd_510300_v1.json",
    "backtest_result": "artifact://session123/backtest_result_session123_stg_macd_510300_v1_bt_20260422_001.json"
  }
}
```

这样做的好处：

- State 更轻
- Artifact 可独立管理
- 结果恢复更清晰

## 13. Artifact 生命周期

第一版建议定义以下生命周期阶段。

## 13.1 创建

触发：

- 某阶段第一次产出对象

例如：

- Strategy Schema 固化后创建 `strategy_schema`
- 回测完成后创建 `backtest_result`

## 13.2 更新

触发：

- 同一阶段对象有新的稳定版本

第一版建议：

- 尽量新增新 Artifact，而不是覆盖旧对象
- 必要时可以把“latest 引用”保存在 State

## 13.3 引用

触发：

- Agent / Tool / 前端需要读取已有结果

方式：

- 通过 Artifact URI 或 Artifact ID

## 13.4 复用

触发：

- 用户继续追问
- 用户修改参数重跑

方式：

- 从已有 `strategy_schema` / `backtest_result` Artifact 恢复

## 14. 多轮研究如何恢复

这是第一版必须支持的能力。

当用户问：

- “如果把 MACD 参数改成 6, 13, 5 呢？”

系统建议按以下顺序恢复：

1. 从 Session State 读取当前 `strategy.schema`
2. 若 State 缺失，则从 `strategy_schema` Artifact 恢复
3. 生成一个新的修改版策略对象
4. 创建新的回测 run
5. 保存新的 `backtest_result` 和 `equity_curve` Artifact

而不是重新从整段对话文本抽取一遍。

## 15. 推荐的 Artifact 存储清单

第一版建议至少保证以下对象一定落 Artifact。

### 必存

- `strategy_schema`
- `backtest_result`
- `equity_curve`

### 强烈建议存

- `strategy_card`
- `drawdown_curve`
- `report`

### 可选

- `strategy_draft`
- `clarification_trace`

## 16. 与收益曲线要求的关系

前面结果页文档已经明确：

- 回测收益曲线是硬要求

因此这份文档也要明确：

- `equity_curve` 不只是前端临时图表数据
- 它应该成为一类正式 Artifact

原因：

- 它是结果页必需项
- 它是结果解释的重要依据
- 它是后续对比和导出的基础对象

## 17. 回调与 State / Artifact 更新点

第一版建议在以下关键节点触发回调更新：

### 解析完成后

- 更新 `strategy.draft`
- 可选保存 `strategy_draft` Artifact

### 澄清完成后

- 更新 `clarification.*`

### Schema 固化后

- 更新 `strategy.schema`
- 保存 `strategy_schema` Artifact

### 回测完成后

- 更新 `backtest.status`
- 保存 `backtest_result` Artifact
- 保存 `equity_curve` Artifact

### 结果组装后

- 更新 `result.*`
- 保存 `report` Artifact

## 18. 一个推荐的 State + Artifact 执行链

```text
User Query
  -> Session created
  -> State.current_query updated
  -> StrategyParsingAgent
  -> State.strategy.draft updated
  -> Clarification loop
  -> State.clarification updated
  -> Strategy schema finalized
  -> Artifact(strategy_schema) created
  -> BacktestRunTool
  -> Artifact(backtest_result) created
  -> Artifact(equity_curve) created
  -> Metrics + Explanation
  -> ReportAssemblyTool
  -> Artifact(report) created
  -> State.result updated
```

## 19. 第一版边界控制

第一版建议保持克制。

### 第一版先做

- 结构化 State
- 核心 Artifact 类型
- 引用式状态管理
- 基本恢复能力

### 第一版暂不急着做

- 复杂 Artifact 版本树
- Artifact 差异比较
- 大规模长期研究档案管理
- 重型检索式 Artifact 索引

## 20. 下一步建议

基于这份文档，下一步最适合继续写的是：

1. `implementation_roadmap_v1.md`
2. `mvp_scope_checklist_v1.md`

因为到这里为止，项目的产品、规则、架构、接口、状态和产物都已经收敛得比较完整了。

接下来最值得做的是：

- 把这些设计转成分阶段实现路线
- 明确第一版哪些是必须落地、哪些可以后置
