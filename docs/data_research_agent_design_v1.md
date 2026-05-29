# DataResearchAgent Design v1

## 目标

`DataResearchAgent` 负责在策略设计完成后、正式回测执行前，判断数据是否足够支撑本次回测。

它不是回测 Agent，也不是任意 Tushare 查询助手。它的职责是：

- 读懂 `StrategySchema` 对数据的需求。
- 判断本地数据是否覆盖标的、时间、频率、字段。
- 识别缺口和风险。
- 在需要补数时，生成结构化补数计划。
- 不直接替用户做投资判断。

## 放在 ADK 编排中的位置

当前链路：

```text
IntentClassifierAgent
-> ClarificationAgent
-> StrategyDesignerAgent
-> StrategyExecutionAgent
-> ResultExplanationAgent
```

建议链路：

```text
IntentClassifierAgent
-> ClarificationAgent
-> StrategyDesignerAgent
-> DataResearchAgent
-> StrategyExecutionAgent
-> ResultExplanationAgent
```

原因：

- `IntentClassifierAgent` 和 `ClarificationAgent` 决定“用户到底要不要回测、是否缺关键字段”。
- `StrategyDesignerAgent` 产出 `StrategySchema`，数据需求才能具体化。
- `DataResearchAgent` 根据 schema 判断数据是否可用。
- `StrategyExecutionAgent` 继续保持确定性执行，不把数据研究逻辑塞进去。

## Agent 类型

第一阶段建议使用 `LlmAgent`，输出结构化 schema。

但它只能做“数据需求分析和补数计划”，不直接调用 Tushare 拉数。

真正的数据探测和补数由确定性工具完成：

- `inspect_local_data`
- `check_tushare_environment`
- `probe_tushare_api`
- `plan_tushare_fetch`
- `fetch_tushare_data`
- `normalize_market_data`
- `store_market_data_artifact`

## 输出结构：DataAvailabilityReport

```json
{
  "is_required": true,
  "is_ready": true,
  "blocking_issues": [],
  "warnings": ["period.end defaults to latest local trade date"],
  "required_datasets": [
    {
      "dataset": "fund_daily",
      "symbols": ["510300.SH"],
      "start_date": "20180101",
      "end_date": "latest",
      "frequency": "1d",
      "fields": ["trade_date", "open", "close"],
      "local_path_hint": "data/raw/fund_daily/510300.SH.parquet",
      "fallback_api": "fund_daily"
    }
  ],
  "local_coverage": [
    {
      "dataset": "fund_daily",
      "symbol": "510300.SH",
      "exists": true,
      "start_date": "20230103",
      "end_date": "20241231",
      "row_count": 484,
      "missing_fields": []
    }
  ],
  "fetch_plan": [],
  "rationale": "本地 ETF 日线数据足以支撑回测。"
}
```

字段含义：

- `is_required`：本轮是否需要数据检查。解释类请求可为 `false`。
- `is_ready`：是否可以进入回测执行。
- `blocking_issues`：阻塞回测的问题，例如本地数据缺失、字段缺失、Tushare token 不可用。
- `warnings`：不阻塞但需要披露的问题，例如结束日期使用本地最新交易日。
- `required_datasets`：从策略 schema 推导出来的数据需求。
- `local_coverage`：本地数据实际覆盖情况。
- `fetch_plan`：如需补数，给出结构化计划。
- `rationale`：中文解释。

## DataRequestSchema

补数计划使用单独结构：

```json
{
  "task_type": "daily_bar",
  "dataset": "daily_qfq",
  "api_name": "daily",
  "symbols": ["300750.SZ"],
  "start_date": "20180101",
  "end_date": "latest",
  "fields": ["trade_date", "open", "high", "low", "close", "vol", "amount"],
  "adjustment": "qfq",
  "output_format": "parquet",
  "target_path": "data/derived/daily_qfq/300750.SZ.parquet",
  "reason": "backtest_missing_local_data"
}
```

第一阶段支持的 `task_type`：

- `fund_daily`
- `index_daily`
- `daily_bar`
- `daily_basic`
- `adj_factor`

先不覆盖财务、新闻、资金流、宏观，避免 MVP 被数据范围拖散。

## 本地数据优先原则

默认策略：

1. 先查本地 parquet。
2. 如果本地足够，`is_ready=true`，不联网。
3. 如果本地不足，`is_ready=false`，生成 `fetch_plan`。
4. 是否自动补数由产品策略决定，MVP 可以先只展示缺口。
5. 补数完成后，重新执行数据检查，再进入回测。

这样可以保证：

- 回测可复现。
- 不因为在线接口波动影响结果。
- 不消耗不必要的 Tushare 配额。
- 用户知道数据口径。

## 和 StrategyExecutionAgent 的关系

`StrategyExecutionAgent` 应增加一个 gate：

```text
if DataAvailabilityReport exists and is_ready is false:
    skip backtest
    expose blocking_issues and fetch_plan
```

不要让执行 Agent 自己判断哪些 Tushare 接口该拉。

执行 Agent 只消费“数据已准备好”的状态。

## 和 Tushare Skill 的关系

官方 Tushare skill 给我们三层借鉴：

1. 自然语言数据任务 taxonomy。
2. 接口选择和字段确认原则。
3. 输出口径、限制和文件路径说明。

但我们不直接把官方 demo 脚本接进回测主链路。

更合适的方式是：

- 把官方 skill 作为 `DataResearchAgent` 的知识参考。
- 把 Tushare API 调用封装成确定性工具。
- 把数据写入本地标准目录，再由回测引擎读取。

## 最小可行版本

第一版只做三件事：

1. `DataResearchAgent` 结构化输出 `DataAvailabilityReport`。
2. 确定性工具 `inspect_local_data` 检查本地 parquet 是否存在、日期范围和字段是否足够。
3. `StrategyExecutionAgent` 根据 `data_availability.is_ready` 决定是否继续。

暂时不自动补数。

这样能先把产品体验跑通：

- 用户不会看到回测失败后才知道缺数据。
- Agent 执行轨迹会显示“检查本地数据”。
- 结果页可以明确告诉用户“缺哪份数据，建议用哪个 Tushare 接口补”。

## 推荐 Pydantic Schema

建议新增到 `schemas/agent_outputs.py` 或单独文件 `schemas/data_research.py`：

```python
class RequiredDataset(BaseModel):
    dataset: Literal["fund_daily", "index_daily", "daily_qfq", "daily_basic", "adj_factor"]
    symbols: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    frequency: Literal["1d"] = "1d"
    fields: list[str] = Field(default_factory=list)
    local_path_hint: str | None = None
    fallback_api: str | None = None


class LocalCoverage(BaseModel):
    dataset: str
    symbol: str | None = None
    exists: bool
    start_date: str | None = None
    end_date: str | None = None
    row_count: int = 0
    missing_fields: list[str] = Field(default_factory=list)


class DataFetchPlan(BaseModel):
    task_type: str
    api_name: str
    symbols: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    fields: list[str] = Field(default_factory=list)
    target_path: str
    reason: str


class DataAvailabilityReport(BaseModel):
    is_required: bool
    is_ready: bool
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_datasets: list[RequiredDataset] = Field(default_factory=list)
    local_coverage: list[LocalCoverage] = Field(default_factory=list)
    fetch_plan: list[DataFetchPlan] = Field(default_factory=list)
    rationale: str
```

## Agent 提示词约束

`DataResearchAgent` 的 instruction 应包含：

- 只输出 `DataAvailabilityReport` JSON。
- 如果 `IntentClassifierAgent.is_backtest_request=false`，输出 `is_required=false, is_ready=true`。
- 如果 `ClarificationAgent.needs_clarification=true`，输出 `is_required=false, is_ready=false`，不要生成补数计划。
- 对 `signal_trading`：
  - ETF / 基金优先需要 `fund_daily`。
  - A 股个股优先需要 `daily_qfq`。
  - 指数基准需要 `index_daily`。
- 对 `cross_sectional_rotation`：
  - 需要 `daily_basic` 截面。
  - 需要每个入选股票的 `daily_qfq`。
  - 第一版可以只检查 `daily_basic` 和回测基准，个股覆盖由回测引擎按需检查。
- 不要直接调用 Tushare。
- 不要把默认手续费、滑点、日期当成阻塞数据问题。
- 数据缺口要说清楚“缺什么、本地路径、建议接口”。

## 执行轨迹设计

用户看到的 timeline 建议是：

```text
意图分类 Agent：完成
澄清判断 Agent：完成
策略设计 Agent：完成
数据研究 Agent：检查本地数据
数据研究 Agent：数据就绪 / 发现缺口
执行回测：开始
计算指标：完成
生成结果页：完成
```

如果数据缺失：

```text
数据研究 Agent：发现缺口
执行回测：跳过
```

页面总结应该显示：

- 缺失数据集
- 缺失标的/日期范围
- 建议 Tushare 接口
- 是否可一键补数（第二阶段）

## 第一版实现步骤

1. 新增 `DataAvailabilityReport` 相关 schema。
2. 新增 `agents/data_research.py`，使用 `output_schema=DataAvailabilityReport`。
3. 在 `orchestrator.py` 中插入 `create_data_research_agent()`。
4. 扩展 `structured_outputs.AGENT_OUTPUT_SCHEMAS`，让 runtime 能收集 `data_availability`。
5. 新增 `tools/data_availability.py` 或 `services/data_availability.py`，做本地 parquet 覆盖检查。
6. 在 `StrategyExecutionAgent` 的 gate 中加入：
   - 如果存在 `data_availability.is_ready=false`，跳过执行。
7. 前端 result view 支持 `blocked_missing_data` 状态。
8. 加测试：
   - 本地数据存在：MACD 可以继续跑。
   - 数据缺失：不进入 `run_backtest`。
   - 非回测问题：`DataResearchAgent` 不阻塞解释类回答。

## 第二阶段

第二阶段再增加：

- `check_tushare_environment`
- `probe_tushare_api`
- `fetch_tushare_data`
- `normalize_market_data`
- `store_market_data_artifact`

补数流程也要通过 ADK timeline 暴露，避免用户干等。

## 设计边界

- 不直接给投资建议。
- 不把实时行情混进历史回测。
- 不为了某个极端自然语言 case 写规则补丁。
- 不让 LLM 直接联网拉全量数据。
- 不在 `StrategyExecutionAgent` 里堆数据接口选择逻辑。
