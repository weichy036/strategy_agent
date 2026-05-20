# Strategy Agent

Strategy Agent 是一个面向普通投资者与研究型用户的自然语言量化研究产品。

它的目标不是“替用户荐股”，而是帮助用户把模糊的投资想法，转成可解释、可回测、可复现的策略研究过程，让用户真正知道自己在做什么。

当前项目的工程原则已经明确：

- Python 环境与依赖统一使用 `uv` 管理
- 整个 Agent 系统必须基于 Google ADK 设计和实现
- 设计优先于编码，先把产品、策略和系统文档打磨清楚

## 愿景

用户可以像和研究员对话一样提问：

- “对于沪深300ETF，MACD 日线金叉买入、死叉卖出，每年的平均收益是多少？”
- “如果每个月买入市值最大的 20 只股票，持有到下个月，收益是多少？”
- “如果我只买过去 60 天创出新高、且换手率大于过去一年中位数的股票，结果会怎样？”

系统负责把这些自然语言问题拆解为：

1. 策略定义
2. 数据需求
3. 回测假设
4. 交易约束
5. 结果解释

最终输出的不只是收益率，还包括：

- 策略逻辑摘要
- 参数与假设
- 回测区间
- 收益与风险指标
- 交易明细
- 结果解释与局限性

## 产品定位

一句话定义：

“一个把自然语言投资想法转成可验证量化策略的研究助手。”

产品核心价值：

- 降低量化研究门槛
- 避免模糊叙事和拍脑袋投资
- 让策略可以被验证、复现和比较
- 让普通用户也能理解收益来自哪里、风险来自哪里

## 推荐的首期范围

为了尽快做出一个真实可用的 MVP，建议第一阶段只做：

- 市场范围：A 股、ETF
- 数据频率：日频
- 策略类型：技术指标策略、规则选股策略、定期调仓策略
- 回测模式：多头、无杠杆、基础手续费和滑点
- 输出形式：对话式解释 + 图表化回测结果

## 核心原则

- 先做“研究工具”，不做“荐股工具”
- 先做“可解释”，再做“高复杂度模型”
- 先做“少而准的策略能力”，再做“全能策略语言”
- 先解决“用户知道自己在干什么”，再追求“自动化赚钱”
- 先按 Google ADK Native 架构设计，再考虑具体实现细节
- 环境、依赖、运行入口统一收敛到 `uv`

## 模型配置

当前默认模型已切到 DeepSeek（通过 Google ADK + LiteLLM）：

- `ADK_MODEL=deepseek/deepseek-chat`
- `DEEPSEEK_API_KEY=...`
- `DEEPSEEK_API_BASE=https://api.deepseek.com`

本地开发可直接使用项目根目录 `.env`，`config` 会在启动时自动加载。

### 模型连通性自检

项目提供了最小诊断接口：

- 启动：`UV_CACHE_DIR=.uv-cache uv run strategy-agent-api`
- 配置检查：`GET /health/model`
- 在线探测：`GET /health/model?check=1`

说明：

- `check=0`（默认）只检查本地配置，不发起外网请求。
- `check=1` 会通过 DeepSeek API 发起一次最小请求，用于验证密钥与网络连通性。

### 研究接口

- 示例查询：`GET /research/examples`
- 执行研究（Agent-first）：`POST /research/run`

请求体示例：

```json
{
  "query": "如果每个月买入市值最大的20只股票，持有到下个月，收益是多少？",
  "user_id": "web-user",
  "session_id": "demo-api"
}
```

说明：

- `user_id + session_id` 用于多轮会话连续性（ADK Session）。
- 接口主路径为 Agent 编排，不再依赖规则解析主流程。
- 当 Agent 成功完成回测时，`data.result_page.equity_curve.series` 为收益曲线。

### Web 页面

已内置一个参考 `finance_agent` 风格的最小研究页面：

- 启动：`UV_CACHE_DIR=.uv-cache uv run strategy-agent-api`
- 打开：`http://127.0.0.1:8000/`

页面支持直接输入自然语言问题，并展示：

- 多轮对话时间线（用户/Agent）
- 执行轨迹（Agent 工具调用过程）
- 回测状态与策略摘要
- 核心指标卡片
- 收益曲线（SVG）
- 年度收益表与风险提示
- 澄清交互（当缺少关键信息时，可直接补充并继续回测）

澄清续聊机制：

- 补充信息会作为同一 `user_id + session_id` 会话中的下一轮消息发送给 Agent。
- 不再通过字符串拼接“原问题 + 补充条件”来驱动主流程。

## 文档

- [产品蓝图](docs/product_blueprint.md)
- [设计路线图](docs/design_roadmap.md)
- [环境与依赖说明](docs/environment_setup.md)
- [ADK 架构原则](docs/adk_architecture.md)
- [用户流程 V1](docs/user_flow_v1.md)
- [Strategy Schema V1](docs/strategy_schema_v1.md)
- [澄清规则 V1](docs/clarification_rules_v1.md)
- [回测假设 V1](docs/backtest_assumptions_v1.md)
- [指标与结果解释 V1](docs/metrics_and_explanations_v1.md)
- [ADK 系统架构 V1](docs/adk_system_architecture_v1.md)
- [ADK Agent 拓扑 V1](docs/adk_agent_topology_v1.md)
- [数据访问架构 V1](docs/data_access_architecture_v1.md)
- [Tool Contracts V1](docs/tool_contracts_v1.md)
- [ADK State 与 Artifacts V1](docs/adk_state_and_artifacts_v1.md)
- [实现路线图 V1](docs/implementation_roadmap_v1.md)
- [MVP 范围清单 V1](docs/mvp_scope_checklist_v1.md)
- [仓库脚手架 V1](docs/repository_scaffold_v1.md)
- [数据清单](docs/data_inventory.md)

## 当前实现进度

目前已经完成：

1. `uv` + Google ADK 工程骨架与根 Agent 编排
2. 自然语言策略解析、Schema 校验、澄清决策主链路
3. ETF `MACD` 策略回测闭环（含收益曲线、指标与结果页）
4. A 股“月度市值 Top N 轮动”回测闭环（含收益曲线、指标与结果页）
5. 研究过程关键 Artifact 落盘（`strategy_schema/backtest/equity_curve/report`）

当前下一步：

1. 将研究流接入 API / 页面，展示完整收益曲线与指标卡片
2. 增加更完整的测试样例与多轮会话恢复
3. 补充更细的风险与交易统计（如胜率、换手、行业暴露）
