# 仓库脚手架 V1

## 1. 文档目标

这份文档用于定义第一版项目的代码仓库结构和首批文件脚手架。

它回答的问题是：

- 代码目录怎么组织
- 哪些模块应该先建出来
- 哪些文件属于第一批必须存在的骨架
- 如何让当前设计文档自然映射到代码结构

这份文档的目标不是写实现细节，而是避免我们一开始写代码时目录结构反复调整。

## 2. 设计原则

### 原则 1：结构要服务于 ADK Native 架构

目录结构必须能直接映射：

- Agents
- Tools
- State / Artifact
- 数据访问层
- 域层

### 原则 2：结构要服务于第一版 MVP，而不是未来所有可能性

先把最小可运行版本需要的模块立住，不急着做非常复杂的分层。

### 原则 3：确定性能力和 Agent 编排能力分开

目录上要一眼能看出：

- 哪些是 Agent
- 哪些是 Tool
- 哪些是纯数据或领域逻辑

### 原则 4：文档与代码要能互相映射

比如：

- `strategy_schema_v1.md` 对应 `schemas/strategy_schema.py`
- `tool_contracts_v1.md` 对应 `tools/` 下的工具输入输出实现

## 3. 推荐仓库结构

第一版建议采用下面这套结构。

```text
/Users/admin/weichy/strategy_agent
├── README.md
├── pyproject.toml
├── uv.lock
├── data/
├── docs/
├── strategy_agent/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   ├── constants.py
│   ├── agents/
│   ├── tools/
│   ├── schemas/
│   ├── data_access/
│   ├── domain/
│   ├── services/
│   ├── artifacts/
│   └── utils/
└── tests/
```

## 4. 顶层目录说明

## 4.1 `data/`

用途：

- 保存本地市场数据

当前已存在：

- `raw/fund_daily`
- `raw/index_daily`
- `raw/daily_basic`
- `derived/daily_qfq`

## 4.2 `docs/`

用途：

- 保存所有设计文档

当前已经较完整，后续不建议再无限扩张，只保留真正有约束价值的文档。

## 4.3 `strategy_agent/`

用途：

- 保存项目主代码

建议整个第一版核心实现都从这里开始。

## 4.4 `tests/`

用途：

- 保存最小测试集

第一版可以先不追求测试量大，但建议从主链路就开始有最小用例。

## 5. `strategy_agent/` 内部结构

## 5.1 `app.py`

作用：

- 项目主入口
- 初始化 ADK Runner
- 注册顶层 Agent
- 绑定 Session / Artifact / Memory 服务

它是整个系统的运行起点。

## 5.2 `config.py`

作用：

- 集中管理配置

建议包括：

- 数据目录
- 默认市场
- 默认回测参数
- Artifact 根目录
- Session / Memory 配置

## 5.3 `constants.py`

作用：

- 放稳定常量

例如：

- 默认指标参数
- 默认手续费与滑点
- 默认过滤项
- 默认支持的策略类型

## 6. `agents/` 目录

建议第一版至少建立以下文件。

### `agents/__init__.py`

作用：

- 导出主要 Agent

### `agents/orchestrator.py`

作用：

- 实现 `ResearchOrchestratorAgent`

### `agents/strategy_parsing.py`

作用：

- 实现 `StrategyParsingAgent`

### `agents/result_explanation.py`

作用：

- 实现 `ResultExplanationAgent`

### `agents/follow_up.py`

作用：

- 预留 `ResearchFollowUpAgent`

第一版可以先放空骨架或简单占位实现。

## 7. `tools/` 目录

建议第一版至少建立以下文件。

### `tools/__init__.py`

### `tools/instrument_resolve.py`

实现：

- `InstrumentResolveTool`

### `tools/strategy_validation.py`

实现：

- `StrategyValidationTool`

### `tools/clarification_decision.py`

实现：

- `ClarificationDecisionTool`

### `tools/market_data_query.py`

实现：

- `MarketDataQueryTool`

### `tools/backtest_run.py`

实现：

- `BacktestRunTool`

### `tools/metrics_compute.py`

实现：

- `MetricsComputeTool`

### `tools/artifact_store.py`

实现：

- `ArtifactStoreTool`

### `tools/report_assembly.py`

实现：

- `ReportAssemblyTool`

## 8. `schemas/` 目录

这是非常关键的一层。

建议第一版至少建立以下文件。

### `schemas/__init__.py`

### `schemas/strategy_schema.py`

作用：

- 对应 [Strategy Schema V1](docs/strategy_schema_v1.md)

建议内容：

- Strategy 顶层对象定义
- 子对象定义
- 校验逻辑

### `schemas/tool_contracts.py`

作用：

- 对应 [Tool Contracts V1](docs/tool_contracts_v1.md)

建议内容：

- Tool 输入输出对象定义
- 错误对象定义
- 统一返回包装定义

### `schemas/state.py`

作用：

- 对应 [ADK State 与 Artifacts V1](docs/adk_state_and_artifacts_v1.md)

建议内容：

- Session State 顶层结构
- clarification / strategy / backtest / result 子对象

### `schemas/result_page.py`

作用：

- 对应结果页输出结构

建议内容：

- metric cards
- equity curve
- drawdown curve
- risk disclosures

## 9. `data_access/` 目录

这一层建议严格保持“确定性、无 Agent 化”。

### `data_access/__init__.py`

### `data_access/storage.py`

作用：

- 路径常量
- 文件存在性检查
- 基础 parquet 读取

### `data_access/normalize.py`

作用：

- 对不同来源数据做统一化处理

重点对应：

- ETF / 股票 / 指数价格结构统一
- `daily_basic` 单位统一
- `asset_type` / `price_mode` 补齐

### `data_access/status.py`

作用：

- 数据可用性检查
- 最新交易日判断

## 10. `domain/` 目录

这一层负责给 Tool 提供业务友好的接口。

### `domain/__init__.py`

### `domain/instruments.py`

作用：

- 标的解析
- 标的别名
- 市场分类

### `domain/market_data.py`

作用：

- 面向业务的市场数据读取接口

建议暴露：

- `get_bar_frame`
- `get_daily_basic_frame`
- `get_daily_basic_by_instrument`
- `get_latest_trade_date`
- `get_benchmark_frame`

### `domain/backtest.py`

作用：

- 回测执行核心逻辑

这里建议放纯执行逻辑，不放 ADK 调用细节。

### `domain/metrics.py`

作用：

- 指标计算逻辑

## 11. `services/` 目录

这层用于放会跨多个模块的服务对象。

### `services/session_state.py`

作用：

- State 初始化
- State 更新辅助逻辑

### `services/artifact_manager.py`

作用：

- Artifact 命名
- Artifact 写入 / 引用管理

### `services/clarification.py`

作用：

- 澄清流程辅助逻辑

### `services/result_builder.py`

作用：

- 把回测结果、指标、解释组装成结果页结构

## 12. `artifacts/` 目录

这里是代码层的辅助目录，不是数据层 Artifact 存储目录本身。

建议内容：

- Artifact 类型定义
- 命名模板
- 序列化辅助函数

### 建议文件

- `artifacts/__init__.py`
- `artifacts/naming.py`
- `artifacts/serializers.py`

## 13. `utils/` 目录

只放真正跨模块、低业务耦合的工具。

例如：

- 日期处理
- DataFrame 辅助函数
- 日志格式化

不要把核心业务逻辑塞进 `utils/`。

## 14. `tests/` 目录建议

第一版建议至少有下面这些测试文件占位。

```text
tests/
├── test_strategy_schema.py
├── test_market_data.py
├── test_instrument_resolve.py
├── test_clarification_flow.py
├── test_backtest_etf.py
└── test_backtest_rotation.py
```

## 15. 第一批必须创建的文件

如果下一步开始真正建代码骨架，建议第一批先创建下面这些文件。

### P0 文件

- `strategy_agent/__init__.py`
- `strategy_agent/app.py`
- `strategy_agent/config.py`
- `strategy_agent/constants.py`
- `strategy_agent/agents/orchestrator.py`
- `strategy_agent/agents/strategy_parsing.py`
- `strategy_agent/agents/result_explanation.py`
- `strategy_agent/tools/strategy_validation.py`
- `strategy_agent/tools/market_data_query.py`
- `strategy_agent/tools/backtest_run.py`
- `strategy_agent/tools/metrics_compute.py`
- `strategy_agent/schemas/strategy_schema.py`
- `strategy_agent/schemas/state.py`
- `strategy_agent/data_access/storage.py`
- `strategy_agent/data_access/normalize.py`
- `strategy_agent/domain/market_data.py`

### P1 文件

- `strategy_agent/tools/instrument_resolve.py`
- `strategy_agent/tools/clarification_decision.py`
- `strategy_agent/tools/artifact_store.py`
- `strategy_agent/tools/report_assembly.py`
- `strategy_agent/services/session_state.py`
- `strategy_agent/services/artifact_manager.py`
- `strategy_agent/domain/backtest.py`
- `strategy_agent/domain/metrics.py`

## 16. 模块依赖建议

为了减少循环依赖，建议遵守下面这个方向：

```text
agents -> tools -> domain -> data_access
agents -> schemas
tools -> schemas
services -> schemas / domain / data_access
```

尽量避免：

- `domain` 反向依赖 `agents`
- `data_access` 反向依赖 `tools`

## 17. 从文档到代码的映射表

### 产品与流程文档

- `user_flow_v1.md`
  主要映射到 `agents/orchestrator.py`

### 结构化对象文档

- `strategy_schema_v1.md`
  映射到 `schemas/strategy_schema.py`

### 澄清文档

- `clarification_rules_v1.md`
  映射到 `tools/clarification_decision.py` 与 `services/clarification.py`

### 回测假设文档

- `backtest_assumptions_v1.md`
  映射到 `domain/backtest.py` 与 `constants.py`

### 结果页文档

- `metrics_and_explanations_v1.md`
  映射到 `domain/metrics.py`、`agents/result_explanation.py`、`schemas/result_page.py`

### ADK 文档

- `adk_system_architecture_v1.md`
- `adk_agent_topology_v1.md`
- `adk_state_and_artifacts_v1.md`

主要映射到：

- `app.py`
- `agents/`
- `services/session_state.py`
- `services/artifact_manager.py`

## 18. 第一版推荐起步方式

如果下一步就开始搭代码，我建议按下面顺序落文件：

1. 建 `strategy_agent/` 包和子目录
2. 建 `config.py` / `constants.py`
3. 建 `schemas/strategy_schema.py` / `schemas/state.py`
4. 建 `data_access/storage.py` / `data_access/normalize.py`
5. 建 `domain/market_data.py`
6. 建 `tools/strategy_validation.py` / `tools/market_data_query.py`
7. 建 `agents/orchestrator.py`
8. 再逐步补回测和解释链路

## 19. 结论

到这一步为止，项目已经不缺设计，也不缺目录方向。

这份脚手架文档的作用，就是让我们下一步开始写代码时：

- 不会乱建目录
- 不会把 Agent 和 Tool 写混
- 不会把数据访问和回测执行耦合在一起

如果按这份结构开工，后续扩展到更多策略类型、更多 Tool、更多 ADK 能力时，也会平滑很多。
