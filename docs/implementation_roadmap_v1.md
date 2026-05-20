# 实现路线图 V1

## 1. 文档目标

这份文档用于把当前已经完成的产品、规则、架构和接口设计，转换成一条可执行的实现路线。

它回答的问题是：

- 我们应该先做什么，再做什么
- 第一版最小可运行版本由哪些模块组成
- 哪些能力必须第一阶段实现
- 哪些能力可以后置
- 如何在充分利用 Google ADK 的前提下，尽量降低返工

## 1.1 当前里程碑（截至 2026-04-23）

已完成：

- `uv` 工程与 Google ADK Runner 主骨架
- 自然语言策略解析、Schema 校验与澄清决策
- 单标的 ETF 信号策略回测闭环（含收益曲线）
- A 股横截面轮动（Top N 月度调仓）回测闭环（含收益曲线）
- 指标计算与结果页组装
- `strategy_schema/backtest_result/equity_curve/report` Artifact 落盘

进行中：

- Session State 与 Artifact 引用统一化
- API / UI 对接与结果展示

## 2. 当前设计基础

截至目前，项目已经有了比较完整的设计文档体系，核心包括：

- [产品蓝图](docs/product_blueprint.md)
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

这意味着我们现在不缺方向，缺的是一条低返工、可启动的实施顺序。

## 3. 实施总原则

### 原则 1：先打通主链路，再补厚能力

第一版最重要的不是支持最多策略，而是打通这条链路：

- 用户问题
- 策略解析
- 澄清收敛
- 生成策略对象
- 回测执行
- 结果解释
- 收益曲线展示

### 原则 2：先实现 ADK 主骨架，再填充金融能力

如果没有先把 ADK Runner / Session / State / Artifact 主骨架立起来，后面再补会很痛苦。

### 原则 3：先支持最典型场景

第一版建议只优先打透两类场景：

- ETF 技术指标策略
- A 股月度横截面选股策略

### 原则 4：确定性能力优先做成 Tool

例如：

- 数据访问
- 回测执行
- 指标计算

### 原则 5：前端和复杂展示可以先简化，但收益曲线不能省

这是第一版结果页的硬要求。

## 4. 推荐实施阶段

第一版建议分成 6 个阶段推进。

1. 项目骨架阶段
2. 数据与 Tool 基础阶段
3. ADK 主链路阶段
4. 回测闭环阶段
5. 结果页与 Artifact 阶段
6. 稳定性与 MVP 收口阶段

## 5. 阶段 1：项目骨架阶段

### 目标

先把当前项目从“只有文档和数据”变成“有基本 Python / ADK 工程骨架”的状态。

### 必做项

- 建立基础目录结构
- 建立 `uv` 驱动的运行入口
- 建立最小 ADK app / runner 入口
- 建立配置模块
- 建立数据路径常量模块

### 建议目录

```text
strategy_agent/
  __init__.py
  app.py
  config.py
  agents/
  tools/
  domain/
  data_access/
  schemas/
  services/
```

### 阶段产出

- 可以启动一个最小 ADK Runner
- 可以创建 Session
- 可以承载顶层 Orchestrator Agent

## 6. 阶段 2：数据与 Tool 基础阶段

### 目标

先把所有确定性基础能力做出来，给 ADK 编排层提供可用工具。

### 必做项

- 实现 `data_access/storage.py`
- 实现 `data_access/normalize.py`
- 实现 `domain/market_data.py`
- 实现 `InstrumentResolveTool`
- 实现 `MarketDataQueryTool`
- 实现 `StrategyValidationTool`

### 当前优先级最高的数据接口

- `get_bar_frame(...)`
- `get_daily_basic_frame(...)`
- `get_latest_trade_date()`
- `get_benchmark_frame(...)`

### 阶段产出

- 可以稳定读取 ETF、股票、指数、daily_basic 数据
- 可以对 Strategy Schema 做基础字段校验

## 7. 阶段 3：ADK 主链路阶段

### 目标

把 Google ADK 的主编排骨架真正跑起来。

### 必做项

- 实现 `ResearchOrchestratorAgent`
- 实现 `StrategyParsingAgent`
- 建立 Session State 初始化逻辑
- 建立 Artifact 保存基础能力
- 实现澄清 loop 的最小版本

### 这一阶段的重点

不是回测本身，而是：

- 用户输入后，系统能形成策略草案
- 能判断是否需要澄清
- 能把澄清结果收敛成 Strategy Schema

### 建议优先支持的澄清能力

- 标的识别
- 卖出逻辑缺失
- 持仓数量缺失
- 持有周期缺失

### 阶段产出

- 能从自然语言稳定生成 `strategy_schema`
- 能在 ADK Session 中保存 State
- 能生成 `strategy_schema` Artifact

## 8. 阶段 4：回测闭环阶段

### 目标

实现最小可用回测闭环。

### 必做项

- 实现 `BacktestRunTool`
- 实现 `MetricsComputeTool`
- 跑通 ETF MACD 策略
- 跑通月度大市值前 20 轮动策略

### 推荐顺序

#### 先做 ETF 技术策略

原因：

- 单标的逻辑最简单
- 数据量小
- 最适合先验证收益曲线和指标链路

#### 再做横截面轮动策略

原因：

- 能验证 `daily_basic` 和调仓逻辑
- 能验证组合持仓与换手率统计

### 阶段产出

- 能输出回测净值序列
- 能输出最大回撤、年化收益、夏普等指标
- 能生成收益曲线数据

## 9. 阶段 5：结果页与 Artifact 阶段

### 目标

把“有回测结果”提升成“有完整研究结果页”。

### 必做项

- 实现 `ResultExplanationAgent`
- 实现 `ReportAssemblyTool`
- 生成 `backtest_result` Artifact
- 生成 `equity_curve` Artifact
- 生成 `report` Artifact

### 第一版必须做到

- 结果里一定有收益曲线
- 结果里一定有结论摘要
- 结果里一定有风险提示

### 阶段产出

- 一个完整的结果对象
- 支持对外展示的收益曲线和核心指标
- 支持多轮研究继续追问

## 10. 阶段 6：稳定性与 MVP 收口阶段

### 目标

在主链路跑通后，补足稳定性和最小可交付性。

### 必做项

- 增加最小测试集
- 增加示例问题集
- 增加错误处理与失败分支
- 校正默认值透明展示
- 检查 State / Artifact 恢复能力

### 推荐优先测试的场景

- ETF MACD 金叉死叉
- ETF RSI
- 每月买入市值最大的 20 只股票
- 60 日新高筛选后固定持有
- 卖出规则缺失的澄清场景
- 标的歧义场景

### 阶段产出

- 一个可以实际演示的研究型 MVP

## 11. 第一版最小可运行版本定义

如果只做一个最小但完整的版本，建议它必须包含：

### 输入侧

- 自然语言提问
- 至少一个澄清问题能力

### 中间层

- Strategy Schema 生成
- Session State 保存
- Strategy Schema Artifact 保存

### 执行侧

- ETF 单标的回测
- A 股月度横截面轮动回测

### 输出侧

- 年化收益
- 最大回撤
- 夏普比率
- 年度收益表
- 回测收益曲线
- 解释摘要

如果这几项都做到了，就已经是一个真正意义上的第一版产品，而不是 demo 碎片。

## 12. 哪些能力可以后置

为了避免第一版过重，以下内容建议后置。

### 可后置 1：复杂 Memory

- 先不做重型长期记忆

### 可后置 2：MCP 深度接入

- 先预留接口，不急着接多个外部源

### 可后置 3：复杂多 Agent 并行

- 先以一个主编排 Agent 为核心

### 可后置 4：复杂可视化

- 第一版先把收益曲线和回撤曲线做好

### 可后置 5：数据维护自动化迁移

- 当前项目先消费已有本地数据
- 数据自动更新体系后续再迁入

## 13. 推荐实现顺序清单

下面是一条更贴近开发任务的顺序。

1. 建立 Python 包结构和 ADK 启动入口
2. 建立配置模块与数据路径模块
3. 实现基础数据访问层
4. 实现 `InstrumentResolveTool`
5. 实现 `StrategyValidationTool`
6. 实现 `StrategyParsingAgent`
7. 实现 `ClarificationDecisionTool`
8. 实现 `ResearchOrchestratorAgent` 的澄清闭环
9. 实现 `BacktestRunTool` 的 ETF 版本
10. 实现 `MetricsComputeTool`
11. 实现收益曲线输出
12. 实现 `ResultExplanationAgent`
13. 实现 `ReportAssemblyTool`
14. 扩展到横截面组合策略
15. 增加 State / Artifact 恢复和回归测试

## 14. 依赖顺序建议

为了少返工，建议依赖关系按下面理解。

### 基础依赖

- 配置
- 数据路径
- 数据访问

### 中层依赖

- Strategy Schema
- Tool Contracts
- State / Artifact

### 编排依赖

- Orchestrator Agent
- Parsing Agent
- Explanation Agent

### 执行依赖

- Backtest Tool
- Metrics Tool
- Report Assembly

也就是说：

- 不要在数据访问层没定好的时候急着写 Backtest Tool
- 不要在 Tool Contract 没定好的时候急着拼 Agent

## 15. 第一版里程碑建议

### Milestone 1：Schema 可收敛

完成标准：

- 自然语言问题可以生成 Strategy Schema
- 澄清逻辑可运行

### Milestone 2：ETF 回测跑通

完成标准：

- ETF 策略可输出收益曲线和基础指标

### Milestone 3：结果页闭环

完成标准：

- 有结论摘要
- 有收益曲线
- 有风险提示

### Milestone 4：组合策略跑通

完成标准：

- 月度横截面轮动可运行

### Milestone 5：MVP 可演示

完成标准：

- 两类核心场景稳定可用
- 多轮追问可基本恢复上下文

## 16. 角色与模块优先级

如果开始真实开发，我建议优先级如下：

### P0

- ADK Runner / Session / State 主骨架
- Strategy Schema 收敛
- ETF 回测
- 收益曲线

### P1

- 横截面组合回测
- Artifact 体系
- 结果解释 Agent

### P2

- Memory 偏好
- MCP 扩展位
- 更复杂结果页

## 17. 这一轮之后最适合继续补的文档

如果还要继续完善文档，我建议再补两份轻量文档：

1. `mvp_scope_checklist_v1.md`
2. `repository_scaffold_v1.md`

第一份用于把“必须做 / 可后置”列成清单；
第二份用于把项目代码目录结构先定下来。

## 18. 结论

当前项目已经不再缺“设计方向”，而是进入“如何有节奏地开始实现”的阶段。

最推荐的做法不是一口气把所有东西都写出来，而是：

- 先把 ADK 主骨架立住
- 再把数据与 Tool 基础打牢
- 再跑通 ETF 回测闭环
- 最后扩到组合策略和更丰富的结果页

这样最稳，也最符合我们当前已经形成的设计约束。
