from __future__ import annotations

from datetime import date

import pandas as pd

from strategy_agent.data_update.daily_basic import update_daily_basic
from strategy_agent.data_update.market_series import update_fund_daily, update_index_daily
from strategy_agent.data_update.meta import refresh_meta
from strategy_agent.data_update.qfq import build_daily_qfq
from strategy_agent.data_update.selection import plan_selection_build
from strategy_agent.data_update.status import collect_data_status
from strategy_agent.data_update.stock_history import update_adj_factor, update_stock_daily
from strategy_agent.data_update.plan import plan_data_update
from strategy_agent.data_update.runner import run_data_maintenance
from strategy_agent.data_update.tushare_policy import TushareRetryPolicy


def test_collect_data_status_reports_dataset_lag(tmp_path) -> None:
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    daily_qfq = derived / "daily_qfq"
    daily_basic = raw / "daily_basic"
    selection_daily = derived / "selection_daily"
    fund_daily = raw / "fund_daily"
    index_daily = raw / "index_daily"
    selection_monthly = derived / "selection_monthly"
    for path in [daily_qfq, daily_basic, selection_daily, fund_daily, index_daily, selection_monthly]:
        path.mkdir(parents=True)

    pd.DataFrame({"trade_date": ["20260420", "20260421"], "close": [1, 2]}).to_parquet(
        daily_qfq / "000001.SZ.parquet",
        index=False,
    )
    pd.DataFrame({"trade_date": ["20241231"], "close": [1]}).to_parquet(
        fund_daily / "510300.SH.parquet",
        index=False,
    )
    pd.DataFrame({"trade_date": ["20260312"], "close": [1]}).to_parquet(
        index_daily / "000300.SH.parquet",
        index=False,
    )
    pd.DataFrame({"ts_code": ["000001.SZ"]}).to_parquet(daily_basic / "20260421.parquet", index=False)
    pd.DataFrame({"ts_code": ["000001.SZ"]}).to_parquet(selection_daily / "20260421.parquet", index=False)
    pd.DataFrame({"ts_code": ["000001.SZ"]}).to_parquet(selection_monthly / "202603_monthly_return.parquet", index=False)

    report = collect_data_status(
        as_of=date(2026, 6, 4),
        stale_after_days=7,
        raw_root=raw,
        derived_root=derived,
    ).to_dict()
    by_name = {item["name"]: item for item in report["datasets"]}

    assert by_name["daily_qfq"]["latest_date"] == "20260421"
    assert by_name["daily_qfq"]["lag_days"] == 44
    assert by_name["fund_daily"]["latest_date"] == "20241231"
    assert by_name["selection_monthly"]["latest_date"] == "20260301"
    assert set(report["stale_datasets"]) == {
        "daily_qfq",
        "daily_basic",
        "selection_daily",
        "fund_daily",
        "index_daily",
        "selection_monthly",
    }


def test_collect_data_status_uses_complete_daily_qfq_coverage(tmp_path) -> None:
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    daily_qfq = derived / "daily_qfq"
    daily_qfq.mkdir(parents=True)

    pd.DataFrame({"trade_date": ["20260421", "20260422"]}).to_parquet(
        daily_qfq / "000001.SZ.parquet",
        index=False,
    )
    pd.DataFrame({"trade_date": ["20260421"]}).to_parquet(
        daily_qfq / "000002.SZ.parquet",
        index=False,
    )

    report = collect_data_status(
        as_of=date(2026, 6, 4),
        raw_root=raw,
        derived_root=derived,
    ).to_dict()
    daily_status = {item["name"]: item for item in report["datasets"]}["daily_qfq"]

    assert daily_status["latest_date"] == "20260421"
    assert "80%" in daily_status["note"]


def test_plan_data_update_requires_tushare_token(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    (raw / "daily_basic").mkdir(parents=True)
    (derived / "daily_qfq").mkdir(parents=True)

    plan = plan_data_update(
        as_of=date(2026, 6, 4),
        raw_root=raw,
        derived_root=derived,
    ).to_dict()

    assert not plan["runnable"]
    assert plan["environment"]["token_present"] is False
    assert "TUSHARE_TOKEN" in plan["reason"]
    assert [step["name"] for step in plan["steps"] if step["required"]] == [
        "refresh_meta",
        "update_stock_daily",
        "update_adj_factor",
        "update_daily_basic",
        "update_fund_daily",
        "update_index_daily",
        "build_daily_qfq",
        "build_selection",
    ]


def test_plan_data_update_is_runnable_when_token_exists_and_data_is_stale(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "abcdef123456")
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    daily_basic = raw / "daily_basic"
    daily_qfq = derived / "daily_qfq"
    fund_daily = raw / "fund_daily"
    index_daily = raw / "index_daily"
    for path in [daily_basic, daily_qfq, fund_daily, index_daily]:
        path.mkdir(parents=True)

    pd.DataFrame({"trade_date": ["20260421"]}).to_parquet(daily_qfq / "000001.SZ.parquet", index=False)
    pd.DataFrame({"trade_date": ["20260407"]}).to_parquet(fund_daily / "510300.SH.parquet", index=False)
    pd.DataFrame({"trade_date": ["20260312"]}).to_parquet(index_daily / "000300.SH.parquet", index=False)
    pd.DataFrame({"ts_code": ["000001.SZ"]}).to_parquet(daily_basic / "20260421.parquet", index=False)

    plan = plan_data_update(
        as_of=date(2026, 6, 4),
        raw_root=raw,
        derived_root=derived,
    ).to_dict()

    assert plan["runnable"]
    assert plan["environment"]["token_hint"] == "abcdef***3456"
    assert plan["reason"] == "本地数据存在过期项，可以执行数据维护任务。"


def test_data_maintenance_dry_run_blocks_without_token(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    result = run_data_maintenance(raw_root=tmp_path / "raw", derived_root=tmp_path / "derived").to_dict()

    assert result["ok"]
    assert result["mode"] == "dry_run"
    assert result["events"] == [
        {
            "name": "environment",
            "title": "检查 Tushare 环境",
            "state": "blocked",
            "message": "TUSHARE_TOKEN 未配置，无法执行在线数据维护。",
        }
    ]


def test_data_maintenance_dry_run_plans_required_steps(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "abcdef123456")
    result = run_data_maintenance(
        as_of=date(2026, 6, 4),
        raw_root=tmp_path / "raw",
        derived_root=tmp_path / "derived",
    ).to_dict()

    assert result["message"] == "数据维护 dry-run 完成：计划执行 8 个步骤。"
    assert result["events"][0]["state"] == "planned"
    assert result["events"][0]["name"] == "refresh_meta"
    assert len(result["events"]) == 8


def test_data_maintenance_refresh_meta_uses_injected_client(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "abcdef123456")

    class FakePro:
        def stock_basic(self, **kwargs):
            return pd.DataFrame([{"ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行"}])

        def trade_cal(self, **kwargs):
            return pd.DataFrame([{"cal_date": "20260105", "is_open": 1}])

        def fund_basic(self, **kwargs):
            return pd.DataFrame([{"ts_code": "510300.SH", "name": "沪深300ETF"}])

    result = run_data_maintenance(
        mode="refresh_meta",
        raw_root=tmp_path / "raw",
        derived_root=tmp_path / "derived",
        meta_dir=tmp_path / "meta",
        pro=FakePro(),
    ).to_dict()

    assert result["ok"]
    assert result["message"] == "基础信息刷新完成。"
    assert result["events"] == [
        {
            "name": "refresh_meta",
            "title": "刷新基础信息",
            "state": "succeeded",
            "message": "基础信息已刷新：股票 1 只，交易日 1 条，ETF 1 只。",
        }
    ]


def test_update_daily_basic_only_fetches_missing_open_dates(tmp_path) -> None:
    class FakePro:
        def __init__(self):
            self.requested = []

        def query(self, api_name, **kwargs):
            assert api_name == "daily_basic"
            self.requested.append(kwargs["trade_date"])
            return pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": kwargs["trade_date"], "total_mv": 1.0}])

    target = tmp_path / "daily_basic"
    target.mkdir()
    pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": "20260105"}]).to_parquet(
        target / "20260105.parquet",
        index=False,
    )
    calendar = pd.DataFrame(
        [
            {"cal_date": "20260105", "is_open": 1},
            {"cal_date": "20260106", "is_open": 1},
            {"cal_date": "20260107", "is_open": 0},
            {"cal_date": "20260108", "is_open": 1},
        ]
    )
    pro = FakePro()

    result = update_daily_basic(
        pro,
        trade_calendar=calendar,
        target_dir=target,
        end_date="20260108",
        sleep_seconds=0,
    ).to_dict()

    assert pro.requested == ["20260106", "20260108"]
    assert result["saved_count"] == 2
    assert result["failed_count"] == 0
    assert result["latest_saved_date"] == "20260108"
    assert (target / "20260106.parquet").exists()
    assert (target / "20260108.parquet").exists()


def test_update_daily_basic_retries_transient_failure(tmp_path) -> None:
    class FakePro:
        def __init__(self):
            self.calls = 0

        def query(self, api_name, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporary timeout")
            return pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": kwargs["trade_date"]}])

    target = tmp_path / "daily_basic"
    calendar = pd.DataFrame([{"cal_date": "20260105", "is_open": 1}])

    result = update_daily_basic(
        FakePro(),
        trade_calendar=calendar,
        target_dir=target,
        sleep_seconds=0,
        retry_policy=TushareRetryPolicy(max_attempts=2, retry_delays=()),
    ).to_dict()

    assert result["saved_count"] == 1
    assert result["failed_count"] == 0
    assert result["failure_samples"] == []


def test_update_daily_basic_stops_after_failure_threshold(tmp_path) -> None:
    class FakePro:
        def query(self, api_name, **kwargs):
            raise TimeoutError(f"timeout {kwargs['trade_date']}")

    target = tmp_path / "daily_basic"
    calendar = pd.DataFrame(
        [
            {"cal_date": "20260105", "is_open": 1},
            {"cal_date": "20260106", "is_open": 1},
            {"cal_date": "20260107", "is_open": 1},
        ]
    )

    result = update_daily_basic(
        FakePro(),
        trade_calendar=calendar,
        target_dir=target,
        start_date="20260105",
        end_date="20260107",
        sleep_seconds=0,
        retry_policy=TushareRetryPolicy(max_attempts=1, retry_delays=(), stop_after_failures=2),
    ).to_dict()

    assert result["failed_count"] == 2
    assert result["requested_dates"] == ["20260105", "20260106", "20260107"]
    assert len(result["failure_samples"]) == 2


def test_data_maintenance_update_daily_basic_uses_injected_client(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "abcdef123456")
    raw = tmp_path / "raw"
    meta = tmp_path / "meta"
    daily_basic = raw / "daily_basic"
    daily_basic.mkdir(parents=True)
    meta.mkdir()
    pd.DataFrame(
        [
            {"cal_date": "20260105", "is_open": 1},
            {"cal_date": "20260106", "is_open": 1},
        ]
    ).to_parquet(meta / "trade_calendar.parquet", index=False)
    pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": "20260105"}]).to_parquet(
        daily_basic / "20260105.parquet",
        index=False,
    )

    class FakePro:
        def query(self, api_name, **kwargs):
            return pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": kwargs["trade_date"]}])

    result = run_data_maintenance(
        mode="update_daily_basic",
        raw_root=raw,
        derived_root=tmp_path / "derived",
        meta_dir=meta,
        pro=FakePro(),
    ).to_dict()

    assert result["ok"]
    assert result["message"] == "截面基础数据更新完成。"
    assert result["events"][0]["name"] == "update_daily_basic"
    assert result["events"][0]["state"] == "succeeded"
    assert "写入 1 个文件" in result["events"][0]["message"]


def test_update_fund_daily_fetches_missing_range(tmp_path) -> None:
    class FakePro:
        def __init__(self):
            self.calls = []

        def fund_daily(self, **kwargs):
            self.calls.append(kwargs)
            return pd.DataFrame([{"ts_code": kwargs["ts_code"], "trade_date": kwargs["start_date"], "close": 1.0}])

    target = tmp_path / "fund_daily"
    target.mkdir()
    pd.DataFrame([{"trade_date": "20260407", "close": 1.0}]).to_parquet(target / "510300.SH.parquet", index=False)
    pro = FakePro()

    result = update_fund_daily(
        pro,
        fund_info=pd.DataFrame([{"ts_code": "510300.SH"}]),
        target_dir=target,
        end_date="20260408",
        sleep_seconds=0,
    ).to_dict()

    assert pro.calls == [{"ts_code": "510300.SH", "start_date": "20260408", "end_date": "20260408"}]
    assert result["updated_count"] == 1
    assert pd.read_parquet(target / "510300.SH.parquet")["trade_date"].tolist() == ["20260407", "20260408"]


def test_update_fund_daily_prioritizes_existing_local_funds(tmp_path) -> None:
    class FakePro:
        def __init__(self):
            self.calls = []

        def fund_daily(self, **kwargs):
            self.calls.append(kwargs["ts_code"])
            return pd.DataFrame([{"ts_code": kwargs["ts_code"], "trade_date": kwargs["start_date"]}])

    target = tmp_path / "fund_daily"
    target.mkdir()
    pd.DataFrame([{"trade_date": "20260407"}]).to_parquet(target / "510300.SH.parquet", index=False)
    pro = FakePro()

    update_fund_daily(
        pro,
        fund_info=pd.DataFrame([{"ts_code": "150001.SZ"}, {"ts_code": "510300.SH"}]),
        target_dir=target,
        end_date="20260408",
        max_codes=1,
        sleep_seconds=0,
    )

    assert pro.calls == ["510300.SH"]


def test_update_index_daily_uses_existing_index_codes(tmp_path) -> None:
    class FakePro:
        def __init__(self):
            self.calls = []

        def index_daily(self, **kwargs):
            self.calls.append(kwargs)
            return pd.DataFrame([{"ts_code": kwargs["ts_code"], "trade_date": kwargs["start_date"], "close": 1.0}])

    target = tmp_path / "index_daily"
    target.mkdir()
    pd.DataFrame([{"trade_date": "20260312", "close": 1.0}]).to_parquet(target / "000300.SH.parquet", index=False)
    pro = FakePro()

    result = update_index_daily(
        pro,
        target_dir=target,
        end_date="20260313",
        sleep_seconds=0,
    ).to_dict()

    assert pro.calls == [{"ts_code": "000300.SH", "start_date": "20260313", "end_date": "20260313"}]
    assert result["updated_count"] == 1


def test_data_maintenance_update_market_sources_use_injected_client(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "abcdef123456")
    raw = tmp_path / "raw"
    meta = tmp_path / "meta"
    fund_daily = raw / "fund_daily"
    index_daily = raw / "index_daily"
    fund_daily.mkdir(parents=True)
    index_daily.mkdir(parents=True)
    meta.mkdir()
    pd.DataFrame([{"ts_code": "510300.SH"}]).to_parquet(meta / "fund_info.parquet", index=False)
    pd.DataFrame([{"trade_date": "20260407"}]).to_parquet(fund_daily / "510300.SH.parquet", index=False)
    pd.DataFrame([{"trade_date": "20260312"}]).to_parquet(index_daily / "000300.SH.parquet", index=False)

    class FakePro:
        def fund_daily(self, **kwargs):
            return pd.DataFrame([{"ts_code": kwargs["ts_code"], "trade_date": kwargs["start_date"]}])

        def index_daily(self, **kwargs):
            return pd.DataFrame([{"ts_code": kwargs["ts_code"], "trade_date": kwargs["start_date"]}])

    fund_result = run_data_maintenance(
        mode="update_fund_daily",
        raw_root=raw,
        derived_root=tmp_path / "derived",
        meta_dir=meta,
        pro=FakePro(),
    ).to_dict()
    index_result = run_data_maintenance(
        mode="update_index_daily",
        raw_root=raw,
        derived_root=tmp_path / "derived",
        pro=FakePro(),
    ).to_dict()

    assert fund_result["message"] == "ETF 日线更新完成。"
    assert fund_result["events"][0]["name"] == "update_fund_daily"
    assert "更新 1 只" in fund_result["events"][0]["message"]
    assert index_result["message"] == "指数日线更新完成。"
    assert index_result["events"][0]["name"] == "update_index_daily"
    assert "更新 1 只" in index_result["events"][0]["message"]


def test_update_stock_daily_starts_after_existing_qfq_date(tmp_path) -> None:
    class FakePro:
        def __init__(self):
            self.calls = []

        def daily(self, **kwargs):
            self.calls.append(kwargs)
            return pd.DataFrame(
                [
                    {
                        "ts_code": kwargs["ts_code"],
                        "trade_date": kwargs["start_date"],
                        "close": 10.0,
                    }
                ]
            )

    qfq = tmp_path / "qfq"
    daily = tmp_path / "daily"
    qfq.mkdir()
    stock_info = pd.DataFrame([{"ts_code": "000001.SZ"}])
    pd.DataFrame([{"trade_date": "20260421", "close": 9.0}]).to_parquet(qfq / "000001.SZ.parquet", index=False)
    pro = FakePro()

    result = update_stock_daily(
        pro,
        stock_info=stock_info,
        daily_dir=daily,
        qfq_dir=qfq,
        end_date="20260422",
        sleep_seconds=0,
    ).to_dict()

    assert pro.calls == [{"ts_code": "000001.SZ", "start_date": "20260422", "end_date": "20260422"}]
    assert result["updated_count"] == 1
    assert pd.read_parquet(daily / "000001.SZ.parquet")["trade_date"].tolist() == ["20260422"]


def test_update_stock_daily_retries_and_records_failure_samples(tmp_path) -> None:
    class FakePro:
        def daily(self, **kwargs):
            raise TimeoutError("read timeout")

    qfq = tmp_path / "qfq"
    daily = tmp_path / "daily"
    qfq.mkdir()
    pd.DataFrame([{"trade_date": "20260421", "close": 9.0}]).to_parquet(qfq / "000001.SZ.parquet", index=False)

    result = update_stock_daily(
        FakePro(),
        stock_info=pd.DataFrame([{"ts_code": "000001.SZ"}]),
        daily_dir=daily,
        qfq_dir=qfq,
        end_date="20260422",
        sleep_seconds=0,
        retry_policy=TushareRetryPolicy(max_attempts=2, retry_delays=(), stop_after_failures=1),
    ).to_dict()

    assert result["failed_count"] == 1
    assert result["failure_samples"] == ["000001.SZ: read timeout"]


def test_update_adj_factor_writes_factor_partition(tmp_path) -> None:
    class FakePro:
        def adj_factor(self, **kwargs):
            assert kwargs == {"ts_code": "000001.SZ", "trade_date": ""}
            return pd.DataFrame(
                [
                    {"ts_code": "000001.SZ", "trade_date": "20260421", "adj_factor": 1.0},
                    {"ts_code": "000001.SZ", "trade_date": "20260422", "adj_factor": 1.1},
                ]
            )

    qfq = tmp_path / "qfq"
    adj = tmp_path / "adj_factor"
    qfq.mkdir()
    pd.DataFrame([{"trade_date": "20260421", "close": 9.0}]).to_parquet(qfq / "000001.SZ.parquet", index=False)

    result = update_adj_factor(
        FakePro(),
        stock_info=pd.DataFrame([{"ts_code": "000001.SZ"}]),
        adj_factor_dir=adj,
        qfq_dir=qfq,
        end_date="20260422",
        sleep_seconds=0,
    ).to_dict()

    assert result["updated_count"] == 1
    assert pd.read_parquet(adj / "000001.SZ.parquet")["trade_date"].tolist() == ["20260421", "20260422"]


def test_data_maintenance_update_stock_daily_uses_injected_client(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "abcdef123456")
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    meta = tmp_path / "meta"
    qfq = derived / "daily_qfq"
    qfq.mkdir(parents=True)
    meta.mkdir()
    pd.DataFrame([{"ts_code": "000001.SZ"}]).to_parquet(meta / "stock_info.parquet", index=False)
    pd.DataFrame([{"trade_date": "20260421"}]).to_parquet(qfq / "000001.SZ.parquet", index=False)

    class FakePro:
        def daily(self, **kwargs):
            return pd.DataFrame([{"ts_code": kwargs["ts_code"], "trade_date": kwargs["start_date"]}])

    result = run_data_maintenance(
        mode="update_stock_daily",
        raw_root=raw,
        derived_root=derived,
        meta_dir=meta,
        pro=FakePro(),
    ).to_dict()

    assert result["message"] == "股票日线更新完成。"
    assert result["events"][0]["name"] == "update_stock_daily"
    assert "更新 1 只" in result["events"][0]["message"]


def test_data_maintenance_update_stock_daily_applies_batch_and_retry_options(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "abcdef123456")
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    meta = tmp_path / "meta"
    qfq = derived / "daily_qfq"
    qfq.mkdir(parents=True)
    meta.mkdir()
    pd.DataFrame([{"ts_code": "000001.SZ"}, {"ts_code": "000002.SZ"}]).to_parquet(
        meta / "stock_info.parquet",
        index=False,
    )
    pd.DataFrame([{"trade_date": "20260421"}]).to_parquet(qfq / "000001.SZ.parquet", index=False)
    pd.DataFrame([{"trade_date": "20260421"}]).to_parquet(qfq / "000002.SZ.parquet", index=False)

    class FakePro:
        def __init__(self) -> None:
            self.calls = 0

        def daily(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporary tushare timeout")
            return pd.DataFrame([{"ts_code": kwargs["ts_code"], "trade_date": kwargs["start_date"]}])

    client = FakePro()
    result = run_data_maintenance(
        mode="update_stock_daily",
        raw_root=raw,
        derived_root=derived,
        meta_dir=meta,
        pro=client,
        max_codes=1,
        sleep_seconds=0,
        retry_max_attempts=2,
        retry_delay_seconds=0,
    ).to_dict()

    assert client.calls == 2
    assert result["events"][0]["state"] == "succeeded"
    assert "请求 1 只股票" in result["events"][0]["message"]
    assert "更新 1 只" in result["events"][0]["message"]


def test_data_maintenance_run_batch_executes_update_rebuild_and_selection(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "abcdef123456")
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    meta = tmp_path / "meta"
    qfq = derived / "daily_qfq"
    qfq.mkdir(parents=True)
    meta.mkdir()
    pd.DataFrame([{"ts_code": "000001.SZ"}]).to_parquet(meta / "stock_info.parquet", index=False)
    pd.DataFrame(
        [{"ts_code": "000001.SZ", "trade_date": "20260421", "open": 10.0, "close": 10.0}]
    ).to_parquet(qfq / "000001.SZ.parquet", index=False)

    class FakeSelectionResult:
        def to_dict(self):
            return {
                "built_daily_count": 1,
                "built_monthly_count": 1,
                "plan": {"latest_price_date": "20260422", "blocked_after_price_date_count": 0},
            }

    class FakePro:
        def daily(self, **kwargs):
            return pd.DataFrame(
                [
                    {
                        "ts_code": kwargs["ts_code"],
                        "trade_date": kwargs["start_date"],
                        "open": 11.0,
                        "close": 12.0,
                        "pre_close": 10.0,
                    }
                ]
            )

        def adj_factor(self, **kwargs):
            return pd.DataFrame(
                [
                    {"ts_code": kwargs["ts_code"], "trade_date": "20260421", "adj_factor": 1.0},
                    {"ts_code": kwargs["ts_code"], "trade_date": "20260422", "adj_factor": 1.2},
                ]
            )

    monkeypatch.setattr("strategy_agent.data_update.runner.build_selection_data", lambda: FakeSelectionResult())

    result = run_data_maintenance(
        mode="run_batch",
        raw_root=raw,
        derived_root=derived,
        meta_dir=meta,
        pro=FakePro(),
        max_codes=1,
        sleep_seconds=0,
    ).to_dict()

    assert result["message"] == "数据维护批处理完成。"
    assert [event["name"] for event in result["events"]] == [
        "update_stock_daily",
        "update_adj_factor",
        "update_fund_daily",
        "update_index_daily",
        "build_daily_qfq",
        "build_selection",
    ]
    assert pd.read_parquet(qfq / "000001.SZ.parquet")["trade_date"].tolist() == ["20260421", "20260422"]


def test_data_maintenance_run_batch_stops_after_failed_online_step(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "abcdef123456")
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    meta = tmp_path / "meta"
    qfq = derived / "daily_qfq"
    qfq.mkdir(parents=True)
    meta.mkdir()
    pd.DataFrame([{"ts_code": "000001.SZ"}]).to_parquet(meta / "stock_info.parquet", index=False)
    pd.DataFrame([{"trade_date": "20260421"}]).to_parquet(qfq / "000001.SZ.parquet", index=False)

    class FakePro:
        def daily(self, **kwargs):
            raise TimeoutError("temporary tushare timeout")

    result = run_data_maintenance(
        mode="run_batch",
        raw_root=raw,
        derived_root=derived,
        meta_dir=meta,
        pro=FakePro(),
        max_codes=1,
        sleep_seconds=0,
        retry_max_attempts=1,
        stop_after_failures=1,
    ).to_dict()

    assert result["message"] == "数据维护批处理失败。"
    assert [event["name"] for event in result["events"]] == ["update_stock_daily"]
    assert result["events"][0]["state"] == "failed"


def test_build_daily_qfq_merges_incremental_rows(tmp_path) -> None:
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    daily = raw / "daily"
    adj = raw / "adj_factor"
    qfq = derived / "daily_qfq"
    for path in [daily, adj, qfq]:
        path.mkdir(parents=True)

    pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": "20260421", "close": 10.0, "open": 10.0}]).to_parquet(
        qfq / "000001.SZ.parquet",
        index=False,
    )
    pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "trade_date": "20260422", "open": 20.0, "close": 22.0, "pre_close": 19.0},
            {"ts_code": "000001.SZ", "trade_date": "20260423", "open": 30.0, "close": 33.0, "pre_close": 29.0},
        ]
    ).to_parquet(daily / "000001.SZ.parquet", index=False)
    pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "trade_date": "20260422", "adj_factor": 2.0},
            {"ts_code": "000001.SZ", "trade_date": "20260423", "adj_factor": 4.0},
        ]
    ).to_parquet(adj / "000001.SZ.parquet", index=False)

    result = build_daily_qfq(daily_dir=daily, adj_factor_dir=adj, output_dir=qfq).to_dict()
    out = pd.read_parquet(qfq / "000001.SZ.parquet")

    assert result["built_count"] == 1
    assert out["trade_date"].tolist() == ["20260421", "20260422", "20260423"]
    assert out.loc[out["trade_date"] == "20260422", "close"].iloc[0] == 11.0
    assert out.loc[out["trade_date"] == "20260423", "close"].iloc[0] == 33.0
    assert out["adj_type"].dropna().unique().tolist() == ["qfq"]


def test_data_maintenance_build_daily_qfq_uses_temp_roots(tmp_path) -> None:
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    daily = raw / "daily"
    adj = raw / "adj_factor"
    daily.mkdir(parents=True)
    adj.mkdir(parents=True)
    pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": "20260422", "close": 10.0}]).to_parquet(
        daily / "000001.SZ.parquet",
        index=False,
    )
    pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": "20260422", "adj_factor": 1.0}]).to_parquet(
        adj / "000001.SZ.parquet",
        index=False,
    )

    result = run_data_maintenance(mode="build_daily_qfq", raw_root=raw, derived_root=derived).to_dict()

    assert result["message"] == "前复权日线重建完成。"
    assert result["events"][0]["name"] == "build_daily_qfq"
    assert "生成 1 只" in result["events"][0]["message"]
    assert (derived / "daily_qfq" / "000001.SZ.parquet").exists()


def test_plan_selection_build_stops_at_latest_price_date(tmp_path) -> None:
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    daily_basic = raw / "daily_basic"
    daily_qfq = derived / "daily_qfq"
    selection_daily = derived / "selection_daily"
    selection_monthly = derived / "selection_monthly"
    for path in [daily_basic, daily_qfq, selection_daily, selection_monthly]:
        path.mkdir(parents=True)

    for trade_date in ["20260420", "20260421", "20260422"]:
        pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": trade_date}]).to_parquet(
            daily_basic / f"{trade_date}.parquet",
            index=False,
        )
    pd.DataFrame({"trade_date": ["20260420", "20260421"], "close": [1, 2]}).to_parquet(
        daily_qfq / "000001.SZ.parquet",
        index=False,
    )
    pd.DataFrame([{"ts_code": "000001.SZ"}]).to_parquet(selection_daily / "20260420.parquet", index=False)

    plan = plan_selection_build(
        daily_basic_dir=daily_basic,
        daily_qfq_dir=daily_qfq,
        selection_daily_dir=selection_daily,
        selection_monthly_dir=selection_monthly,
    ).to_dict()

    assert plan["latest_price_date"] == "20260421"
    assert plan["missing_daily_dates"] == ["20260421"]
    assert plan["blocked_after_price_date_count"] == 1
    assert plan["months_to_build"] == ["202604"]


def test_plan_selection_build_ignores_partial_price_dates(tmp_path) -> None:
    raw = tmp_path / "raw"
    derived = tmp_path / "derived"
    daily_basic = raw / "daily_basic"
    daily_qfq = derived / "daily_qfq"
    selection_daily = derived / "selection_daily"
    selection_monthly = derived / "selection_monthly"
    for path in [daily_basic, daily_qfq, selection_daily, selection_monthly]:
        path.mkdir(parents=True)

    for trade_date in ["20260421", "20260422"]:
        pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": trade_date}]).to_parquet(
            daily_basic / f"{trade_date}.parquet",
            index=False,
        )
    pd.DataFrame({"trade_date": ["20260421", "20260422"], "close": [1, 2]}).to_parquet(
        daily_qfq / "000001.SZ.parquet",
        index=False,
    )
    pd.DataFrame({"trade_date": ["20260421"], "close": [1]}).to_parquet(
        daily_qfq / "000002.SZ.parquet",
        index=False,
    )

    plan = plan_selection_build(
        daily_basic_dir=daily_basic,
        daily_qfq_dir=daily_qfq,
        selection_daily_dir=selection_daily,
        selection_monthly_dir=selection_monthly,
    ).to_dict()

    assert plan["latest_price_date"] == "20260421"
    assert plan["missing_daily_dates"] == ["20260421"]
    assert plan["blocked_after_price_date_count"] == 1


def test_data_maintenance_build_selection_reports_price_boundary(monkeypatch) -> None:
    monkeypatch.setattr(
        "strategy_agent.data_update.runner.build_selection_data",
        lambda: type(
            "FakeResult",
            (),
            {
                "to_dict": lambda self: {
                    "ok": True,
                    "built_daily_count": 0,
                    "built_monthly_count": 0,
                    "plan": {
                        "latest_price_date": "20260421",
                        "blocked_after_price_date_count": 29,
                    },
                }
            },
        )(),
    )

    result = run_data_maintenance(mode="build_selection").to_dict()

    assert result["ok"]
    assert result["message"] == "选股截面构建检查完成。"
    assert result["events"][0]["name"] == "build_selection"
    assert result["events"][0]["state"] == "succeeded"
    assert "股票日线最新到 20260421" in result["events"][0]["message"]
    assert "需先补股票日线" in result["events"][0]["message"]


def test_refresh_meta_writes_stock_calendar_and_fund_info(tmp_path) -> None:
    class FakePro:
        def stock_basic(self, **kwargs):
            assert kwargs["fields"] == "ts_code,symbol,name,area,industry,list_date,list_status"
            return pd.DataFrame(
                [
                    {"ts_code": "300750.SZ", "symbol": "300750", "name": "宁德时代"},
                    {"ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行"},
                ]
            )

        def trade_cal(self, **kwargs):
            assert kwargs["start_date"] == "20150101"
            return pd.DataFrame(
                [
                    {"cal_date": "20260105", "is_open": 1},
                    {"cal_date": "20260104", "is_open": 0},
                ]
            )

        def fund_basic(self, **kwargs):
            assert kwargs["market"] == "E"
            return pd.DataFrame([{"ts_code": "510300.SH", "name": "沪深300ETF"}])

    result = refresh_meta(FakePro(), meta_dir=tmp_path).to_dict()

    assert result == {
        "ok": True,
        "meta_dir": str(tmp_path),
        "stock_count": 2,
        "trade_calendar_count": 2,
        "fund_count": 1,
        "skipped_fund_info": False,
    }
    assert pd.read_parquet(tmp_path / "stock_info.parquet")["ts_code"].tolist() == ["000001.SZ", "300750.SZ"]
    assert pd.read_parquet(tmp_path / "trade_calendar.parquet")["cal_date"].tolist() == ["20260104", "20260105"]
    assert pd.read_parquet(tmp_path / "fund_info.parquet")["ts_code"].tolist() == ["510300.SH"]
