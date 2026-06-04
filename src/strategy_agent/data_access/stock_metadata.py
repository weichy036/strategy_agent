from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

import pandas as pd

from strategy_agent.config import settings


_FINANCE_AGENT_STOCK_INFO = Path("/Users/admin/weichy/finance_agent/data/meta/stock_info.parquet")


def stock_label(ts_code: str) -> str:
    code = str(ts_code or "").upper()
    return stock_name_map().get(code) or code


def stock_display_items(symbols: list[str]) -> list[dict[str, str]]:
    items = []
    for symbol in symbols:
        code = str(symbol or "").upper()
        items.append({"symbol": code, "label": stock_label(code)})
    return items


@lru_cache(maxsize=1)
def stock_name_map() -> dict[str, str]:
    path = _stock_info_path()
    if not path:
        return {}
    frame = pd.read_parquet(path, columns=["ts_code", "name"])
    if frame.empty:
        return {}
    frame["ts_code"] = frame["ts_code"].astype(str).str.upper()
    frame["name"] = frame["name"].astype(str).str.strip()
    frame = frame[frame["ts_code"].ne("") & frame["name"].ne("")]
    return dict(zip(frame["ts_code"], frame["name"], strict=False))


def _stock_info_path() -> Path | None:
    candidates = [
        os.getenv("STOCK_INFO_PATH", ""),
        str(settings.data_root / "meta" / "stock_info.parquet"),
        str(_FINANCE_AGENT_STOCK_INFO),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None
