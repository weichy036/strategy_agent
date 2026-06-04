from __future__ import annotations

import pandas as pd

from strategy_agent.data_access.stock_metadata import stock_display_items, stock_label, stock_name_map


def test_stock_metadata_uses_configured_stock_info_path(tmp_path, monkeypatch) -> None:
    path = tmp_path / "stock_info.parquet"
    pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "name": "平安银行"},
            {"ts_code": "300750.SZ", "name": "宁德时代"},
        ]
    ).to_parquet(path, index=False)
    monkeypatch.setenv("STOCK_INFO_PATH", str(path))
    stock_name_map.cache_clear()

    try:
        assert stock_label("000001.SZ") == "平安银行"
        assert stock_display_items(["300750.SZ", "999999.SZ"]) == [
            {"symbol": "300750.SZ", "label": "宁德时代"},
            {"symbol": "999999.SZ", "label": "999999.SZ"},
        ]
    finally:
        stock_name_map.cache_clear()
