# 数据清单

当前项目已经从 `/Users/admin/weichy/finance_agent` 复制了第一版回测所需的基础日线数据。

## 已复制数据

### 1. ETF 日线

目录：

- `/Users/admin/weichy/strategy_agent/data/raw/fund_daily`

用途：

- 支持 ETF 技术指标择时策略
- 示例包括 `510300.SH`、`510500.SH`、`510050.SH`

样例字段：

- `ts_code`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `pre_close`
- `pct_chg`
- `vol`
- `amount`

### 2. 指数日线

目录：

- `/Users/admin/weichy/strategy_agent/data/raw/index_daily`

用途：

- 支持回测基准
- 当前包含沪深 300 指数 `000300.SH`

### 3. 股票前复权日线

目录：

- `/Users/admin/weichy/strategy_agent/data/derived/daily_qfq`

用途：

- 支持 A 股个股回测
- 支持横截面选股后的收益计算
- 用作技术指标计算的主价格源

样例字段：

- `ts_code`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `pre_close`
- `pct_chg`
- `vol`
- `amount`
- `adj_factor`
- `adj_type`

### 4. 股票日度基础面快照

目录：

- `/Users/admin/weichy/strategy_agent/data/raw/daily_basic`

用途：

- 支持按市值、换手率、估值等横截面字段筛选股票
- 可用于“每月买入市值最大的 20 只股票”这类策略

样例字段：

- `ts_code`
- `trade_date`
- `turnover_rate`
- `pe`
- `pb`
- `total_share`
- `float_share`
- `total_mv`
- `circ_mv`

## 为什么暂时不复制其他数据

当前没有复制以下目录：

- `data/raw/daily`
- `data/raw/adj_factor`

原因：

- `daily_qfq` 已经可以直接作为前复权回测价格源
- `daily_qfq` 中已经包含 `adj_factor`
- 对当前 MVP 来说，继续保留原始未复权日线会增加体积和维护成本

## 当前数据规模

- `data/raw/fund_daily`: 6 个文件
- `data/raw/index_daily`: 1 个文件
- `data/raw/daily_basic`: 2744 个文件
- `data/derived/daily_qfq`: 5512 个文件

## 对 MVP 的支撑能力

这批数据已经足以支撑我们第一版的两类核心场景：

1. ETF 技术指标回测
2. A 股横截面选股与定期调仓回测

后续如果要扩展到更复杂的策略，可以再补：

- 行业分类
- 财务报表
- ST / 停牌 / 退市状态
- 成分股历史
- 分钟级数据
