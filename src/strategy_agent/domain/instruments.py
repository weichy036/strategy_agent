from __future__ import annotations

import re
from pathlib import Path

from strategy_agent.config import settings
from strategy_agent.constants import DEFAULT_ETF_ALIASES, DEFAULT_INDEX_ALIASES


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", "", query.strip().lower())


def _is_ts_code(value: str) -> bool:
    return bool(re.fullmatch(r"\d{6}\.(sh|sz|bj)", value.lower()))


def _is_bare_code(value: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", value))


def resolve_instrument(query: str) -> dict[str, str | bool | list[dict[str, str]]]:
    normalized = _normalize_query(query)
    if not normalized:
        return {
            "resolved": False,
            "is_ambiguous": False,
            "instrument": None,
            "candidates": [],
        }

    if _is_ts_code(normalized) or _is_bare_code(normalized):
        code = _resolve_code_from_local_files(normalized.upper())
        asset_type = _asset_type_for_code(code)
        return {
            "resolved": True,
            "is_ambiguous": False,
            "instrument": {
                "ts_code": code,
                "name": code,
                "asset_type": asset_type,
                "market": "CN_A",
            },
            "candidates": [],
        }

    if normalized in DEFAULT_ETF_ALIASES:
        code = DEFAULT_ETF_ALIASES[normalized]
        return {
            "resolved": True,
            "is_ambiguous": False,
            "instrument": {
                "ts_code": code,
                "name": query.strip(),
                "asset_type": "etf",
                "market": "CN_A",
            },
            "candidates": [],
        }

    if normalized in DEFAULT_INDEX_ALIASES:
        code = DEFAULT_INDEX_ALIASES[normalized]
        return {
            "resolved": True,
            "is_ambiguous": False,
            "instrument": {
                "ts_code": code,
                "name": query.strip(),
                "asset_type": "index",
                "market": "CN_A",
            },
            "candidates": [],
        }

    candidates: list[dict[str, str]] = []
    for base, asset_type in (
        (settings.fund_daily_dir, "fund"),
        (settings.index_daily_dir, "index"),
        (settings.daily_qfq_dir, "stock"),
    ):
        for path in sorted(base.glob("*.parquet"))[:50]:
            if normalized in path.stem.lower():
                candidates.append(
                    {
                        "ts_code": path.stem.upper(),
                        "name": path.stem.upper(),
                        "asset_type": asset_type,
                    }
                )

    if len(candidates) == 1:
        hit = candidates[0]
        return {
            "resolved": True,
            "is_ambiguous": False,
            "instrument": {
                **hit,
                "market": "CN_A",
            },
            "candidates": [],
        }

    return {
        "resolved": False,
        "is_ambiguous": bool(candidates),
        "instrument": None,
        "candidates": candidates,
    }


def _resolve_code_from_local_files(code: str) -> str:
    if "." in code:
        return code
    for base in (settings.fund_daily_dir, settings.index_daily_dir, settings.daily_qfq_dir):
        matches = sorted(base.glob(f"{code}.*.parquet"))
        if matches:
            return matches[0].stem.upper()
    if code.startswith(("5", "6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return code


def _asset_type_for_code(code: str) -> str:
    if (settings.fund_daily_dir / f"{code}.parquet").exists():
        return "fund"
    if (settings.index_daily_dir / f"{code}.parquet").exists():
        return "index"
    return "stock"
