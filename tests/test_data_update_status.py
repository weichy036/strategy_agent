from __future__ import annotations

from datetime import date

import pandas as pd

from strategy_agent.data_update.status import collect_data_status


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
