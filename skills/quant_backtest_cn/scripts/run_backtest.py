from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from strategy_agent.tools.backtest_run import run_backtest
from strategy_agent.tools.metrics_compute import compute_metrics
from strategy_agent.tools.report_assembly import assemble_result_page
from strategy_agent.tools.strategy_validation import validate_strategy_schema


def _load_schema(args: argparse.Namespace) -> dict[str, Any]:
    if args.schema_json:
        return json.loads(args.schema_json)
    if args.schema_file:
        return json.loads(Path(args.schema_file).read_text())
    raise SystemExit("Provide --schema-json or --schema-file")


def _default_explanations(schema: dict[str, Any], metrics: dict[str, Any]) -> dict[str, str]:
    name = schema.get("name") or "策略"
    annual = ((metrics.get("return_metrics") or {}).get("annualized_return") or 0.0) * 100
    drawdown = ((metrics.get("risk_metrics") or {}).get("max_drawdown") or 0.0) * 100
    return {
        "summary_text": f"{name} 回测完成，年化收益约 {annual:.2f}%，最大回撤约 {drawdown:.2f}%。",
        "risk_text": "回测结果基于历史数据，不代表未来表现。",
        "limitations_text": "当前结果未构成投资建议，仍需结合交易成本、流动性和参数稳定性复核。",
    }


def _run(schema: dict[str, Any]) -> dict[str, Any]:
    validation = validate_strategy_schema(schema)
    if not validation.ok or not (validation.data or {}).get("is_complete"):
        return {"ok": False, "stage": "validate_schema", "validation": validation.model_dump()}

    backtest = run_backtest(schema)
    if not backtest.ok:
        return {"ok": False, "stage": "run_backtest", "backtest": backtest.model_dump()}

    metrics = compute_metrics(backtest.data or {})
    if not metrics.ok:
        return {"ok": False, "stage": "compute_metrics", "metrics": metrics.model_dump()}

    report = assemble_result_page(
        strategy_schema=schema,
        backtest_result=backtest.data or {},
        metrics=metrics.data or {},
        explanations=_default_explanations(schema, metrics.data or {}),
    )
    if not report.ok:
        return {"ok": False, "stage": "assemble_result_page", "report": report.model_dump()}

    return {
        "ok": True,
        "data": {
            "validation": validation.data,
            "backtest": backtest.data,
            "metrics": metrics.data,
            "result_page": (report.data or {}).get("result_page"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a StrategySchema v1 backtest.")
    parser.add_argument("--schema-json")
    parser.add_argument("--schema-file")
    parser.add_argument("--output-file")
    args = parser.parse_args()

    result = _run(_load_schema(args))
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output_file:
        Path(args.output_file).write_text(output)
    print(output)
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
