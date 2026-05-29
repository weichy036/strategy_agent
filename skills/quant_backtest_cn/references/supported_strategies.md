# Supported Strategies

## signal_trading

Single-instrument timing strategy using explicit buy and sell signals.

Examples:

- MACD bullish cross buy, bearish cross sell.
- MA10 crossing above MA60 buy, crossing below sell.
- RSI oversold buy, overbought sell.

Required fields:

- `universe.type = instrument`
- one symbol in `universe.symbols`
- `signals.buy`
- `signals.sell`
- `execution`

## rule_based_timing

Single-instrument rule strategy with boolean conditions.

Examples:

- Close above MA20 buy, close below MA20 sell.
- Breakout above 20-day high buy, fall below MA20 sell.

Required fields:

- `universe.type = instrument`
- one symbol in `universe.symbols`
- `signals.buy`
- `signals.sell`
- `execution`

## cross_sectional_rotation

Periodic selection and rebalance strategy across an equity universe.

Examples:

- Monthly buy top 20 by total market cap.
- Monthly buy top 10 by turnover.

Required fields:

- `universe.type = equity_universe`
- `selection.ranking`
- `portfolio.position_count`
- `portfolio.weight_method`
- `portfolio.rebalance_frequency`
- `execution`

## Not Yet Supported

Do not claim these are fully supported:

- Intraday strategies.
- Futures, options, convertible bonds.
- Short selling.
- Leverage.
- Pair trading.
- ML model training inside the live request.
- Arbitrary user Python strategy execution.

For unsupported strategies, explain the limitation and suggest the closest supported version.
