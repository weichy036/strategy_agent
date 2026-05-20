# ADK 全 Agent 化执行蓝图 V1

## 1. 文档目标

这份文档只解决一件事：把本项目的主链路设计成 **100% Agent 驱动** 的执行系统。

约束如下：

- 全流程由 Agent 判定与推进，不使用规则树做兜底决策
- Google ADK 是唯一编排框架（Session / State / Callback / Tool / AgentAsTool / Workflow）
- 结果页必须包含回测收益曲线，否则视为未完成
- 用户在执行过程中必须看到“当前 Agent 在做什么”，不能长时间无反馈

---

## 2. 核心原则

### 原则 A：决策权只在 Agent，不在规则代码

可以有 Schema 校验、类型约束、工具参数检查，但这些只负责“输入合法性”，不负责业务决策。

业务决策统一由 Agent 输出，包括：

- 是否需要澄清
- 先执行哪条研究分支
- 使用哪个回测路径
- 结果如何解释与风险提示

### 原则 B：工具是能力，不是流程

Tool 只做确定性能力（拉数据、执行回测、计算指标、组装报告），不拼流程。
流程编排由 Orchestrator Agent + SubAgent 负责。

### 原则 C：状态是共享认知，Artifact 是可追溯证据

- State 用于“当前会话工作记忆”
- Artifact 用于“可复用研究产物”
- 任一关键结论都必须能追溯到对应 Artifact

### 原则 D：收益曲线是结果页硬门槛

即使指标都已计算完成，只要缺少收益曲线，结果页就不允许进入 `done` 状态。

---

## 3. ADK 抽象映射

## 3.1 Session

每次用户会话对应一个 ADK Session，承载：

- 用户多轮输入
- Agent 事件流
- 会话状态

建议继续使用现有 SessionService（开发环境可 InMemory/SQLite，生产可持久化后端）。

## 3.2 State（建议键位）

- `user:investor_profile`
- `user:risk_preference`
- `session:current_intent`
- `session:strategy_draft`
- `session:clarification_round`
- `session:backtest_status`
- `session:result_page_status`
- `temp:active_subtask`
- `temp:tool_trace_buffer`

说明：

- `user:` 用于跨轮偏好记忆
- `session:` 用于本次研究主状态
- `temp:` 用于当前轮中间态，允许被覆盖

## 3.3 Artifact（建议清单）

- `strategy_schema.json`
- `strategy_card.json`
- `backtest_result.json`
- `equity_curve.json`
- `metrics_snapshot.json`
- `result_page.json`

其中 `equity_curve.json` 为强制产物。

## 3.4 Callback（全局可观测性入口）

统一在 LlmAgent 上启用以下回调：

- `before_model_callback`: 写入“思考阶段”轨迹
- `after_model_callback`: 记录模型阶段产出摘要
- `before_tool_callback`: 写入“准备执行工具”
- `after_tool_callback`: 写入“工具执行成功 + 摘要”
- `on_tool_error_callback`: 写入“工具失败 + 重试意图”
- `on_model_error_callback`: 写入“模型异常 + 降级方案”

这些轨迹写入 `temp:tool_trace_buffer`，并同步给前端时间线。

## 3.5 AgentAsTool（协作主干）

每个子能力 Agent 都通过 `AgentTool` 暴露给编排 Agent：

- `intent_classifier_agent_tool`
- `clarification_agent_tool`
- `strategy_designer_agent_tool`
- `backtest_executor_agent_tool`
- `result_explainer_agent_tool`

这样编排层可以像调用普通 Tool 一样调用子 Agent，并天然复用 ADK 的上下文与状态传播能力。

---

## 4. 推荐执行拓扑（Workflow + AgentAsTool）

主入口：`orchestrator_agent`

执行阶段：

1. 意图判定阶段  
`orchestrator -> intent_classifier_agent_tool`
2. 澄清补全阶段  
`orchestrator -> clarification_agent_tool`
3. 策略生成阶段  
`orchestrator -> strategy_designer_agent_tool`
4. 回测执行阶段  
`orchestrator -> backtest_executor_agent_tool`
5. 结果解释阶段  
`orchestrator -> result_explainer_agent_tool`
6. 结果组装阶段  
`orchestrator -> report_assembly_tool`

所有阶段都由 Agent 决定是否继续、回退、重试或再澄清。

---

## 5. 时间线可视化规范（防止用户“干等”）

前端时间线最少展示以下事件类型：

- `agent_enter`
- `agent_decision`
- `tool_start`
- `tool_done`
- `tool_error`
- `agent_handoff`
- `waiting_user_input`
- `result_ready`

最低可见轨迹示例：

- `validate_strategy -> backtest_run -> metrics_compute -> report_assembly`

每条轨迹字段建议：

- `event_id`
- `timestamp`
- `stage`
- `actor`（agent/tool 名）
- `status`（running/success/error/waiting）
- `message`（短文案）

---

## 6. 结果页完成条件（Done Definition）

只有满足以下条件才允许返回“回测完成”：

- 存在 `backtest_result` Artifact
- 存在 `equity_curve` Artifact
- 结果页结构化对象通过 schema 校验
- 时间线中至少包含一次 `backtest_run` 成功事件

若缺失收益曲线：

- 系统状态置为 `session:result_page_status = blocked`
- Agent 必须继续补全，不得直接给“完成”答复

---

## 7. 与当前代码结构的落点

建议优先收敛这些文件职责：

- `src/strategy_agent/agents/orchestrator.py`  
  只做编排与委托，不写业务规则分支
- `src/strategy_agent/agents/*.py`  
  每个子 Agent 只聚焦单一职责
- `src/strategy_agent/tools/*.py`  
  只保留确定性工具逻辑
- `src/strategy_agent/services/session_state.py`  
  统一状态读写封装
- `src/strategy_agent/services/artifact_manager.py`  
  统一产物存取
- `src/strategy_agent/static/app.js`  
  接收并渲染 Agent 时间线

---

## 8. 实施顺序（下一步）

1. 把 Orchestrator 改成 AgentAsTool 协作主链  
2. 给 LlmAgent 挂完整回调并落时间线状态  
3. 打通“收益曲线缺失即阻塞”状态门  
4. 前端渲染执行轨迹与阶段状态  
5. 最后补多轮澄清与中断恢复

---

## 9. 验收标准

- 用户发起一个策略请求后，能持续看到执行轨迹变化
- 关键阶段失败时，轨迹可见错误点与重试动作
- 全流程决策由 Agent 输出，不存在规则树分流
- 结果页始终包含收益曲线
- Session/State/Artifact 中可复盘整个研究过程
