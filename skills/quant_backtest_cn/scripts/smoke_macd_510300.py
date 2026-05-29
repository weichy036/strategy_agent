from __future__ import annotations

from run_backtest import _run


def main() -> None:
    result = _run(
        {
            "schema_version": "v1",
            "name": "沪深300ETF MACD 金叉死叉",
            "market": "CN",
            "strategy_type": "signal_trading",
            "universe": {"type": "instrument", "symbols": ["510300.SH"]},
            "period": {"frequency": "1d", "start": None, "end": "latest"},
            "signals": {
                "buy": [
                    {
                        "kind": "indicator_event",
                        "indicator": "macd",
                        "params": {"fast": 12, "slow": 26, "signal": 9},
                        "operator": "bullish_cross",
                    }
                ],
                "sell": [
                    {
                        "kind": "indicator_event",
                        "indicator": "macd",
                        "params": {"fast": 12, "slow": 26, "signal": 9},
                        "operator": "bearish_cross",
                    }
                ],
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
    equity = (((result.get("data") or {}).get("result_page") or {}).get("equity_curve") or {}).get("series") or []
    print(f"ok={result.get('ok')} equity_points={len(equity)}")
    if not result.get("ok") or len(equity) < 2:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
