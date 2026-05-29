# Data Contract

The current MVP reads local historical data copied into the project data directory.

## Expected Data

ETF daily bars:

- `data/raw/fund_daily`

Index daily bars:

- `data/raw/index_daily`

Stock adjusted daily bars:

- `data/derived/daily_qfq`

Daily basic/factor data:

- `data/raw/daily_basic`

## Required Bar Columns

Daily bar frames should provide:

- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `vol` or volume equivalent when available

## Date Format

Internal trade dates are normalized as `YYYYMMDD` strings.

The user may write dates naturally, but StrategySchema should keep dates simple:

- `YYYY-MM-DD`
- `YYYYMMDD`
- `latest`
- `null` for default

## Result Requirements

Backtest result must include:

- `run_id`
- `date_range`
- `equity_curve`
- `drawdown_curve`
- `trade_log`
- `position_log`
- `yearly_returns`
- `summary`

The completed result page must include a non-empty equity curve series.
