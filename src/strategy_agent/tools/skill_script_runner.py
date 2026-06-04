from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from strategy_agent.config import PROJECT_ROOT, SRC_ROOT
from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse


SCRIPTS_ROOT = PROJECT_ROOT / "skills" / "quant_backtest_cn" / "scripts"


@dataclass(frozen=True)
class AllowedScript:
    file_name: str
    allowed_args: frozenset[str] = frozenset()
    timeout_seconds: int = 120


ALLOWED_SCRIPTS: dict[str, AllowedScript] = {
    "validate_schema": AllowedScript("validate_schema.py", frozenset({"schema_json"}), 30),
    "run_backtest": AllowedScript("run_backtest.py", frozenset({"schema_json"}), 120),
    "smoke_macd_510300": AllowedScript("smoke_macd_510300.py", frozenset(), 120),
    "smoke_rotation_top20": AllowedScript("smoke_rotation_top20.py", frozenset(), 120),
}


def run_allowed_skill_script(script_name: str, args: dict[str, Any] | None = None) -> ToolResponse[dict]:
    """Run a whitelisted quant skill script with bounded arguments."""

    script = ALLOWED_SCRIPTS.get(_normalize_script_name(script_name))
    if not script:
        return ToolResponse(
            ok=False,
            error=ToolError(
                code="script_not_allowed",
                message="只能执行白名单中的固定脚本",
                details={"script_name": script_name, "allowed_scripts": sorted(ALLOWED_SCRIPTS)},
            ),
        )

    try:
        command = _build_command(script, args or {})
        started = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=SCRIPTS_ROOT,
            env=_script_env(),
            text=True,
            capture_output=True,
            timeout=script.timeout_seconds,
            check=False,
        )
    except TimeoutError:
        return _script_error("script_timeout", "脚本执行超时", script, args or {})
    except ValueError as exc:
        return _script_error("invalid_script_args", str(exc), script, args or {})
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return _script_error("script_execution_failed", str(exc), script, args or {})

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    data = {
        "script_name": script.file_name,
        "return_code": completed.returncode,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "stdout": stdout,
        "stderr": stderr,
        "parsed_json": _parse_json_stdout(stdout),
    }
    if completed.returncode != 0:
        return ToolResponse(
            ok=False,
            data=data,
            error=ToolError(code="script_returned_error", message="固定脚本执行失败", details=data),
        )
    return ToolResponse(ok=True, data=data, meta={"runner": "whitelisted_skill_script"})


def _normalize_script_name(script_name: str) -> str:
    name = script_name.removeprefix("scripts/")
    return name.removesuffix(".py")


def _build_command(script: AllowedScript, args: dict[str, Any]) -> list[str]:
    unknown_args = sorted(set(args) - set(script.allowed_args))
    if unknown_args:
        raise ValueError(f"脚本参数不在白名单内：{', '.join(unknown_args)}")

    command = [sys.executable, str(SCRIPTS_ROOT / script.file_name)]
    if "schema_json" in args:
        command.extend(["--schema-json", _json_arg(args["schema_json"])])
    return command


def _json_arg(value: Any) -> str:
    if isinstance(value, str):
        json.loads(value)
        return value
    return json.dumps(value, ensure_ascii=False)


def _script_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_ROOT) if not existing else f"{SRC_ROOT}{os.pathsep}{existing}"
    return env


def _parse_json_stdout(stdout: str) -> Any:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def _script_error(code: str, message: str, script: AllowedScript, args: dict[str, Any]) -> ToolResponse[dict]:
    return ToolResponse(
        ok=False,
        data={"script_name": script.file_name, "args": sorted(args)},
        error=ToolError(code=code, message=message),
    )


__all__ = ["ALLOWED_SCRIPTS", "run_allowed_skill_script"]
