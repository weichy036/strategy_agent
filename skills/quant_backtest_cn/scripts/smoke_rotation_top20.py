from __future__ import annotations

from run_backtest import _run


def main() -> None:
    result = _run(
        {
            "schema_version": "v1",
            "name": "每月买入市值最大的20只股票",
            "market": "CN",
            "strategy_type": "cross_sectional_rotation",
            "universe": {"type": "equity_universe", "scope": "cn_a_share"},
            "period": {"frequency": "1d", "start": None, "end": "latest"},
            "selection": {
                "ranking": {"sort_by": "total_mv", "order": "desc", "top_n": 20}
            },
            "portfolio": {
                "position_count": 20,
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
            "costs": {"commission_bps": 3, "slippage_bps": 5},
        }
    )
    data = result.get("data") or {}
    equity = ((data.get("result_page") or {}).get("equity_curve") or {}).get("series") or []
    yearly = ((data.get("metrics") or {}).get("period_breakdown") or {}).get("yearly_returns") or []
    print(f"ok={result.get('ok')} equity_points={len(equity)} yearly_rows={len(yearly)}")
    if not result.get("ok") or len(equity) < 2:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
