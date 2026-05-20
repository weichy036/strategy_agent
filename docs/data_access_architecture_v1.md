# 数据访问架构 V1

## 1. 文档目标

这份文档用于定义第一版项目的数据访问架构。

它回答的问题是：

- 当前项目应该如何组织和读取本地市场数据
- 如何吸收 `/Users/admin/weichy/finance_agent` 中已有的数据链路经验
- Tushare 数据是如何进入系统的
- 前复权数据如何生成
- 每日数据如何定时更新
- `BacktestRunTool` 应通过什么接口稳定获取数据

这份文档的重点不是立即实现所有代码，而是先把“数据从哪里来、如何变成可回测对象、如何持续更新”这件事讲清楚。

## 2. 数据层设计原则

第一版数据访问层建议遵守以下原则：

### 原则 1：继承已有成熟链路，不重复造轮子

`finance_agent` 已经把很多关键问题处理过了：

- Tushare 拉取
- raw / derived / gold / precomputed 分层
- 前复权生成
- daily_basic 截面管理
- 每日自动更新

当前项目应优先吸收这些经验，而不是从零自造另一套完全不同的数据体系。

### 原则 2：数据访问层必须和回测引擎解耦

`BacktestRunTool` 不应该直接自己拼路径、自己读 parquet、自己猜字段。

更合理的方式是：

- 由统一数据访问层提供标准化接口
- 回测工具只消费标准业务对象

### 原则 3：原始数据、派生数据、服务数据分层

当前项目应继续沿用这条思想：

- `raw`: 原始数据
- `derived`: 派生数据
- `gold`: 快照查询层
- `precomputed`: 预计算层

### 原则 4：默认优先使用本地数据

第一版回测系统以本地已有数据为主，不把远程拉数作为主链路的一部分。

远程拉数能力可以保留为：

- 补齐机制
- 运维更新机制
- 特定标的按需拉取机制

## 3. 从 finance_agent 学到的当前数据链路

从 `/Users/admin/weichy/finance_agent` 的代码和脚本来看，现有数据链路已经比较完整。

它的主更新顺序是：

1. `meta`
2. `raw/daily`
3. `raw/adj_factor`
4. `raw/daily_basic`
5. `derived/daily_qfq`
6. `derived/factors`
7. `gold/feature_snapshot`
8. `precomputed/drawdown`

对应入口文件是：

- `/Users/admin/weichy/finance_agent/scripts/update_all_data.py`

这条顺序非常合理，当前项目建议直接继承这条依赖关系。

## 4. 当前项目已有数据资产

当前仓库已复制的核心数据包括：

- `data/raw/fund_daily`
- `data/raw/index_daily`
- `data/raw/daily_basic`
- `data/derived/daily_qfq`

这些数据已经足以支撑第一版策略研究 MVP：

- ETF 技术指标回测
- A 股横截面选股
- 定期调仓策略
- 基准比较

## 5. 为什么当前项目暂时没有复制 raw/daily 和 raw/adj_factor

这是有意做的收敛，不是遗漏。

原因是：

- 第一版回测执行直接使用 `derived/daily_qfq`
- 当前 `daily_qfq` 已经包含 `adj_factor`
- 对“读数据做回测”来说，`daily_qfq + daily_basic + fund_daily + index_daily` 已经够用

但这也意味着：

- 当前项目虽然能做回测
- 还不具备完整的“本地自更新原始股价 + 本地重建前复权”的最小闭环

所以在架构设计上，我们要把这件事明确下来：

- 第一版运行时依赖当前已复制数据
- 后续如果要把数据维护也纳入当前项目，再补 `raw/daily` 和 `raw/adj_factor`

## 6. Tushare 接入方式

从 `finance_agent` 代码看，Tushare 的接入方式已经非常清晰。

### 6.1 Token 来源

主要来源：

- 环境变量 `TUSHARE_TOKEN`
- 或项目 `.env`

相关入口可见：

- `/Users/admin/weichy/finance_agent/scripts/update_all_data.py`
- `/Users/admin/weichy/finance_agent/scripts/supplement_fq_factor.py`
- `/Users/admin/weichy/finance_agent/data_platform/ingest/tushare_fund.py`
- `/Users/admin/weichy/finance_agent/data_platform/ingest/tushare_index.py`

### 6.2 当前项目建议

当前项目第一版建议保留同样的约定：

- 如果未来需要本地补拉数据，统一通过 `TUSHARE_TOKEN` 提供认证

并且建议不要把 token 写死在代码里。

## 7. 前复权数据如何生成

从 `/Users/admin/weichy/finance_agent/scripts/calc_adj_daily.py` 可以明确看到当前前复权的生成逻辑。

## 7.1 输入

输入来自：

- `raw/daily/{ts_code}.parquet`
- `raw/adj_factor/{ts_code}.parquet`

## 7.2 计算逻辑

核心逻辑是：

- 将 `daily` 和 `adj_factor` 按 `trade_date` 合并
- 取最新交易日的 `adj_factor` 作为基准
- 计算：

```text
adj_ratio = 当日 adj_factor / 最新日 adj_factor
前复权价 = 原始价格 × adj_ratio
```

会对以下价格列做处理：

- `open`
- `high`
- `low`
- `close`
- `pre_close`

并重新计算：

- `change`
- `pct_chg`

最终输出：

- `derived/daily_qfq/{ts_code}.parquet`
- 增加 `adj_type = qfq`

## 7.3 对当前项目的含义

这说明第一版数据访问架构可以明确假设：

- 股票回测默认读 `derived/daily_qfq`
- 不需要回测时再临时计算前复权

这样能显著简化 `BacktestRunTool`。

## 8. ETF / 指数数据如何处理

`finance_agent` 里 ETF 和指数没有走股票那套前复权流程，而是单独处理。

### 8.1 ETF

来自：

- `raw/fund_daily/{ts_code}.parquet`

按需补拉逻辑在：

- `/Users/admin/weichy/finance_agent/data_platform/ingest/tushare_fund.py`

特点：

- 本地无文件时可按需拉取
- 本地有文件时补缺口，不做大规模重复拉取

### 8.2 指数

来自：

- `raw/index_daily/{ts_code}.parquet`

按需补拉逻辑在：

- `/Users/admin/weichy/finance_agent/data_platform/ingest/tushare_index.py`

特点：

- 同样支持增量补齐

### 8.3 对当前项目的建议

第一版建议继续沿用这个分法：

- 股票主价格源：`derived/daily_qfq`
- ETF 主价格源：`raw/fund_daily`
- 指数基准源：`raw/index_daily`

## 9. 当前 finance_agent 的数据访问分层

从代码上看，`finance_agent` 已经形成了一个值得借鉴的访问分层。

### 9.1 ingest 层

作用：

- 负责从 Tushare 拉取和补齐原始数据

代表文件：

- `data_platform/ingest/tushare_fund.py`
- `data_platform/ingest/tushare_index.py`

### 9.2 normalize 层

作用：

- 把不同目录和字段统一成标准业务 DataFrame

代表文件：

- `data_platform/normalize/service.py`

这层已经处理了：

- ETF / 指数 / 股票的分流读取
- `instrument_id`
- `asset_type`
- `market`
- `price_mode`
- `daily_basic` 市值单位统一为元

### 9.3 domain 层

作用：

- 提供更贴近业务的入口函数

代表文件：

- `domain/market_data/service.py`

例如已经有：

- `get_bar_frame(...)`
- `get_daily_basic_frame(...)`
- `get_daily_basic_by_instrument(...)`

### 9.4 status 层

作用：

- 提供数据更新状态的检查和摘要

代表文件：

- `data_platform/status/service.py`

## 10. 当前项目建议采用的访问架构

基于以上观察，当前项目建议采用三层数据访问结构。

## 10.1 第一层：Storage Layer

职责：

- 管理 parquet 文件和目录结构

对应当前项目目录：

- `data/raw/fund_daily`
- `data/raw/index_daily`
- `data/raw/daily_basic`
- `data/derived/daily_qfq`

这一层只负责“存什么、放哪儿”。

## 10.2 第二层：Normalization Layer

职责：

- 把不同来源的数据统一成可消费对象

需要解决的问题：

- 股票、ETF、指数的价格数据结构统一
- `ts_code` 统一大写
- 统一时间筛选
- `daily_basic` 市值单位统一
- 补齐 `asset_type`、`market`、`price_mode`

这一层建议直接借鉴 `finance_agent/data_platform/normalize/service.py` 的设计思路。

## 10.3 第三层：Domain Access Layer

职责：

- 为 Agent / Tool 提供业务友好接口

第一版建议暴露的接口包括：

- `get_bar_frame(instrument, price_mode="qfq", start_date=None, end_date="latest")`
- `get_daily_basic_frame(trade_date="latest")`
- `get_daily_basic_by_instrument(instrument, trade_date="latest")`
- `get_latest_trade_date()`
- `get_benchmark_frame(symbol, start_date=None, end_date="latest")`

这一层是 `BacktestRunTool` 的直接依赖面。

## 11. BacktestRunTool 需要的数据接口

为了让 `BacktestRunTool` 保持干净，数据访问层至少要提供以下标准输入。

## 11.1 单标的价格接口

用于：

- ETF MACD
- 个股均线策略

建议返回字段至少包括：

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
- `asset_type`
- `price_mode`

## 11.2 横截面基础面接口

用于：

- 按市值排序
- 按换手率筛选

建议返回字段至少包括：

- `ts_code`
- `trade_date`
- `total_mv`
- `circ_mv`
- `turnover_rate`
- `pe`
- `pb`
- `asset_type`

## 11.3 基准接口

用于：

- 结果页收益曲线对比

建议至少支持：

- `000300.SH`

## 11.4 交易日历接口

用于：

- 找下一个交易日
- 处理月末 / 周末调仓

建议未来从 `meta/trade_calendar` 明确提供统一访问。

## 12. daily_basic 的关键注意点

从 `finance_agent` 的 normalize 层可以看到一个很重要的处理：

- Tushare 的 `total_mv` / `circ_mv` 原始单位是“万元”
- 在服务层被统一转成“元”

这对当前项目非常重要。

因为如果不统一单位，像“市值最大的 20 只股票”这类策略就很容易在阈值和排序比较上出错。

所以当前项目建议明确规定：

- 数据访问层输出给上层时，`total_mv`、`circ_mv` 统一使用“元”

## 13. 最新交易日如何判断

`finance_agent` 里已经有一个比较实用的思路：

- 从已有数据中估算最新交易日
- 再和交易日历做差，判断是否缺更近期数据

相关逻辑可见：

- `data_platform/normalize/service.py` 中的 `resolve_latest_trade_date`
- `data_platform/status/service.py` 中的 `get_data_status_summary`

当前项目建议：

- 第一版至少提供 `get_latest_trade_date()`
- 后续再补 `get_data_status_summary()` 之类的运维接口

## 14. 每日定时更新链路

从 `finance_agent` 看，当前每日更新链路非常明确。

### 14.1 调度入口

`launchd` 配置：

- `/Users/admin/weichy/finance_agent/deploy/launchd/com.finance_agent.daily_light.plist`

当前配置显示：

- 工作日 16:50 触发

### 14.2 Shell 入口

- `/Users/admin/weichy/finance_agent/run_daily_update.sh`

作用：

- 加载 `.env`
- 注入 `TUSHARE_TOKEN`
- 调用统一维护入口

### 14.3 Python 统一维护入口

- `/Users/admin/weichy/finance_agent/scripts/run_data_maintenance.py`

作用：

- 根据 profile 选择轻量或完整更新
- 记录维护日志
- 更新后可串联 tracking job

### 14.4 数据更新主脚本

- `/Users/admin/weichy/finance_agent/scripts/update_all_data.py`

作用：

- 执行全链路刷新

## 15. 当前项目对“定时更新”的建议

第一版当前项目先不急着复制整个运维体系，但设计上要明确分成两阶段。

### 阶段 A：研究执行阶段

特点：

- 使用已经复制进项目的静态本地数据
- 先把策略研究主链路跑通

### 阶段 B：数据维护阶段

未来再引入：

- `TUSHARE_TOKEN`
- 原始股票数据补齐
- 前复权重建
- 定时更新调度

这样能避免第一版同时处理太多运维复杂度。

## 16. 对当前项目的具体设计结论

基于以上分析，我建议当前项目的数据访问架构做出如下明确决策。

### 决策 1：第一版回测执行只依赖当前已复制数据

即：

- 股票：`derived/daily_qfq`
- ETF：`raw/fund_daily`
- 指数：`raw/index_daily`
- 截面：`raw/daily_basic`

### 决策 2：第一版不把 Tushare 在线拉数放进主回测路径

原因：

- 降低不确定性
- 减少网络依赖
- 让回测更可复现

### 决策 3：数据访问层要借鉴 finance_agent 的 normalize + domain 设计

也就是：

- 底层读 parquet
- 中层做标准化
- 顶层暴露业务接口

### 决策 4：后续如果补数据维护能力，优先迁移 update_all_data 的思想，而不是零散补脚本

## 17. 推荐的当前项目模块划分

如果未来开始实现，建议数据侧模块按下面拆。

### `data_access/storage.py`

负责：

- 路径常量
- 文件存在性判断
- 基础 parquet 读写

### `data_access/normalize.py`

负责：

- 统一价格数据结构
- 统一 `daily_basic` 字段
- 统一 `asset_type` / `price_mode`

### `domain/market_data.py`

负责：

- 面向 Tool 的业务读取接口

### `services/data_status.py`

负责：

- 数据可用性与最新日期检查

## 18. 与 ADK Tool 的关系

这份文档会直接约束以下 Tool：

- `MarketDataQueryTool`
- `BacktestRunTool`
- `MetricsComputeTool`

其中：

- `MarketDataQueryTool` 应调用 Domain Access Layer
- `BacktestRunTool` 不直接碰底层目录
- `MetricsComputeTool` 只处理回测结果，不负责拉底层数据

## 19. 第一版后续扩展

后续如果把数据维护也纳入当前项目，建议按以下顺序扩展：

1. 补 `meta/trade_calendar`
2. 补 `raw/daily`
3. 补 `raw/adj_factor`
4. 引入前复权生成脚本
5. 引入每日维护入口
6. 再接入定时调度

这样改动最平滑。

## 20. 下一步建议

基于这份文档，下一步最适合继续写的是：

1. `tool_contracts_v1.md`
2. `adk_state_and_artifacts_v1.md`

因为现在我们已经把：

- 产品链路
- 策略对象
- 澄清规则
- 回测假设
- 结果页结构
- ADK 系统架构
- Agent 拓扑
- 数据访问架构

都定下来了，接下来就该继续固定：

- 每个 Tool 的输入输出契约
- Session State 和 Artifact 的字段结构
