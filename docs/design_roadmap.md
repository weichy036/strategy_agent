# 设计路线图

## 1. 目标

当前阶段我们先不急着写核心业务代码，而是先把整个项目的设计流程和文档体系搭完整。

目标是让后续实现建立在清晰、一致、可复用的设计基础上。

## 2. 当前已完成文档

已经存在的文档：

- [产品蓝图](docs/product_blueprint.md)
- [数据清单](docs/data_inventory.md)
- [环境与依赖说明](docs/environment_setup.md)
- [ADK 架构原则](docs/adk_architecture.md)
- [ADK 全 Agent 化执行蓝图 V1](docs/adk_agentic_execution_blueprint_v1.md)

这些文档分别回答：

- 为什么做这个产品
- 当前手里有什么数据
- 工程环境怎么统一
- Agent 系统必须如何建模

## 3. 建议的文档分层

整个项目文档建议分成四层。

### 第一层：产品层

回答：

- 产品目标是什么
- 用户是谁
- MVP 边界是什么
- 产品为什么有价值

当前核心文档：

- `product_blueprint.md`

### 第二层：用户流程层

回答：

- 用户如何提问
- 系统如何澄清
- 用户如何看到策略卡
- 用户如何看到结果和解释

建议后续新增：

- `user_flow_v1.md`

### 第三层：领域规则层

回答：

- 什么是一个策略对象
- 什么字段必填
- 什么情况下需要追问
- 回测默认假设是什么
- 结果页展示哪些指标

建议后续新增：

- `strategy_schema_v1.md`
- `clarification_rules_v1.md`
- `backtest_assumptions_v1.md`
- `metrics_and_explanations_v1.md`

### 第四层：系统架构层

回答：

- 在 ADK 里如何组织 Agent、Tool、Session、Artifact
- 数据访问层如何设计
- 回测引擎如何对接 Agent 工具层

建议后续新增：

- `adk_system_architecture_v1.md`
- `adk_agent_topology_v1.md`
- `data_access_architecture_v1.md`
- `tool_contracts_v1.md`
- `adk_state_and_artifacts_v1.md`
- `adk_agentic_execution_blueprint_v1.md`
- `implementation_roadmap_v1.md`
- `mvp_scope_checklist_v1.md`
- `repository_scaffold_v1.md`

## 4. 推荐设计顺序

为了降低返工，建议按下面顺序推进。

### Step 1：先定用户流程

输出目标：

- `user_flow_v1.md`

核心问题：

- 用户提问后，系统第一轮回复长什么样
- 什么信息必须澄清
- 什么时候直接执行回测

当前状态：

- 已完成第一版 `user_flow_v1.md`

### Step 2：再定策略中间表示

输出目标：

- `strategy_schema_v1.md`

核心问题：

- 系统内部如何统一表示一个策略
- 不同策略类型如何共享字段

当前状态：

- 已完成第一版 `strategy_schema_v1.md`

### Step 3：再定默认规则与约束

输出目标：

- `clarification_rules_v1.md`
- `backtest_assumptions_v1.md`

核心问题：

- 什么时候问用户
- 什么时候用默认值
- 回测可信度如何保证

当前状态：

- 已完成第一版 `clarification_rules_v1.md`
- 已完成第一版 `backtest_assumptions_v1.md`

### Step 4：再定结果解释规则

输出目标：

- `metrics_and_explanations_v1.md`

核心问题：

- 哪些指标必须展示
- 如何把结果翻译成普通用户能看懂的话

当前状态：

- 已完成第一版 `metrics_and_explanations_v1.md`

### Step 5：最后收敛 ADK 系统架构

输出目标：

- `adk_system_architecture_v1.md`
- `adk_agent_topology_v1.md`

核心问题：

- 哪些模块是 Agent
- 哪些模块是 Tool
- 如何组织 Session、Memory、Artifact

当前状态：

- 已完成第一版 `adk_system_architecture_v1.md`
- 已完成第一版 `adk_agent_topology_v1.md`
- 已完成第一版 `data_access_architecture_v1.md`
- 已完成第一版 `tool_contracts_v1.md`
- 已完成第一版 `adk_state_and_artifacts_v1.md`
- 已完成第一版 `implementation_roadmap_v1.md`
- 已完成第一版 `mvp_scope_checklist_v1.md`
- 已完成第一版 `repository_scaffold_v1.md`

## 5. 设计输出标准

后续每份文档都尽量满足四个要求：

### 要求 1：能指导实现

不是纯概念文章，而是能让后续开发知道怎么落地。

### 要求 2：能约束范围

明确第一版做什么，不做什么。

### 要求 3：能和 ADK 抽象对齐

系统设计文档必须说明与 ADK 的映射关系。

### 要求 4：能和数据现实对齐

设计不能脱离我们当前已经拥有的数据。

## 6. 当前项目的设计基线

截至目前，我们已经形成了几个明确结论：

- 产品定位是“自然语言量化研究助手”，不是荐股工具
- 当前先做 A 股和 ETF 的日频场景
- Python 环境统一使用 `uv`
- Agent 框架统一基于 Google ADK

这四条就是当前项目的设计基线。

## 7. 下一步建议

如果继续往下推进，我建议下一轮不再补新的核心设计文档，而是直接开始按路线图和脚手架进入代码骨架实现。
