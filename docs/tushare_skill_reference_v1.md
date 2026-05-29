# Tushare Skill 借鉴说明 v1

## 安装状态

- 官方安装命令已执行：`npx skills add https://github.com/waditu-tushare/skills --skill tushare`
- 安装位置：`.agents/skills/tushare`
- 项目依赖已加入：`tushare==1.4.29`
- 环境变量：`TUSHARE_TOKEN` 已存在
- 冒烟测试：`trade_cal` 可正常返回交易日历

## 官方 Skill 的核心思想

Tushare skill 不是简单的 API 清单，它更像一个“数据研究工作流说明书”：

- 先识别用户要解决的问题，再选择接口。
- 对中文自然语言做实体、时间、市场、字段规范化。
- 请求前做环境检查：Python、依赖、Token、轻量接口冒烟。
- 写请求前先确认接口名、必填参数、返回字段、权限限制。
- 长区间和批量任务默认分段拉取、去重、排序、记录失败分段。
- 输出不仅给原始表，还要给口径、关键指标、异常点、限制和本地文件路径。

## 对 Strategy Agent 的可借鉴点

### 1. 数据 Agent 独立出来

我们现在的回测主链路已经是：

`Intent -> Clarification -> StrategyDesigner -> StrategyExecution -> ResultExplanation`

后续可以新增一个专门的数据子 Agent：

`DataResearchAgent`

职责不是直接回测，而是回答：

- 本地数据是否够用？
- 缺哪些数据？
- 应该用哪个 Tushare 接口补？
- 字段和时间范围是否可用？
- 是否需要提醒用户权限限制？

这样能避免把数据拉取逻辑塞进 `StrategyExecutionAgent`。

### 2. 做 DataRequestSchema

借鉴 Tushare skill 的 intent taxonomy，可以定义一个结构化数据请求：

```json
{
  "task_type": "daily_bar | daily_basic | fund_daily | adj_factor | finance | macro",
  "symbols": ["510300.SH"],
  "start_date": "20180101",
  "end_date": "latest",
  "fields": ["trade_date", "open", "close"],
  "frequency": "1d",
  "output_format": "parquet",
  "reason": "backtest_missing_data"
}
```

这比让工具直接接自然语言更稳，也符合我们“不用规则缝补，靠 Agent 输出结构化契约”的原则。

### 3. 数据工具要有环境预检

可以新增确定性工具：

- `check_tushare_environment`
- `probe_tushare_api`
- `plan_tushare_fetch`
- `fetch_tushare_data`
- `normalize_market_data`

执行顺序可以保持确定性：

`check -> probe -> plan -> fetch -> normalize -> store`

### 4. 本地优先，Tushare 补缺

我们的产品是回测工具，不能每次都在线拉取大数据。

推荐策略：

- 回测默认只读 `data/raw` 和 `data/derived`
- 如果本地数据缺失，Agent 先说明缺口
- 用户确认或系统策略允许时，再使用 Tushare 补数据
- 补到本地 parquet 后，再进入回测

这样结果可复现，也能减少 API 限流和权限问题。

### 5. 数据输出要带元信息

借鉴官方 skill 的 output contract，每次补数据都应写 metadata：

```json
{
  "source": "tushare",
  "api_name": "daily_basic",
  "params": {"trade_date": "20260421"},
  "fetched_at": "...",
  "row_count": 5300,
  "fields": ["ts_code", "trade_date", "total_mv"],
  "failed_chunks": []
}
```

这对金融回测很重要：未来用户问“这个结果基于什么数据”，我们能解释清楚。

## 不建议直接照搬的地方

- 官方 demo 脚本偏示例，不适合作为生产数据管道。
- skill 覆盖面很宽，股票、基金、宏观、新闻、资金流都有；我们 MVP 应该先聚焦回测必需数据。
- 不建议让 LLM 直接决定 API 参数并立即联网拉取，应先通过结构化 schema 和确定性工具校验。
- 不建议把 Tushare 实时查询混进回测主流程，否则结果复现性会变差。

## 推荐落地顺序

1. 新增 `DataRequestSchema` 和 `DataAvailabilityReport`。
2. 新增 `DataResearchAgent`，专门判断数据需求和缺口。
3. 新增 `check_tushare_environment` / `probe_tushare_api` 工具。
4. 把现有本地数据读取扩展为“本地优先、缺口报告”。
5. 再实现小范围补数据：`daily_basic`、`fund_daily`、`daily`、`adj_factor`。
6. 最后把补数据流程接入 ADK session state 和 artifact。

