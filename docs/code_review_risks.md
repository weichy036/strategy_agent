# 策略代理代码审查：风险清单

> 基于 2026-06-01 代码审查，按严重程度排序。

---

## P0 — 必须修复

### 1. `screen_and_hold` 策略类型验证通过但执行崩溃

`strategy_schema.py` 的 `strategy_type` 枚举包含 `"screen_and_hold"`，`validate_strategy_schema`（`strategy_validation.py`）会对此类型检查字段合法性并返回 `is_complete=true`。但 `run_backtest_for_strategy`（`domain/backtest.py:15`）不支持此类型，直接抛出 `ValueError`。

**流程后果：** 用户提问 → 意图分类 → 澄清 → 策略设计 → 数据检查 → 校验通过 → 执行阶段崩溃。

**建议：** 在 `validate_strategy_schema` 中对此类型返回 `is_complete=false`，或实现对应的回测引擎。

**涉及文件：**
- [src/strategy_agent/schemas/strategy_schema.py:125](../src/strategy_agent/schemas/strategy_schema.py#L125)
- [src/strategy_agent/domain/backtest.py:15](../src/strategy_agent/domain/backtest.py#L15)
- [src/strategy_agent/tools/strategy_validation.py:45-49](../src/strategy_agent/tools/strategy_validation.py#L45-L49)

---

### 2. 线程安全：单例 Runtime + 多线程 `asyncio.run()`

[agent_runtime.py:156-173](../src/strategy_agent/services/agent_runtime.py#L156-L173) 中的 `get_agent_runtime()` 返回全局单例 `AgentResearchRuntime`。两个 API 端点：
- 流式端点 `/research/stream`（[api.py:311](../src/strategy_agent/api.py#L311)）在每个请求中启动新线程，线程内调用 `asyncio.run()`
- 非流式端点 `/research/run`（[api.py:274](../src/strategy_agent/api.py#L274)）也调用 `asyncio.run()`

**风险：** 如果 ADK Runner 内部存在非线程安全状态（`InMemorySessionService`、`InMemoryArtifactService` 很可能不是线程安全的），并发请求会导致数据竞争或静默错误。

**建议：** 使用 `asyncio.Lock` 保护 runner，或为每个请求创建独立 Runner 实例。

**涉及文件：**
- [src/strategy_agent/services/agent_runtime.py:25-37](../src/strategy_agent/services/agent_runtime.py#L25-L37)
- [src/strategy_agent/api.py:274-308](../src/strategy_agent/api.py#L274-L308)
- [src/strategy_agent/api.py:310-341](../src/strategy_agent/api.py#L310-L341)

---

## P1 — 高优先级

### 3. 轮动回测现金追踪逻辑脆弱

[rotation_backtest.py:53-56](../src/strategy_agent/domain/rotation_backtest.py#L53-L56) 的回测主循环中，`_sell_all` 返回卖出后的现金，`_buy_targets` 不直接扣减 cash 而是按比例算 shares，最后用 `_cash_after_buys` 反向遍历 `trade_log` 倒推剩余现金。

`_cash_after_buys`（[rotation_backtest.py:139-146](../src/strategy_agent/domain/rotation_backtest.py#L139-L146)）反向遍历遇到第一个非 buy 条目就 break。如果某次调仓卖出后因流动性不足没有执行任何买入，break 逻辑会错误计算剩余现金。

**建议：** 重构让 `_buy_targets` 直接返回实际消耗现金，去除 `_cash_after_buys`。

**涉及文件：**
- [src/strategy_agent/domain/rotation_backtest.py:85-146](../src/strategy_agent/domain/rotation_backtest.py#L85-L146)

---

### 4. ADK 私有 API 强依赖

两个自定义 Agent（`DataResearchAgent` 和 `StrategyExecutionAgent`）通过 `ctx._get_events(current_invocation=True)` 读取前序 Agent 的输出：

- [data_research.py:100](../src/strategy_agent/agents/data_research.py#L100)
- [execution.py:64](../src/strategy_agent/agents/execution.py#L64)

`google-adk>=1.31.1` — ADK 升级后如果修改了 `_get_events` 的内部签名或行为，两个 Agent 会静默失效。

**建议：** 记录 ADK 版本依赖，升级时重点回归测试这两个 Agent。

---

### 5. 全量文件扫描性能瓶颈

多处操作会遍历整个 `daily_qfq` 目录下的所有 parquet 文件（当前 A 股约 5000+）：

- `ensure_selection_daily_frames()`（[selection_daily.py:100](../src/strategy_agent/data_access/selection_daily.py#L100)） — 按月构建选股数据
- `_price_cross_section()`（[selection_daily.py:227](../src/strategy_agent/data_access/selection_daily.py#L227)） — 每个交易日全量扫描
- `load_selection_monthly_sum()`（[selection_daily.py:141](../src/strategy_agent/data_access/selection_daily.py#L141)） — 每月全量扫描
- `ensure_selection_monthly_returns()`（[selection_daily.py:185](../src/strategy_agent/data_access/selection_daily.py#L185)） — 每月全量扫描

**算法复杂度：** O(n × m)（n=股票数，m=调仓次数）。跨越 5 年的月度轮动回测需要约 60 次全量扫描。

**建议：** 引入合并索引或改用单一合并 parquet 文件。

---

### 6. 第一根 K 线 NAV 系统性偏差

[signal_backtest.py:69](../src/strategy_agent/domain/signal_backtest.py#L69) 和 [rotation_backtest.py:66](../src/strategy_agent/domain/rotation_backtest.py#L66) 中，第一根 K 线的 NAV 固定为 1.0（初始资金 never 参与第一根 K 线的涨跌）。

在短回测周期（<60 个交易日）中，这个边界误差会导致总收益率被系统性压低，不可忽略。

---

## P2 — 中等优先级

### 7. 大量静默异常捕获

项目中存在多个 `except Exception: pass / continue / return None` 模式，错误被无声吞没：

| 位置 | 风险 |
|---|---|
| [report_assembly.py:77](../src/strategy_agent/tools/report_assembly.py#L77) | SVG 产物持久化失败无声 |
| [report_assembly.py:116,154](../src/strategy_agent/tools/report_assembly.py#L116) | JSON 持久化失败无声 |
| [selection_daily.py:102,143,186](../src/strategy_agent/data_access/selection_daily.py#L102) | 文件损坏时静默跳过，返回不完整数据 |
| [data_availability.py:177](../src/strategy_agent/services/data_availability.py#L177) | 损坏文件被判定为"不存在" |
| [backtest_run.py:20](../src/strategy_agent/tools/backtest_run.py#L20) | 回测异常丢失堆栈 |

[selection_daily.py:102](../src/strategy_agent/data_access/selection_daily.py#L102) 的 `except Exception: continue` 最危险：某个 parquet 文件损坏时静默跳过，调用方无法区分"数据不存在"和"数据读取失败"。

**建议：** 至少使用 `logger.exception()` 记录错误。

---

### 8. 状态键碎片化

策略 schema 在 ADK session state 中被写入多个 key，各阶段读取位置也不同：

| Agent | 写入 key |
|---|---|
| StrategyDesignerAgent | `strategy_schema_draft` |
| DataResearchAgent | `strategy_schema_draft`（可能覆盖）、`strategy.schema`、`data.executable_strategy_schema` |
| StrategyExecutionAgent 读取 | `data.executable_strategy_schema` **或** `strategy_schema_draft` |

**涉及文件：**
- [execution.py:27](../src/strategy_agent/agents/execution.py#L27)
- [data_research.py:61-68](../src/strategy_agent/agents/data_research.py#L61-L68)

**建议：** 统一使用 `strategy.schema` 一个 key 传递。

---

### 9. LLM JSON 输出解析的启发式回退

[structured_outputs.py:51-67](../src/strategy_agent/services/structured_outputs.py#L51-L67) 中，JSON 解析逐级回退：

```python
# 先尝试代码块提取
fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
# 回退：找第一个 { 和最后一个 }
start = text.find("{")
end = text.rfind("}")
```

当 LLM 输出包含嵌套大括号时，`rfind("}")` 可能匹配错误的层级。Pydantic 验证虽能捕获，但解析失败意味着整个 agent turn 的输出丢失。

---

### 10. Intent/Clarification Agent 缺少后置验证

[IntentClassifierAgent](.../src/strategy_agent/agents/intent_classifier.py) 和 [ClarificationAgent](.../src/strategy_agent/agents/clarification.py) 的 prompt 中有大量规则要求 LLM "不要因为默认值而追问"。但这些约束完全依赖 prompt，没有任何后置验证。LLM 在边界案例中可能不遵循规则，导致不必要的追问循环或信息收集不足。

---

## P3 — 低优先级

### 11. 年化收益率的交易日假定

[metrics_compute.py:30](../src/strategy_agent/tools/metrics_compute.py#L30) 固定使用 252 个交易日/年：

```python
annualized_return = (navs[-1] / navs[0]) ** (252 / max(periods - 1, 1)) - 1.0
```

未根据实际数据长度推算交易日数。对于跨多年的回测影响不大，但短周期内误差明显。

---

### 12. 夏普比率未扣除无风险利率

[metrics_compute.py:44](../src/strategy_agent/tools/metrics_compute.py#L44) 夏普比率计算中无风险利率为 0：

```python
sharpe = (mean_ret * 252) / volatility if volatility else 0.0
```

虽然这在 A 股量化回测中常见，但在无风险利率较高时期（如当前），夏普比率会被系统性高估。

---

### 13. API 端点无速率限制

[api.py](../src/strategy_agent/api.py) 中 `/research/run` 和 `/research/stream` 端点没有速率限制。每次调用都触发 LLM API 调用和全量数据读取，可能被恶意耗尽 LLM 配额。

---

### 14. 艺术作品路径穿越校验边界

[api.py:215-218](../src/strategy_agent/api.py#L215-L218) 的路径穿越防御正确使用 `resolve()` 对比，但 `session_id` 和 `artifact_name` 未做格式校验。如果 `settings.artifact_root` 下存在意外符号链接，可能绕过检查。

---

## 按文件汇总

| 文件 | 问题数 | 关键风险 |
|---|---|---|
| `domain/rotation_backtest.py` | 2 | 现金追踪逻辑、首 K 线 NAV |
| `domain/signal_backtest.py` | 1 | 首 K 线 NAV |
| `agents/execution.py` | 1 | ADK 私有 API |
| `agents/data_research.py` | 1 | ADK 私有 API |
| `data_access/selection_daily.py` | 2 | 全量扫描、静默异常 |
| `services/agent_runtime.py` | 1 | 线程安全 |
| `services/observability.py` | 0 | — |
| `services/structured_outputs.py` | 1 | JSON 解析回退 |
| `services/result_collector.py` | 0 | — |
| `services/data_availability.py` | 0 | — |
| `tools/strategy_validation.py` | 1 | screen_and_hold |
| `tools/report_assembly.py` | 1 | 静默异常 |
| `tools/backtest_run.py` | 1 | 静默异常 |
| `tools/metrics_compute.py` | 2 | 年化方法、夏普比率 |
| `schemas/strategy_schema.py` | 1 | screen_and_hold 枚举 |
| `api.py` | 3 | 线程安全、速率限制、路径穿越 |
