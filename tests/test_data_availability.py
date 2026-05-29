from __future__ import annotations

from strategy_agent.agents.data_research import apply_schema_patch
from strategy_agent.services.data_availability import inspect_strategy_data


def test_inspect_macd_etf_data_ready() -> None:
    report = inspect_strategy_data(
        {
            "strategy_type": "signal_trading",
            "universe": {"type": "instrument", "symbols": ["510300.SH"]},
            "period": {"frequency": "1d", "start": "20230101", "end": "20241231"},
        }
    )

    assert report.is_ready
    assert report.can_continue_backtest
    assert report.required_datasets[0].dataset == "fund_daily"
    assert report.local_coverage[0].exists


def test_inspect_bare_codes_are_normalized_before_data_check() -> None:
    etf_report = inspect_strategy_data(
        {
            "strategy_type": "signal_trading",
            "universe": {"type": "instrument", "symbols": ["510300"]},
            "period": {"frequency": "1d", "start": "20230101", "end": "20241231"},
        }
    )
    stock_report = inspect_strategy_data(
        {
            "strategy_type": "signal_trading",
            "universe": {"type": "instrument", "symbols": ["300750"]},
            "period": {"frequency": "1d", "start": "20230101", "end": "20241231"},
        }
    )

    assert etf_report.is_ready
    assert etf_report.required_datasets[0].symbols == ["510300.SH"]
    assert stock_report.is_ready
    assert stock_report.required_datasets[0].symbols == ["300750.SZ"]


def test_inspect_missing_stock_data_blocks() -> None:
    report = inspect_strategy_data(
        {
            "strategy_type": "signal_trading",
            "universe": {"type": "instrument", "symbols": ["999999.SZ"]},
            "period": {"frequency": "1d", "start": "20230101", "end": "20241231"},
        }
    )

    assert not report.is_ready
    assert report.blocking_issues == ["daily_qfq:999999.SZ:missing"]
    assert report.fetch_plan[0].api_name == "daily+adj_factor"


def test_rotation_amount_ranking_uses_selection_daily_contract() -> None:
    report = inspect_strategy_data(
        {
            "strategy_type": "cross_sectional_rotation",
            "universe": {"type": "equity_universe", "symbols": []},
            "period": {"frequency": "1d", "start": None, "end": None},
            "selection": {"ranking": {"sort_by": "amount", "order": "desc", "top_n": 10}},
            "portfolio": {"position_count": 10},
        }
    )

    assert report.is_ready
    assert report.required_datasets[0].dataset == "selection_daily"
    assert report.required_datasets[0].fields == ["ts_code", "trade_date", "amount"]
    assert report.required_factors[0].name == "amount"
    assert report.required_factors[0].source_type == "raw_field"


def test_previous_month_return_ranking_is_derived_from_local_prices() -> None:
    report = inspect_strategy_data(
        {
            "strategy_type": "cross_sectional_rotation",
            "universe": {"type": "equity_universe", "symbols": []},
            "period": {"frequency": "1d", "start": "20240101", "end": "20241231"},
            "selection": {"ranking": {"sort_by": "last_month_return", "order": "desc", "top_n": 5}},
            "portfolio": {"position_count": 5},
        }
    )

    assert report.is_ready
    assert report.required_datasets[0].fields == ["ts_code", "trade_date", "monthly_return"]
    assert report.can_continue_backtest
    assert report.required_factors[0].name == "monthly_return"
    assert report.required_factors[0].source_type == "derived"
    assert report.required_factors[0].base_fields == ["trade_date", "close"]
    assert report.schema_patch == {
        "selection.ranking.sort_by": "monthly_return",
        "selection.ranking.lookback": "previous_month_return",
    }


def test_unsupported_rotation_factor_blocks_with_factor_context() -> None:
    report = inspect_strategy_data(
        {
            "strategy_type": "cross_sectional_rotation",
            "universe": {"type": "equity_universe", "symbols": []},
            "period": {"frequency": "1d", "start": None, "end": None},
            "selection": {"ranking": {"sort_by": "northbound_net_buy", "order": "desc", "top_n": 5}},
            "portfolio": {"position_count": 5},
        }
    )

    assert not report.is_ready
    assert report.can_continue_backtest is False
    assert report.required_factors[0].name == "northbound_net_buy"
    assert report.required_factors[0].source_type == "unsupported"
    assert report.blocking_issues == ["selection_daily:missing_fields:northbound_net_buy"]


def test_data_research_schema_patch_updates_executable_schema_without_mutating_original() -> None:
    schema = {
        "strategy_type": "cross_sectional_rotation",
        "selection": {"ranking": {"sort_by": "last_month_return", "order": "desc"}},
    }

    patched = apply_schema_patch(
        schema,
        {
            "selection.ranking.sort_by": "monthly_return",
            "selection.ranking.lookback": "previous_month_return",
        },
    )

    assert schema["selection"]["ranking"]["sort_by"] == "last_month_return"
    assert patched["selection"]["ranking"]["sort_by"] == "monthly_return"
    assert patched["selection"]["ranking"]["lookback"] == "previous_month_return"


if __name__ == "__main__":
    test_inspect_macd_etf_data_ready()
    test_inspect_missing_stock_data_blocks()
    test_rotation_amount_ranking_uses_selection_daily_contract()
    test_previous_month_return_ranking_is_derived_from_local_prices()
    test_unsupported_rotation_factor_blocks_with_factor_context()
    test_data_research_schema_patch_updates_executable_schema_without_mutating_original()
    print("ok")
