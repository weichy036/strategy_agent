# Strategy Schema V1

## 1. 文档目标

这份文档定义第一版系统内部使用的统一策略表示。

它的作用是把用户自然语言问题、策略卡展示、回测执行输入、结果解释对象统一到同一个中间层结构上。

这份 Schema 不是给最终用户直接填写的，而是系统内部的核心契约。

## 2. 为什么必须有统一 Schema

如果没有统一 Schema，系统很容易出现三套表达方式：

- 对话层有一套说法
- 回测引擎有一套输入
- 结果解释层有一套理解

这样会导致：

- Agent 理解和执行脱节
- 同一个策略难以复现
- 后续难以保存、克隆、比较

因此第一版必须先把“策略对象”固定下来。

## 3. 设计目标

第一版 Strategy Schema 要满足 5 个目标：

1. 能覆盖当前 MVP 支持的策略类型
2. 能被自然语言稳定映射
3. 能被回测引擎稳定执行
4. 能支持策略卡展示
5. 能支持后续版本扩展

## 4. 当前支持的策略类型

第一版只支持以下四类：

### 4.1 单标的信号策略

示例：

- ETF 的 MACD 金叉买入、死叉卖出
- 均线突破买入、跌破卖出

### 4.2 横截面排序选股策略

示例：

- 每月买入市值最大的 20 只股票
- 每周买入过去 60 天涨幅最高的 10 只股票

### 4.3 条件筛选 + 固定持有期策略

示例：

- 过去 60 天创新高的股票，每周五买入，下周五卖出

### 4.4 单标的规则择时策略

这类策略和 4.1 类似，但更强调布尔条件触发，而不一定是标准指标交叉。

例如：

- 收盘价站上 20 日均线买入，跌破 20 日均线卖出

## 5. Schema 的总体结构

第一版建议策略对象由下面几个一级字段组成：

- `schema_version`
- `strategy_id`
- `name`
- `market`
- `strategy_type`
- `universe`
- `period`
- `signals`
- `selection`
- `portfolio`
- `execution`
- `costs`
- `constraints`
- `metadata`

注意：

- 不是每种策略都必须用到所有字段
- 但顶层结构尽量统一，减少分叉

## 6. 顶层字段定义

### 6.1 `schema_version`

含义：

- 当前 Schema 版本

建议：

- 固定为 `v1`

### 6.2 `strategy_id`

含义：

- 系统内部唯一标识

说明：

- 可由系统生成
- 用户无需输入

### 6.3 `name`

含义：

- 策略展示名称

说明：

- 可由用户指定
- 也可由系统根据问题自动生成

### 6.4 `market`

含义：

- 市场范围

第一版建议值：

- `CN`

### 6.5 `strategy_type`

含义：

- 策略分类

第一版建议值：

- `signal_trading`
- `cross_sectional_rotation`
- `screen_and_hold`
- `rule_based_timing`

### 6.6 `universe`

含义：

- 标的范围

作用：

- 定义是单标的、ETF、还是股票池

### 6.7 `period`

含义：

- 回测时间范围与数据频率

### 6.8 `signals`

含义：

- 买卖触发条件

说明：

- 主要用于单标的信号策略和择时策略

### 6.9 `selection`

含义：

- 选股、排序、筛选逻辑

说明：

- 主要用于横截面和筛选策略

### 6.10 `portfolio`

含义：

- 组合层面的持仓数量、权重方式、调仓频率等

### 6.11 `execution`

含义：

- 成交时点、价格假设、调仓触发方式

### 6.12 `costs`

含义：

- 手续费、滑点、税费等

### 6.13 `constraints`

含义：

- 长仓限制、过滤规则、可交易约束等

### 6.14 `metadata`

含义：

- 原始问题、生成方式、默认值标记等补充信息

## 7. 关键字段详解

### 7.1 `universe`

建议结构：

```json
{
  "type": "instrument",
  "symbols": ["510300.SH"],
  "scope": null,
  "filters": []
}
```

第一版可支持两种形态：

#### 形态 A：单标的

```json
{
  "type": "instrument",
  "symbols": ["510300.SH"]
}
```

#### 形态 B：股票池

```json
{
  "type": "equity_universe",
  "scope": "all_a_share",
  "filters": ["exclude_st", "exclude_suspended", "exclude_recent_ipo_60d"]
}
```

### 7.2 `period`

建议结构：

```json
{
  "frequency": "1d",
  "start": "2018-01-01",
  "end": "2025-12-31"
}
```

第一版建议：

- 频率固定为 `1d`
- 起止时间可以用户指定，也可以系统默认补全

### 7.3 `signals`

适用于：

- `signal_trading`
- `rule_based_timing`

建议结构：

```json
{
  "buy": [
    {
      "kind": "indicator_event",
      "indicator": "macd",
      "params": { "fast": 12, "slow": 26, "signal": 9 },
      "operator": "bullish_cross"
    }
  ],
  "sell": [
    {
      "kind": "indicator_event",
      "indicator": "macd",
      "params": { "fast": 12, "slow": 26, "signal": 9 },
      "operator": "bearish_cross"
    }
  ]
}
```

第一版支持的 `kind` 建议包括：

- `indicator_event`
- `comparison_rule`
- `price_breakout`

第一版支持的 `indicator` 可先限制为：

- `ma`
- `ema`
- `macd`
- `rsi`
- `bollinger`

### 7.4 `selection`

适用于：

- `cross_sectional_rotation`
- `screen_and_hold`

建议结构：

```json
{
  "filters": [
    {
      "field": "close_breakout_60d_high",
      "operator": "eq",
      "value": true
    }
  ],
  "ranking": {
    "sort_by": "total_mv",
    "order": "desc",
    "top_n": 20
  },
  "hold_period": {
    "type": "calendar_rebalance",
    "frequency": "monthly"
  }
}
```

### 7.5 `portfolio`

建议结构：

```json
{
  "position_count": 20,
  "weight_method": "equal_weight",
  "rebalance_frequency": "monthly",
  "long_only": true
}
```

第一版建议支持：

- `equal_weight`
- `full_position`

其中：

- 单标的策略可使用 `full_position`
- 组合策略可使用 `equal_weight`

### 7.6 `execution`

建议结构：

```json
{
  "buy_price": "next_open",
  "sell_price": "next_open",
  "trade_timing": "next_bar",
  "rebalance_trigger": "calendar"
}
```

第一版建议支持：

- `buy_price`: `next_open`, `close`
- `sell_price`: `next_open`, `close`

### 7.7 `costs`

建议结构：

```json
{
  "commission_bps": 3,
  "slippage_bps": 5
}
```

第一版先不引入复杂税费模型。

### 7.8 `constraints`

建议结构：

```json
{
  "tradability_filters": [
    "exclude_suspended",
    "exclude_limit_up",
    "exclude_limit_down"
  ],
  "allow_short": false
}
```

第一版原则：

- 只做多
- 不支持杠杆
- 默认考虑基础可交易约束

### 7.9 `metadata`

建议结构：

```json
{
  "source_query": "如果每个月买入市值最大的20只股票，持有到下个月，收益是多少？",
  "defaulted_fields": [
    "period.start",
    "period.end",
    "portfolio.weight_method",
    "costs.commission_bps",
    "costs.slippage_bps"
  ]
}
```

作用：

- 记录原始问题
- 标记哪些字段是系统默认补出来的
- 方便结果页做透明说明

## 8. 必填字段与默认字段

### 8.1 第一版必填字段

无论什么策略，建议最少必须有：

- `schema_version`
- `market`
- `strategy_type`
- `universe`
- `period.frequency`
- `execution`

### 8.2 条件必填字段

#### 对于 `signal_trading` / `rule_based_timing`

必须有：

- `signals.buy`
- `signals.sell`

#### 对于 `cross_sectional_rotation`

必须有：

- `selection.ranking`
- `portfolio.position_count`
- `portfolio.weight_method`
- `portfolio.rebalance_frequency`

#### 对于 `screen_and_hold`

必须有：

- `selection.filters`
- `selection.hold_period`

### 8.3 可默认字段

第一版建议允许系统默认补全：

- `period.start`
- `period.end`
- `costs.commission_bps`
- `costs.slippage_bps`
- `constraints.tradability_filters`
- `portfolio.weight_method`

但系统必须在输出中明确说明哪些字段用了默认值。

## 9. 策略类型与字段映射

### 9.1 `signal_trading`

适用场景：

- MACD 金叉 / 死叉
- MA 上穿 / 下穿

重点字段：

- `universe`
- `signals`
- `execution`
- `costs`

### 9.2 `rule_based_timing`

适用场景：

- 价格站上均线买入
- RSI 低于阈值买入

重点字段：

- `universe`
- `signals`
- `execution`

### 9.3 `cross_sectional_rotation`

适用场景：

- 每月买入市值最大的 20 只股票
- 每周买入动量最高的 10 只股票

重点字段：

- `universe`
- `selection.ranking`
- `portfolio`
- `execution`

### 9.4 `screen_and_hold`

适用场景：

- 筛出满足条件的股票，固定持有一段时间

重点字段：

- `universe`
- `selection.filters`
- `selection.hold_period`
- `portfolio`

## 10. 示例 1：ETF MACD 策略

```json
{
  "schema_version": "v1",
  "strategy_id": "stg_macd_510300_v1",
  "name": "沪深300ETF MACD 金叉死叉策略",
  "market": "CN",
  "strategy_type": "signal_trading",
  "universe": {
    "type": "instrument",
    "symbols": ["510300.SH"]
  },
  "period": {
    "frequency": "1d",
    "start": "2018-01-01",
    "end": "2025-12-31"
  },
  "signals": {
    "buy": [
      {
        "kind": "indicator_event",
        "indicator": "macd",
        "params": { "fast": 12, "slow": 26, "signal": 9 },
        "operator": "bullish_cross"
      }
    ],
    "sell": [
      {
        "kind": "indicator_event",
        "indicator": "macd",
        "params": { "fast": 12, "slow": 26, "signal": 9 },
        "operator": "bearish_cross"
      }
    ]
  },
  "portfolio": {
    "position_count": 1,
    "weight_method": "full_position",
    "rebalance_frequency": "event_driven",
    "long_only": true
  },
  "execution": {
    "buy_price": "next_open",
    "sell_price": "next_open",
    "trade_timing": "next_bar",
    "rebalance_trigger": "signal"
  },
  "costs": {
    "commission_bps": 3,
    "slippage_bps": 5
  },
  "constraints": {
    "tradability_filters": [],
    "allow_short": false
  },
  "metadata": {
    "source_query": "对于沪深300ETF，MACD 日线金叉买入、死叉卖出，每年的平均收益是多少？",
    "defaulted_fields": []
  }
}
```

## 11. 示例 2：月度大市值轮动策略

```json
{
  "schema_version": "v1",
  "strategy_id": "stg_large_cap_monthly_v1",
  "name": "月度大市值前20轮动",
  "market": "CN",
  "strategy_type": "cross_sectional_rotation",
  "universe": {
    "type": "equity_universe",
    "scope": "all_a_share",
    "filters": ["exclude_st", "exclude_suspended", "exclude_recent_ipo_60d"]
  },
  "period": {
    "frequency": "1d",
    "start": "2018-01-01",
    "end": "2025-12-31"
  },
  "selection": {
    "filters": [],
    "ranking": {
      "sort_by": "total_mv",
      "order": "desc",
      "top_n": 20
    },
    "hold_period": {
      "type": "calendar_rebalance",
      "frequency": "monthly"
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
    "slippage_bps": 10
  },
  "constraints": {
    "tradability_filters": ["exclude_suspended"],
    "allow_short": false
  },
  "metadata": {
    "source_query": "如果每个月买入市值最大的20只股票，持有到下个月，收益是多少？",
    "defaulted_fields": ["costs.commission_bps", "costs.slippage_bps"]
  }
}
```

## 12. 示例 3：筛选后固定持有策略

```json
{
  "schema_version": "v1",
  "strategy_id": "stg_breakout_weekly_v1",
  "name": "60日新高周度持有策略",
  "market": "CN",
  "strategy_type": "screen_and_hold",
  "universe": {
    "type": "equity_universe",
    "scope": "all_a_share",
    "filters": ["exclude_st", "exclude_suspended"]
  },
  "period": {
    "frequency": "1d",
    "start": "2019-01-01",
    "end": "2025-12-31"
  },
  "selection": {
    "filters": [
      {
        "field": "close_breakout_60d_high",
        "operator": "eq",
        "value": true
      }
    ],
    "ranking": null,
    "hold_period": {
      "type": "fixed_holding_days",
      "days": 5
    }
  },
  "portfolio": {
    "position_count": 20,
    "weight_method": "equal_weight",
    "rebalance_frequency": "weekly",
    "long_only": true
  },
  "execution": {
    "buy_price": "close",
    "sell_price": "close",
    "trade_timing": "same_bar",
    "rebalance_trigger": "calendar"
  },
  "costs": {
    "commission_bps": 3,
    "slippage_bps": 10
  },
  "constraints": {
    "tradability_filters": ["exclude_suspended"],
    "allow_short": false
  },
  "metadata": {
    "source_query": "找出过去60天创新高的股票，每周五买入，下周五卖出，效果怎么样？",
    "defaulted_fields": []
  }
}
```

## 13. 第一版不放进 Schema 的内容

为了保持第一版简单稳定，以下内容建议暂不纳入：

- 杠杆参数
- 做空逻辑
- 多市场混合组合
- 期权期货合约属性
- 分钟级执行细节
- 复杂订单类型
- 机器学习模型配置

## 14. 设计原则总结

第一版 Strategy Schema 需要坚持下面几条原则：

### 原则 1：统一顶层结构

即使不同策略类型字段不完全一样，也尽量使用统一的一级字段。

### 原则 2：让自然语言容易映射

字段命名和结构不能只为了程序员方便，也要考虑是否容易从用户问题中抽取。

### 原则 3：让执行层尽量确定

一旦策略对象生成，回测执行应尽可能少依赖额外推理。

### 原则 4：让默认值显式可见

不能偷偷补全关键假设。

### 原则 5：为后续扩展留接口

第一版虽然收敛，但结构上不要把未来多市场、多策略类型彻底堵死。

## 15. 这份文档对后续设计的约束

这份 Schema 文档会直接约束以下内容：

- `clarification_rules_v1.md`
  因为系统要知道哪些字段缺失时必须追问

- `adk_system_architecture_v1.md`
  因为解析 Agent 和回测 Tool 的输入输出都要围绕这个对象

- 回测引擎设计
  因为回测器最终执行的是这个结构化对象

## 16. 下一步建议

基于这份文档，最适合继续写的是：

1. `clarification_rules_v1.md`
2. `backtest_assumptions_v1.md`

因为现在“对象长什么样”已经基本确定，下一步就该明确：

- 哪些字段缺失必须问用户
- 哪些字段可以默认补
- 默认补全时使用什么规则
