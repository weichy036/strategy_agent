from __future__ import annotations

import re
from typing import Any

from strategy_agent.config import settings
from strategy_agent.constants import (
    DEFAULT_COMMISSION_BPS,
    DEFAULT_ETF_ALIASES,
    DEFAULT_ETF_SLIPPAGE_BPS,
    DEFAULT_FILTERS,
    DEFAULT_STOCK_SLIPPAGE_BPS,
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())


def _extract_top_n(text: str, default: int | None = None) -> int | None:
    match = re.search(r"(?:最大|最高|前|top)(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)只", text)
    if match:
        return int(match.group(1))
    return default


def _resolve_etf_symbol(normalized: str) -> str | None:
    for alias, symbol in DEFAULT_ETF_ALIASES.items():
        if alias in normalized:
            return symbol
    if "沪深300" in normalized and "etf" in normalized:
        return "510300.SH"
    return None


def _build_macd_signal_strategy(query: str, normalized: str) -> dict[str, Any]:
    symbol = _resolve_etf_symbol(normalized)
    has_buy = "金叉" in normalized and "买" in normalized
    has_sell = "死叉" in normalized and "卖" in normalized
    strategy: dict[str, Any] = {
        "schema_version": "v1",
        "strategy_id": f"stg_macd_{(symbol or 'unknown').replace('.', '_').lower()}_v1",
        "name": "MACD 金叉死叉策略",
        "market": "CN",
        "strategy_type": "signal_trading",
        "universe": {
            "type": "instrument",
            "symbols": [symbol] if symbol else [],
        },
        "period": {
            "frequency": "1d",
            "start": settings.default_start_date,
            "end": "latest",
        },
        "signals": {
            "buy": [],
            "sell": [],
        },
        "portfolio": {
            "position_count": 1,
            "weight_method": "full_position",
            "rebalance_frequency": "event_driven",
            "long_only": True,
        },
        "execution": {
            "buy_price": "next_open",
            "sell_price": "next_open",
            "trade_timing": "next_bar",
            "rebalance_trigger": "signal",
        },
        "costs": {
            "commission_bps": DEFAULT_COMMISSION_BPS,
            "slippage_bps": DEFAULT_ETF_SLIPPAGE_BPS,
        },
        "constraints": {
            "tradability_filters": [],
            "allow_short": False,
        },
        "metadata": {
            "source_query": query,
            "defaulted_fields": [
                "period.start",
                "period.end",
                "costs.commission_bps",
                "costs.slippage_bps",
            ],
        },
    }
    if has_buy:
        strategy["signals"]["buy"].append(
            {
                "kind": "indicator_event",
                "indicator": "macd",
                "params": {"fast": 12, "slow": 26, "signal": 9},
                "operator": "bullish_cross",
            }
        )
    if has_sell:
        strategy["signals"]["sell"].append(
            {
                "kind": "indicator_event",
                "indicator": "macd",
                "params": {"fast": 12, "slow": 26, "signal": 9},
                "operator": "bearish_cross",
            }
        )
    return strategy


def _build_large_cap_rotation_strategy(query: str, normalized: str) -> dict[str, Any]:
    top_n = _extract_top_n(query, default=20)
    return {
        "schema_version": "v1",
        "strategy_id": f"stg_large_cap_top{top_n}_monthly_v1",
        "name": f"月度大市值前{top_n}轮动",
        "market": "CN",
        "strategy_type": "cross_sectional_rotation",
        "universe": {
            "type": "equity_universe",
            "scope": "all_a_share",
            "filters": DEFAULT_FILTERS,
        },
        "period": {
            "frequency": "1d",
            "start": settings.default_start_date,
            "end": "latest",
        },
        "selection": {
            "filters": [],
            "ranking": {
                "sort_by": "total_mv",
                "order": "desc",
                "top_n": top_n,
            },
            "hold_period": {
                "type": "calendar_rebalance",
                "frequency": "monthly",
            },
        },
        "portfolio": {
            "position_count": top_n,
            "weight_method": "equal_weight",
            "rebalance_frequency": "monthly",
            "long_only": True,
        },
        "execution": {
            "buy_price": "next_open",
            "sell_price": "next_open",
            "trade_timing": "next_bar",
            "rebalance_trigger": "calendar",
        },
        "costs": {
            "commission_bps": DEFAULT_COMMISSION_BPS,
            "slippage_bps": DEFAULT_STOCK_SLIPPAGE_BPS,
        },
        "constraints": {
            "tradability_filters": ["exclude_suspended"],
            "allow_short": False,
        },
        "metadata": {
            "source_query": query,
            "defaulted_fields": [
                "universe.scope",
                "universe.filters",
                "period.start",
                "period.end",
                "portfolio.weight_method",
                "costs.commission_bps",
                "costs.slippage_bps",
            ],
        },
    }


def parse_strategy_query(query: str) -> dict[str, Any]:
    normalized = _normalize_text(query)
    if "macd" in normalized or "金叉" in normalized or "死叉" in normalized:
        return {
            "recognized": True,
            "problem_type": "signal_trading",
            "strategy_draft": _build_macd_signal_strategy(query, normalized),
            "parser": "rule_based_v1",
        }
    if ("市值" in normalized and ("每月" in normalized or "月" in normalized)) or "最大" in normalized:
        return {
            "recognized": True,
            "problem_type": "cross_sectional_rotation",
            "strategy_draft": _build_large_cap_rotation_strategy(query, normalized),
            "parser": "rule_based_v1",
        }
    return {
        "recognized": False,
        "problem_type": None,
        "strategy_draft": {},
        "parser": "rule_based_v1",
    }
