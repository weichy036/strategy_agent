# Quant Backtest CN Skill

This skill contains Strategy Agent's Chinese-market backtest knowledge base and deterministic scripts.

## Quick Checks

Validate a schema:

```bash
uv run python skills/quant_backtest_cn/scripts/validate_schema.py --schema-file strategy.json
```

Run a full local backtest:

```bash
uv run python skills/quant_backtest_cn/scripts/run_backtest.py --schema-file strategy.json --output-file result.json
```

Smoke test MACD on 510300.SH:

```bash
uv run python skills/quant_backtest_cn/scripts/smoke_macd_510300.py
```

Smoke test monthly top-20 market-cap rotation:

```bash
uv run python skills/quant_backtest_cn/scripts/smoke_rotation_top20.py
```

## Current Verification

- `smoke_macd_510300.py`: passes with a non-empty equity curve.
- `smoke_rotation_top20.py`: passes with a non-empty equity curve and yearly rows.

## ADK Usage Plan

Later, this folder should be loaded through ADK `SkillToolset`.

The skill teaches Agent how to structure and explain strategies, while scripts provide deterministic execution checks. The main product flow should still be orchestrated by `SequentialAgent`.
