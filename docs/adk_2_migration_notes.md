# ADK 2.0 改造说明

本文记录当前项目从 ADK 1.x 风格迁移到 ADK 2.0 后的主实现。旧的设计文档中仍可能出现 `SequentialAgent`，那些内容保留为历史设计参考；当前代码以本文件和 `docs/agent_orchestration_flow.md` 为准。

## 当前主链路

- API 层通过 `build_runner()` 创建 ADK `Runner`。
- `Runner` 使用 ADK 2.0 `App` 包装根 Agent。
- 根 Agent 是 `ResearchOrchestratorAgent`，类型为 ADK 2.0 `Workflow`。
- 主流程为：意图分类、澄清判断、策略设计、数据研究、策略执行、结果解释。
- LLM Agent 负责理解、结构化和解释；确定性 Agent 负责数据检查与回测执行。

## 已接入的 ADK 2.0 能力

- `google.adk.apps.App`：统一承载 root agent，符合 ADK 2.0 Runner 初始化方式。
- `google.adk.workflow.Workflow`：替代历史设计中的 `SequentialAgent`，用显式边表达顺序编排。
- `FileArtifactService`：Runner 已接入 ADK artifact 服务，路径为 `settings.adk_artifact_root`。
- Session state：LLM Agent 通过 `output_key` 写入结构化结果；后续 Agent 从 state 读取，不再依赖私有 event API。
- Event state delta：流式事件适配器会解析 `event.actions.state_delta`，结果收集器从 state delta 中同步结构化结果。
- `SkillToolset`：`skills/quant_backtest_cn` 已作为 ADK SkillToolset 接入 `StrategyDesignerAgent`，用于沉淀量化回测约定、Schema 和脚本资产。

## 依赖变化

- `google-adk==2.0.0`
- `google-cloud-storage>=3.0.0`：ADK 2.0 skills 模块依赖。
- `pyarrow>=24.0.0`：本地 parquet 数据读取依赖，显式声明避免环境隐式依赖。
- `pytest>=9.0.3`：放入 dev dependency，确保 `uv run pytest` 使用项目虚拟环境。

## 暂未改造的部分

- 前端结果页仍继续读取项目自己的 `/artifacts/{session_id}/{artifact_name}` 路径；ADK artifact 服务已接入 Runner，但还没有替代前端现有 artifact 加载方式。
- `.agents/skills/tushare` 暂未接入主链路，避免在线数据补齐影响当前交互稳定性。
- `DataResearchAgent` 仍是确定性数据检查 Agent；后续可以把因子规划、数据补齐计划沉淀为独立 Skill 或 Agent。
- Trace 页面目前展示项目侧采集的 run/tool/token 信息，尚未完全做成 ADK Dev UI 风格的 waterfall 明细页。

## 验证命令

```bash
PYTHONPATH=src uv run pytest -q
```

当前预期：全部测试通过，仅保留第三方库 warning。
