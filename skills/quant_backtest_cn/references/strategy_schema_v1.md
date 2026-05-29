# StrategySchema v1 Reference

StrategySchema is the single contract between natural-language understanding, backtest execution, and result explanation.

## Supported Top-Level Fields

- `schema_version`: fixed to `v1`.
- `strategy_id`: optional internal id.
- `name`: optional display name.
- `market`: fixed to `CN`.
- `strategy_type`: one of `signal_trading`, `rule_based_timing`, `cross_sectional_rotation`.
- `universe`: instrument or equity universe.
- `period`: frequency and date range.
- `signals`: buy and sell rules for timing strategies.
- `selection`: ranking or filters for cross-sectional strategies.
- `portfolio`: position count, weight method, and rebalance frequency.
- `execution`: execution timing and price assumptions.
- `costs`: commission and slippage.
- `constraints`: tradability and shorting constraints.
- `metadata`: source query and defaulted fields.

## Single-Instrument MACD Example

```json
{
  "schema_version": "v1",
  "name": "沪深300ETF MACD 金叉死叉",
  "market": "CN",
  "strategy_type": "signal_trading",
  "universe": {
    "type": "instrument",
    "symbols": ["510300.SH"]
  },
  "period": {
    "frequency": "1d",
    "start": null,
    "end": "latest"
  },
  "signals": {
    "buy": [
      {
        "kind": "indicator_event",
        "indicator": "macd",
        "params": {"fast": 12, "slow": 26, "signal": 9},
        "operator": "bullish_cross"
      }
    ],
    "sell": [
      {
        "kind": "indicator_event",
        "indicator": "macd",
        "params": {"fast": 12, "slow": 26, "signal": 9},
        "operator": "bearish_cross"
      }
    ]
  },
  "execution": {
    "buy_price": "next_open",
    "sell_price": "next_open",
    "trade_timing": "next_bar",
    "rebalance_trigger": "calendar"
  },
  "costs": {
    "commission_bps": 3,
    "slippage_bps": 5
  },
  "metadata": {
    "source_query": "对于沪深300ETF，MACD 日线金叉买入、死叉卖出，每年的平均收益是多少？",
    "defaulted_fields": ["period.start", "period.end", "execution", "costs"]
  }
}
```

## Monthly Top-Market-Cap Rotation Example

```json
{
  "schema_version": "v1",
  "name": "每月买入市值最大的20只股票",
  "market": "CN",
  "strategy_type": "cross_sectional_rotation",
  "universe": {
    "type": "equity_universe",
    "scope": "cn_a_share"
  },
  "period": {
    "frequency": "1d",
    "start": null,
    "end": "latest"
  },
  "selection": {
    "ranking": {
      "sort_by": "total_mv",
      "order": "desc",
      "top_n": 20
    }
  },
  "portfolio": {
    "position_count": 20,
    "weight_method": "equal_weight",
    "rebalance_frequency": "monthly",
    "long_only": true
  },
  "execution": {
    "buy_price": "next_open",
    "sell_price": "next_open",
    "trade_timing": "next_bar",
    "rebalance_trigger": "calendar"
  },
  "costs": {
    "commission_bps": 3,
    "slippage_bps": 5
  }
}
```

## Common Invalid Values

Do not output these values for `strategy_type`:

- `timing`
- `signal_based`
- `single_instrument`
- `etf`
- `factor`
- `basic`
- `backtest`
- empty string

Use the supported enum values only.
