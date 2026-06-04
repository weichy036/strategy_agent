from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json
import os
from pathlib import Path
from typing import Literal

from strategy_agent.data_update.status import DataStatusReport, collect_data_status


UpdateProfile = Literal["daily_light", "weekly_full"]


@dataclass(frozen=True)
class TushareEnvironment:
    token_present: bool
    token_hint: str | None


@dataclass(frozen=True)
class UpdateStep:
    name: str
    title: str
    reason: str
    required: bool


@dataclass(frozen=True)
class DataUpdatePlan:
    profile: UpdateProfile
    runnable: bool
    reason: str
    environment: TushareEnvironment
    status: DataStatusReport
    steps: list[UpdateStep]

    def to_dict(self) -> dict:
        return asdict(self)


def plan_data_update(
    *,
    profile: UpdateProfile = "daily_light",
    as_of: date | None = None,
    stale_after_days: int = 7,
    raw_root: Path | None = None,
    derived_root: Path | None = None,
) -> DataUpdatePlan:
    status = collect_data_status(
        as_of=as_of,
        stale_after_days=stale_after_days,
        raw_root=raw_root,
        derived_root=derived_root,
    )
    env = inspect_tushare_environment()
    steps = _build_steps(status, profile)
    runnable = env.token_present and any(step.required for step in steps)
    return DataUpdatePlan(
        profile=profile,
        runnable=runnable,
        reason=_reason(env, steps),
        environment=env,
        status=status,
        steps=steps,
    )


def inspect_tushare_environment() -> TushareEnvironment:
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    return TushareEnvironment(token_present=bool(token), token_hint=_mask_secret(token))


def main() -> None:
    print(json.dumps(plan_data_update().to_dict(), ensure_ascii=False, indent=2))


def _build_steps(status: DataStatusReport, profile: UpdateProfile) -> list[UpdateStep]:
    stale = set(status.stale_datasets)
    stock_sources_stale = bool(stale & {"daily_qfq", "daily_basic", "selection_daily", "selection_monthly"})
    market_sources_stale = bool(stale & {"fund_daily", "index_daily"})
    steps = [
        UpdateStep(
            name="refresh_meta",
            title="刷新基础信息",
            reason="同步股票列表、基金列表和交易日历，避免新上市或退市信息缺失。",
            required=bool(stale),
        ),
        UpdateStep(
            name="update_stock_daily",
            title="补股票日线",
            reason="daily_qfq 或选股因子需要股票原始日线作为输入。",
            required=stock_sources_stale,
        ),
        UpdateStep(
            name="update_adj_factor",
            title="补复权因子",
            reason="股票回测默认使用前复权数据，需要 adj_factor 参与重建。",
            required="daily_qfq" in stale,
        ),
        UpdateStep(
            name="update_daily_basic",
            title="补截面基础数据",
            reason="市值、成交额等截面选股因子来自 daily_basic。",
            required=bool(stale & {"daily_basic", "selection_daily", "selection_monthly"}),
        ),
        UpdateStep(
            name="update_fund_daily",
            title="补 ETF 日线",
            reason="ETF 回测直接读取 fund_daily。",
            required="fund_daily" in stale,
        ),
        UpdateStep(
            name="update_index_daily",
            title="补指数日线",
            reason="收益对比和基准展示需要 index_daily。",
            required="index_daily" in stale,
        ),
        UpdateStep(
            name="build_daily_qfq",
            title="重建前复权日线",
            reason="将 raw/daily 和 raw/adj_factor 合成为回测使用的 daily_qfq。",
            required="daily_qfq" in stale,
        ),
        UpdateStep(
            name="build_selection",
            title="重建选股截面",
            reason="月度轮动策略需要 selection_daily 和 selection_monthly。",
            required=bool(stale & {"selection_daily", "selection_monthly"}),
        ),
    ]
    if profile == "weekly_full":
        return [step if step.required else _force_step(step) for step in steps]
    return steps


def _force_step(step: UpdateStep) -> UpdateStep:
    return UpdateStep(name=step.name, title=step.title, reason=step.reason, required=True)


def _reason(env: TushareEnvironment, steps: list[UpdateStep]) -> str:
    if not env.token_present:
        return "TUSHARE_TOKEN 未配置，暂不能执行在线数据更新。"
    if not any(step.required for step in steps):
        return "本地数据未超过过期阈值，当前无需更新。"
    return "本地数据存在过期项，可以执行数据维护任务。"


def _mask_secret(value: str) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "***"
    return f"{value[:6]}***{value[-4:]}"


if __name__ == "__main__":
    main()
