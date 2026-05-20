from __future__ import annotations


DEFAULT_COMMISSION_BPS = 3
DEFAULT_ETF_SLIPPAGE_BPS = 5
DEFAULT_STOCK_SLIPPAGE_BPS = 10

DEFAULT_FILTERS = [
    "exclude_st",
    "exclude_suspended",
    "exclude_recent_ipo_60d",
]

DEFAULT_ETF_ALIASES = {
    "沪深300etf": "510300.SH",
    "300etf": "510300.SH",
    "上证50etf": "510050.SH",
    "50etf": "510050.SH",
    "中证500etf": "510500.SH",
    "500etf": "510500.SH",
    "红利etf": "510880.SH",
    "证券etf": "512880.SH",
    "创业板etf": "159915.SZ",
}

DEFAULT_INDEX_ALIASES = {
    "沪深300": "000300.SH",
    "沪深300指数": "000300.SH",
    "hs300": "000300.SH",
}

SUPPORTED_STRATEGY_TYPES = {
    "signal_trading",
    "cross_sectional_rotation",
    "screen_and_hold",
    "rule_based_timing",
}

STATE_STAGES = {
    "intake",
    "parsing",
    "clarifying",
    "schema_ready",
    "running_backtest",
    "computing_metrics",
    "explaining",
    "assembled",
    "completed",
    "failed",
}
