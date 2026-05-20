# ADK 系统架构 V1

## 1. 文档目标

这份文档用于定义第一版系统如何基于 Google ADK 来组织整体架构。

它回答的问题是：

- 整个系统在 ADK 中由哪些核心对象组成
- 哪些能力应该建成 Agent，哪些应该建成 Tool
- Session、State、Memory、Artifact 如何协作
- 如何利用 ADK 的 sub-agent、sequential、loop、回调、人机交互、MCP 等能力

这份文档的核心目标是确保我们不是“做完一个普通应用后再套一层 ADK”，而是从一开始就按 ADK Native 的方式设计。

## 2. 一个前提

当前项目必须充分利用 Google ADK，而不是只使用其中最基础的 `Agent + Tool` 两个抽象。

第一版虽然不追求把所有高级能力都做满，但在架构设计上必须为下面这些能力预留明确位置：

- Session
- State
- Memory
- Artifact / 文件管理
- Sub-agent
- Sequential orchestration
- Loop orchestration
- 回调函数
- 人机交互
- MCP Toolset
- Plugin / 可插拔扩展

这条原则非常重要，因为它决定了系统是否能从“单轮问答工具”成长为“长期可扩展的研究工作台”。

## 3. ADK Native 架构原则

第一版系统建议遵守以下原则。

### 原则 1：顶层流程由 Agent 编排，不由外部脚本拼接

用户从提问到拿到结果的主链路，应该由 ADK Agent 负责编排，而不是由外部 Python 代码硬编码成一串调用。

### 原则 2：确定性计算尽量下沉到 Tool

例如：

- 数据读取
- 标的解析
- Schema 校验
- 回测执行
- 指标计算

这些模块都更适合作为 Tool 或普通库。

### 原则 3：状态和上下文尽量使用 ADK Session / State 管理

不要在 ADK 外侧再平行发明一套会话状态系统作为主实现。

### 原则 4：中间产物尽量沉淀为 Artifact

例如：

- 策略卡
- 结构化策略对象
- 回测结果 JSON
- 收益曲线图片
- 报告 Markdown / HTML

这些都应该尽量按 Artifact 管理，而不是散落在临时变量里。

### 原则 5：人机交互必须是主链路的一部分

澄清问题、默认值确认、关键分支选择，不应该被视为“异常处理”，而应该是编排流程中的正式节点。

## 4. 第一版系统分层

第一版建议系统分成 5 层。

1. 对话与交互层
2. Agent 编排层
3. Tool 能力层
4. 数据与回测域层
5. 存储与产物层

## 5. 第一版核心 ADK 对象映射

## 5.1 `Runner`

角色：

- 整个应用运行入口

职责：

- 承载顶层 Agent
- 绑定 Session / Memory / Artifact 服务
- 处理事件流
- 组织插件与工具注册

第一版建议：

- 使用统一 Runner 作为对话研究入口

## 5.2 `Session`

角色：

- 一次用户研究会话的容器

会话中应包含：

- 当前用户问题
- 已生成的策略草案
- 已确认的澄清结果
- 最终策略对象
- 已运行的回测结果
- 后续追问历史

Session 是研究过程的主上下文，不只是聊天记录。

## 5.3 `State`

角色：

- 保存当前会话中的结构化运行状态

第一版建议把以下内容放入 State：

- `current_query`
- `problem_type`
- `clarification_status`
- `strategy_draft`
- `strategy_schema`
- `backtest_status`
- `result_summary`
- `defaulted_fields`

## 5.4 `Memory`

角色：

- 保存跨轮对话可复用的研究偏好和上下文记忆

第一版建议 Memory 先聚焦轻量能力：

- 用户常用市场偏好
- 用户是否习惯看 ETF / 股票
- 用户是否更偏好默认基准展示
- 用户常用默认回测区间偏好

说明：

- 第一版不必把 Memory 做得很重
- 但必须从架构上预留位置

## 5.5 `Artifact`

角色：

- 保存研究过程中的结构化输出与文件输出

第一版建议重点沉淀的 Artifact：

- `strategy_card.json`
- `strategy_schema.json`
- `backtest_result.json`
- `equity_curve.png` 或图表数据对象
- `report.md`

如果后续前端采用 API 驱动，也可以让 Artifact 既包含文件，也包含结构化对象引用。

## 6. 第一版 Agent 拆分

第一版建议采用“一个顶层编排 Agent + 少量领域子 Agent + 多个确定性 Tool”的结构。

## 6.1 顶层 Agent：Research Orchestrator Agent

这是系统主脑。

职责：

- 识别用户意图是否属于策略研究
- 决定当前是否需要澄清
- 组织策略解析
- 调用回测与结果解释流程
- 管理多轮研究上下文

它不应直接承担所有计算细节，而是负责“流程决策”。

## 6.2 子 Agent：Strategy Parsing Agent

职责：

- 把自然语言问题转成策略草案
- 识别问题对应的策略类型
- 提取 Schema 关键字段
- 标记缺失字段和默认字段候选

它的输出应是结构化草案，而不是最终自然语言回复。

## 6.3 子 Agent：Result Explanation Agent

职责：

- 读取回测结果
- 结合收益曲线、回撤和指标生成解释
- 组织结论摘要、风险提示和局限性说明

它更偏分析和表达，因此适合作为独立 Agent。

## 6.4 可选子 Agent：Research Follow-up Agent

第一版不是必须实现，但建议在架构中预留。

职责：

- 处理“那如果把月度改成季度呢”
- 处理策略克隆、参数修改、再回测
- 帮助用户在已有结果上继续研究

## 7. 第一版 Tool 拆分

## 7.1 Instrument Resolve Tool

职责：

- 把“沪深300ETF”“平安银行”这类自然语言标的解析为统一代码

输入：

- 用户文本中的标的描述

输出：

- 标准证券代码
- 识别置信度
- 候选列表

## 7.2 Strategy Validation Tool

职责：

- 校验 `Strategy Schema V1`
- 判断字段完整性
- 输出缺失字段与非法字段

它是澄清流程的关键基础工具。

## 7.3 Clarification Decision Tool

职责：

- 结合 `clarification_rules_v1.md`
- 把缺失字段分类为：
  - 必须追问
  - 可默认补全
  - 可直接执行

说明：

- 这个能力也可以内嵌在顶层 Agent 逻辑中
- 但从架构可维护性看，抽成独立工具更清晰

## 7.4 Market Data Query Tool

职责：

- 从本地数据目录读取 ETF / 股票 / 指数 / daily_basic 数据

输入：

- 标的
- 字段
- 时间范围

输出：

- 可供回测和指标计算使用的标准化数据对象

## 7.5 Backtest Run Tool

职责：

- 接收完整策略对象
- 按 `backtest_assumptions_v1.md` 执行回测
- 返回结构化结果

这是第一版最关键的确定性执行工具。

## 7.6 Metrics Compute Tool

职责：

- 从净值序列和交易记录中计算：
  - 年化收益
  - 最大回撤
  - 夏普
  - 胜率
  - 年度收益

## 7.7 Report Assembly Tool

职责：

- 把策略卡、指标、收益曲线数据、解释结果整合为前端可消费对象

## 8. 如何使用 Sub-agent

你提到的重点非常对，ADK 的 sub-agent 能力必须充分利用。

第一版建议的使用方式是：

- 顶层 Orchestrator 负责编排
- Strategy Parsing Agent 专注“理解并结构化”
- Result Explanation Agent 专注“解释并表达”

这样做的好处：

- 各 Agent 关注点单一
- 容易评估每一步输出质量
- 后续增加更多研究型子 Agent 更自然

## 9. 如何使用 SequentialAgent

ADK 的 `SequentialAgent` 很适合我们的主链路。

第一版建议把这条固定流水线设计为 sequential：

1. 解析用户问题
2. 校验字段完整性
3. 判断是否澄清
4. 生成策略对象
5. 运行回测
6. 计算指标
7. 解释结果
8. 组装最终响应

说明：

- 并不是所有步骤都必须由不同 Agent 实现
- 但逻辑上应当按 sequential pipeline 建模

## 10. 如何使用 LoopAgent

ADK 的 `LoopAgent` 非常适合处理“澄清直到足够完整”为止的循环。

第一版建议把澄清流程建模成 loop：

1. 读取当前策略草案
2. 检查缺失字段
3. 如果存在必须追问项，则向用户发起问题
4. 读取用户回答并更新草案
5. 再次校验
6. 直到策略达到可执行条件后退出 loop

这比把澄清写成零散的 if/else 更自然，也更贴近产品交互。

## 11. 如何使用 ParallelAgent

第一版不建议大规模依赖 parallel 作为主流程，但可以预留以下使用点：

- 并行生成多个解释视角
- 并行准备多个可选基准
- 并行对比不同参数版本的策略结果

第一版主链路仍以 sequential 为主、loop 为辅。

## 12. 如何使用回调函数

ADK 的回调能力很适合研究产品中的过程感知和状态更新。

第一版建议主要用于：

- 在解析完成后写入 State
- 在回测开始前更新 `backtest_status`
- 在回测结束后保存 Artifact
- 在结果解释阶段记录关键摘要

后续如果前端支持流式反馈，回调还可以用于：

- 进度事件推送
- 中间状态可视化
- 过程日志记录

## 13. 如何使用人机交互能力

ADK 里的人机交互能力不能只用于“最后确认”。

第一版建议至少在以下场景使用：

- 澄清策略关键字段
- 确认是否接受默认值
- 在多个可识别标的中让用户选择
- 在超范围时给用户替代路径

特别重要的一点：

- 人机交互不是打断流程，而是流程本身

如果使用 ADK 的选择型工具，例如 `get_user_choice` 一类能力，这一层会更稳定。

## 14. 如何使用 Artifact / 文件管理

你提到的文件管理也非常关键。

第一版建议把 Artifact 视为“研究资产容器”，而不只是附件。

建议沉淀的对象：

- 策略卡 JSON
- 最终 Strategy Schema
- 回测结果 JSON
- 收益曲线图或图表数据
- 结果摘要 Markdown

这样做的价值：

- 会话可以恢复
- 结果可以复用
- 后续可以导出或分享
- ADK 内部状态和前端展示之间更容易打通

## 15. 如何使用 Memory

ADK Memory 的价值不在于“存所有聊天记录”，而在于记住研究偏好。

第一版建议记住：

- 用户常研究的市场范围
- 用户是否更常看 ETF 或股票
- 用户是否习惯默认展示基准
- 用户是否偏好更长或更短的默认回测区间

第二版以后再考虑：

- 用户常用策略模板
- 历史研究结论索引
- 可检索的研究知识库

## 16. 如何使用 MCP Toolset

你提到 MCP 很重要，这点我完全同意。

第一版架构必须预留 MCP 接入层，即使第一版不把所有能力都接满。

建议把 MCP 的角色定义为：

- 外部数据源接入
- 外部研究工具接入
- 外部知识库接入

未来可接入的方向包括：

- 实时或补充金融数据
- 研究文档知识库
- 团队协作系统
- 报告生成与分发工具

在 ADK 中，MCP 更适合作为 Toolset 层的外部扩展面，而不是替代主业务逻辑。

## 17. 如何使用 Plugin

第一版建议把 Plugin 用作横切能力扩展，而不是主业务编排。

适合做成 Plugin 的内容：

- 调试日志
- 反思与重试
- 统一观测
- 结果审计

这样主业务 Agent 可以保持相对干净。

## 18. 一条推荐的 ADK 执行链路

下面是一条更贴近 ADK 的主执行链路：

1. `Runner` 接收用户请求
2. 创建或恢复 `Session`
3. 顶层 `Research Orchestrator Agent` 读取 `State`
4. 调用 `Strategy Parsing Agent`
5. 调用 `Strategy Validation Tool`
6. 进入 `LoopAgent` 做澄清，直到字段完整
7. 生成并保存 `strategy_schema` Artifact
8. 调用 `Backtest Run Tool`
9. 调用 `Metrics Compute Tool`
10. 保存 `backtest_result` 和 `equity_curve` Artifact
11. 调用 `Result Explanation Agent`
12. 调用 `Report Assembly Tool`
13. 输出最终响应并更新 Session State / Memory

## 19. 状态对象建议

第一版建议在 Session State 中维护如下关键对象：

```json
{
  "current_query": "",
  "problem_type": "",
  "clarification_needed": true,
  "missing_fields": [],
  "defaultable_fields": [],
  "strategy_draft": {},
  "strategy_schema": {},
  "backtest_status": "idle",
  "backtest_result_ref": null,
  "artifacts": {
    "strategy_schema": null,
    "backtest_result": null,
    "equity_curve": null,
    "report": null
  }
}
```

## 20. 第一版边界控制

虽然 ADK 很强大，但第一版仍应克制。

第一版建议：

- 必用 Session / State / Artifact
- 必用 sub-agent
- 必用 sequential + loop
- 必预留 MCP 扩展位
- 适度使用回调和人机交互

第一版暂不建议：

- 复杂网状多 Agent 自主协作
- 大规模并行研究分支
- 重型长期记忆系统
- 过深的插件链

## 21. 这份文档对后续实现的约束

从现在开始，后续实现设计都要回答：

1. 这个模块在 ADK 里是 Agent、Tool、Session、Artifact、Memory 还是 Plugin
2. 它的输入输出是什么
3. 它在主流程中的顺序是什么
4. 它是否应进入 sequential / loop / human-in-the-loop 节点

如果答不上来，说明该设计还不够 ADK Native。

## 22. 下一步建议

基于这份文档，下一步最适合继续写的是：

1. `adk_agent_topology_v1.md`
2. `data_access_architecture_v1.md`

因为系统框架已经明确，接下来最该继续下沉的是：

- 每个 Agent 的职责边界
- 每个 Tool 的输入输出契约
- 数据访问层如何给 Backtest Tool 稳定供数
