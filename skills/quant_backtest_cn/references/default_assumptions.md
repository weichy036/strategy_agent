# Default Assumptions

These defaults are used when the user does not specify details. Do not ask the user for these fields unless they explicitly want to override them.

## Market and Frequency

- `market`: `CN`
- `period.frequency`: `1d`

## Date Range

- `period.start`: project default start date.
- `period.end`: `latest`.

The result page should disclose the actual data date range used by the engine.

## Execution

Daily signals are assumed to be known after market close. Orders execute at the next trading day's open.

Defaults:

- `execution.buy_price`: `next_open`
- `execution.sell_price`: `next_open`
- `execution.trade_timing`: `next_bar`
- `execution.rebalance_trigger`: `calendar`

## Costs

Default costs:

- `costs.commission_bps`: `3`
- `costs.slippage_bps`: `5`

## Data Price Mode

- Stocks use adjusted daily data where available.
- ETFs use fund daily bars.
- Index data is used as benchmark or trading calendar, not as a tradable asset unless explicitly supported.

## Clarification Boundary

Ask only for fields that change the strategy definition itself. Do not ask for operational defaults.
