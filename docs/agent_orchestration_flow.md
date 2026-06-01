# Agent 编排流程

这张图描述当前 TradeX / Strategy Agent 的主链路：用户用自然语言提出策略想法，系统通过 ADK 2.0 `Workflow` 编排多个 Agent，最终完成策略结构化、数据检查、回测执行、结果解释和 Trace 展示。

```mermaid
flowchart TB
    User["用户自然语言请求"] --> API["FastAPI /chat<br/>ADK Runner + Session"]

    API --> Orchestrator["ResearchOrchestratorAgent<br/>ADK 2.0 Workflow"]

    Orchestrator --> Intent["IntentClassifierAgent<br/>LLM Agent<br/>意图分类 / 是否可回测"]
    Intent --> Clarify["ClarificationAgent<br/>LLM Agent<br/>只澄清不可默认字段"]
    Clarify --> Designer["StrategyDesignerAgent<br/>LLM Agent<br/>生成 StrategySchema v1"]
    Designer --> DataResearch["DataResearchAgent<br/>BaseAgent<br/>检查本地数据与因子可用性"]
    DataResearch --> Execution["StrategyExecutionAgent<br/>BaseAgent<br/>确定性执行回测链路"]
    Execution --> Explain["ResultExplanationAgent<br/>LLM Agent<br/>解释结果与风险限制"]

    Explain --> Result["前端结果页<br/>收益曲线 / 指标 / 选股 / 交易 / Trace"]

    subgraph LLMAgents["LLM Agent 层"]
        Intent
        Clarify
        Designer
        Explain
    end

    subgraph DeterministicAgents["确定性 Agent 层"]
        DataResearch
        Execution
    end

    subgraph ExecutionTools["StrategyExecutionAgent 内部工具链"]
        V["validate_strategy_schema<br/>校验策略结构"]
        Q["query_market_data<br/>检查行情数据"]
        B["run_backtest<br/>执行回测"]
        M["compute_metrics<br/>计算收益/回撤/夏普"]
        R["assemble_result_page<br/>组装结果页 + artifacts"]
    end

    Execution --> V --> Q --> B --> M --> R

    subgraph Domain["回测与数据领域层"]
        Signal["signal_backtest<br/>单标的 MACD/RSI/均线"]
        Rotation["rotation_backtest<br/>横截面月度轮动"]
        MarketData["market_data / storage<br/>读取 parquet"]
        Selection["selection_daily<br/>截面选股数据"]
        Factors["factor_catalog<br/>因子字段映射"]
    end

    B --> Signal
    B --> Rotation
    Q --> MarketData
    DataResearch --> Factors
    DataResearch --> Selection
    DataResearch --> MarketData

    subgraph Artifacts["Artifacts"]
        Equity["equity_curve.svg"]
        TradeLog["trade_log.json"]
        SelectionLog["selection_log.json"]
    end

    R --> Equity
    R --> TradeLog
    R --> SelectionLog

    subgraph Observability["Trace / 可观测性"]
        LiveTrace["live_trace<br/>实时执行轨迹"]
        Collector["result_collector<br/>解析 ADK event / token usage"]
        Dashboard["Trace Dashboard<br/>waterfall / token / run detail"]
    end

    Intent -.event.-> Collector
    Clarify -.event.-> Collector
    Designer -.event.-> Collector
    DataResearch -.event.-> Collector
    Execution -.tool events.-> LiveTrace
    Explain -.event.-> Collector
    Collector --> Dashboard
    LiveTrace --> Dashboard

    subgraph Skills["Skill 资产"]
        QuantSkill["skills/quant_backtest_cn<br/>已通过 ADK SkillToolset 接入 StrategyDesignerAgent"]
        TushareSkill[".agents/skills/tushare<br/>Tushare 数据研究 skill"]
    end

    QuantSkill -.ADK SkillToolset.-> Designer
    Skills -.参考/待接入 SkillToolset.-> DataResearch

    subgraph Future["已预留但未主链路启用"]
        AgentTool["TraceableAgentTool<br/>Agent as Tool + 子 Agent trace"]
        TushareSkillToolset["ADK SkillToolset<br/>计划接入 tushare 数据研究"]
    end

    AgentTool -.未来可把 LLM 子 Agent 工具化.-> Orchestrator
    TushareSkillToolset -.未来提供数据研究技能工具.-> Orchestrator
```

## 当前说明

- 主编排方式是 ADK 2.0 `Workflow`，不是手写 if/else 流程。
- LLM Agent 负责理解、澄清、结构化和解释；确定性 Agent 负责数据检查和回测执行。
- `StrategyExecutionAgent` 内部工具链是稳定执行路径，避免让模型直接生成或运行任意代码。
- `skills/quant_backtest_cn` 已作为 ADK `SkillToolset` 接入 `StrategyDesignerAgent`。
- `.agents/skills/tushare` 当前仍作为数据研究 skill 资产，后续可接入数据补齐链路。
- `TraceableAgentTool` 已预留，用于未来把子 Agent 工具化并透传更细粒度 Trace。
