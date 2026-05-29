from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from strategy_agent.tools.strategy_validation import validate_strategy_schema


def _load_schema(args: argparse.Namespace) -> dict[str, Any]:
    if args.schema_json:
        return json.loads(args.schema_json)
    if args.schema_file:
        return json.loads(Path(args.schema_file).read_text())
    raise SystemExit("Provide --schema-json or --schema-file")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate StrategySchema v1.")
    parser.add_argument("--schema-json")
    parser.add_argument("--schema-file")
    args = parser.parse_args()

    response = validate_strategy_schema(_load_schema(args))
    print(json.dumps(response.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
