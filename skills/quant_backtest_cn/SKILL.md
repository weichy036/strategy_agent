---
name: quant-backtest-cn
description: Use this skill when converting Chinese natural-language investment ideas into StrategySchema v1, validating assumptions, running reproducible local backtests, and explaining CN market backtest results with equity curves.
metadata:
  adk_additional_tools: []
---

# Quant Backtest CN

This skill defines the stable workflow for Chinese-market quantitative strategy research in Strategy Agent.

Use this skill when the user asks questions such as:

- "沪深300ETF，MACD 日线金叉买入、死叉卖出，每年平均收益是多少？"
- "每个月买入市值最大的 20 只股票，持有到下个月，收益是多少？"
- "证券 ETF 均线择时策略效果怎么样？"

## Core Rule

Do not let the model freely improvise execution order. The model should understand and structure the strategy, while deterministic tools or scripts execute the backtest.

Stable order:

1. Classify intent.
2. Decide whether clarification is truly required.
3. Produce StrategySchema v1.
4. Validate StrategySchema.
5. Run backtest.
6. Compute metrics.
7. Assemble result page with equity curve.
8. Explain results and limitations.

## Clarification Policy

Only ask the user when a blocking field is truly absent.

Blocking fields:

- Target instrument or universe.
- Buy rule.
- Sell rule.
- Ranking factor.
- Position count.
- Holding period.
- Rebalance rule.

Do not ask for defaultable fields:

- Backtest start date.
- Backtest end date.
- Daily frequency.
- Commission.
- Slippage.
- Next-open execution timing.
- Currency wording.
- Metric wording such as "average yearly return".

Common Chinese instrument names such as 沪深300ETF, 中证500ETF, 创业板ETF, 证券ETF, 红利ETF should be resolved by tools rather than pushed back to the user.

## Supported Strategy Types

Current engine-supported `strategy_type` values:

- `signal_trading`
- `rule_based_timing`
- `cross_sectional_rotation`

Do not invent other strategy types.

Use `signal_trading` for single-instrument technical timing strategies such as MACD, RSI, and moving-average crosses.

Use `cross_sectional_rotation` for monthly or periodic stock selection and rebalance strategies.

## Required Result

A completed result must include:

- Valid StrategySchema.
- Backtest result.
- Metrics.
- Result page.
- Non-empty equity curve series.
- Risk disclosure.

If the result page has no equity curve, the workflow is not completed.

## References

Read these references when needed:

- `references/strategy_schema_v1.md`
- `references/default_assumptions.md`
- `references/supported_strategies.md`
- `references/data_contract.md`
- `references/risk_disclosure.md`

## Scripts

Use scripts for deterministic verification:

- `scripts/validate_schema.py`
- `scripts/run_backtest.py`
- `scripts/smoke_macd_510300.py`
- `scripts/smoke_rotation_top20.py`

Prefer scripts over model-generated execution logic.
