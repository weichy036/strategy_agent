# ADK Runtime Refactor Notes v1

## 背景

参考 `/Users/admin/weichy/baizhi-assistant` 的 ADK 重构实现后，我们确认 Strategy Agent 的运行时也应该从“能跑通”继续升级为“可观测、可测试、可扩展”的结构。重点不是复制业务代码，而是借鉴它对 ADK Runtime 的分层方式。

## 已借鉴并落地

### 0. TraceableAgentTool

新增 `strategy_agent.services.agent_tools.TraceableAgentTool`，并替换 orchestrator 中的四个 specialist subagent：

- `IntentClassifierAgent`
- `ClarificationAgent`
- `StrategyDesignerAgent`
- `ResultExplanationAgent`

它保留 Google ADK 原生 `AgentTool` 的核心行为：

- 使用子 Agent 的 input schema / output schema。
- 使用独立 child runner 执行子 Agent。
- 将子 Agent 的 state delta 同步回父 session。
- 复用父级 artifact、memory、credential、plugin 上下文。

同时额外把子 Agent 的关键过程写入父级 trace state：

- `subagent_start`
- `subagent_message`
- `subagent_tool_start`
- `subagent_tool_done`
- `subagent_done`

这样前端时间线后续可以展示“Agent 正在做什么”，而不是只在最终结果返回后一次性看到工具列表。

### 1. 集中管理 ADK state key

新增 `strategy_agent.services.state_keys.AgentStateKeys`，避免在 callbacks、runtime、collector 里散落字符串 key。

当前重点 key：

- `temp:tool_trace_buffer`：工具执行轨迹缓冲。
- `temp:active_subtask`：当前正在执行的子任务。
- `strategy.schema` / `backtest.result` / `metrics.result` / `report.result_page`：后续可用于把领域结果沉淀到 ADK session state。

### 2. Runtime 事件适配层

新增 `strategy_agent.services.adk_event_adapter`，把 Google ADK 原始 `Event` 转为项目内部的轻量 `AdkStreamEvent`。

这样做的好处：

- API/UI 不直接依赖 Google ADK 的原始事件结构。
- 后续做 SSE 实时输出时，可以复用同一层事件适配。
- 工具调用、工具结果、Agent 文本、state trace 能统一进入一条事件流。

### 3. 结果收集器

新增 `strategy_agent.services.result_collector.StrategyRunResultCollector`，负责把事件流归集成 API 需要的结果：

- `assistant_message`
- `tool_calls`
- `timeline`
- `result_page`
- `metrics`
- `backtest`
- `clarification`
- `status`

`agent_runtime.py` 现在只负责运行 ADK Runner，并把事件交给 adapter + collector。

## 从 Baizhi 继续值得借鉴的点

### 1. TraceableAgentTool 持续增强

`baizhi-assistant` 自定义了 `TraceableAgentTool`，可以在父 Agent 调用子 Agent 时，把子 Agent 内部事件也记录到同一个 trace recorder。

这对 Strategy Agent 很重要，因为我们的用户需要看到：

- 意图分类 Agent 正在判断问题类型。
- 策略设计 Agent 正在生成策略 schema。
- 回测工具正在执行。
- 指标工具正在计算。
- 解释 Agent 正在生成报告。

当前已经完成第一版替换。后续可以继续增强为完整 trace recorder，把耗时、token、错误、child event id 都记录下来。

### 2. Observability Recorder

`baizhi-assistant` 有完整的 `AdkRunTraceRecorder`，能记录：

- 每个 Agent 的事件数量。
- 每个工具的开始/结束/耗时。
- token usage。
- error summary。
- run duration。

Strategy Agent 可以做一个更轻量版本，先服务前端“执行中状态”和后端调试。

### 3. Session Mapping

`baizhi-assistant` 把外层请求上下文映射成 ADK 标准 `AdkRunInput`，再注入初始 state。

Strategy Agent 后续也应该显式建模：

- `user_id`
- `session_id`
- `run_id`
- `message`
- `history`
- `state_delta`

这会让多轮策略追问、基于旧策略继续创建、保存策略和回放研究过程都更稳。

## 下一步建议

优先级最高的是实现 Strategy Agent 版 `TraceableAgentTool`。它可以让前端时间线真正看到 subagent 内部发生了什么，而不是只看到外层工具调用结果。

第二步再做 SSE/streaming，把当前一次性返回的 timeline 变成边执行边推送，用户体验会明显提升。
