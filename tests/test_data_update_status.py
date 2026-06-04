from __future__ import annotations

from datetime import date

import pandas as pd

from strategy_agent.data_update.meta import refresh_meta
from strategy_agent.data_update.status import collect_data_status
from strategy_agent.data_update.plan import plan_data_update
from strategy_agent.data_update.runner import run_data_maintenance


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
