from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json
from pathlib import Path
from typing import Literal

from strategy_agent.data_update.meta import refresh_meta
from strategy_agent.data_update.plan import DataUpdatePlan, UpdateProfile, plan_data_update


RunMode = Literal["dry_run", "refresh_meta"]
StepState = Literal["planned", "skipped", "blocked", "succeeded", "failed"]


@dataclass(frozen=True)
class MaintenanceStepEvent:
    name: str
    title: str
    state: StepState
    message: str


@dataclass(frozen=True)
class MaintenanceRunResult:
    ok: bool
    mode: RunMode
    profile: UpdateProfile
    message: str
    plan: DataUpdatePlan
    events: list[MaintenanceStepEvent]

    def to_dict(self) -> dict:
        return asdict(self)


def run_data_maintenance(
    *,
    profile: UpdateProfile = "daily_light",
    mode: RunMode = "dry_run",
    as_of: date | None = None,
    stale_after_days: int = 7,
    raw_root: Path | None = None,
    derived_root: Path | None = None,
    meta_dir: Path | None = None,
    pro=None,
) -> MaintenanceRunResult:
    plan = plan_data_update(
        profile=profile,
        as_of=as_of,
        stale_after_days=stale_after_days,
        raw_root=raw_root,
        derived_root=derived_root,
    )
    events = _dry_run_events(plan) if mode == "dry_run" else _refresh_meta_events(plan, meta_dir=meta_dir, pro=pro)
    return MaintenanceRunResult(
        ok=all(event.state != "failed" for event in events),
        mode=mode,
        profile=profile,
        message=_message(plan, mode=mode, events=events),
        plan=plan,
        events=events,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run data maintenance tasks.")
    parser.add_argument("--mode", choices=["dry_run", "refresh_meta"], default="dry_run")
    parser.add_argument("--profile", choices=["daily_light", "weekly_full"], default="daily_light")
    args = parser.parse_args()
    print(json.dumps(run_data_maintenance(mode=args.mode, profile=args.profile).to_dict(), ensure_ascii=False, indent=2))


def _dry_run_events(plan: DataUpdatePlan) -> list[MaintenanceStepEvent]:
    if not plan.environment.token_present:
        return [
            MaintenanceStepEvent(
                name="environment",
                title="检查 Tushare 环境",
                state="blocked",
                message="TUSHARE_TOKEN 未配置，无法执行在线数据维护。",
            )
        ]
    events: list[MaintenanceStepEvent] = []
    for step in plan.steps:
        if step.required:
            events.append(
                MaintenanceStepEvent(
                    name=step.name,
                    title=step.title,
                    state="planned",
                    message=f"dry-run：将执行「{step.title}」。",
                )
            )
        else:
            events.append(
                MaintenanceStepEvent(
                    name=step.name,
                    title=step.title,
                    state="skipped",
                    message=f"dry-run：跳过「{step.title}」，当前数据未超过过期阈值。",
                )
            )
    return events


def _refresh_meta_events(plan: DataUpdatePlan, *, meta_dir: Path | None = None, pro=None) -> list[MaintenanceStepEvent]:
    if not plan.environment.token_present:
        return [
            MaintenanceStepEvent(
                name="environment",
                title="检查 Tushare 环境",
                state="blocked",
                message="TUSHARE_TOKEN 未配置，无法执行基础信息刷新。",
            )
        ]
    try:
        client = pro or _build_tushare_client()
        result = refresh_meta(client, meta_dir=meta_dir).to_dict()
    except Exception as exc:  # noqa: BLE001
        return [
            MaintenanceStepEvent(
                name="refresh_meta",
                title="刷新基础信息",
                state="failed",
                message=f"基础信息刷新失败：{exc}",
            )
        ]
    return [
        MaintenanceStepEvent(
            name="refresh_meta",
            title="刷新基础信息",
            state="succeeded",
            message=(
                "基础信息已刷新："
                f"股票 {result['stock_count']} 只，"
                f"交易日 {result['trade_calendar_count']} 条，"
                f"ETF {result['fund_count']} 只。"
            ),
        )
    ]


def _message(plan: DataUpdatePlan, *, mode: RunMode, events: list[MaintenanceStepEvent]) -> str:
    if mode == "refresh_meta":
        event = events[0] if events else None
        if event and event.state == "succeeded":
            return "基础信息刷新完成。"
        if event and event.state == "blocked":
            return "基础信息刷新已阻塞：TUSHARE_TOKEN 未配置。"
        return "基础信息刷新失败。"
    if not plan.environment.token_present:
        return "数据维护 dry-run 已停止：TUSHARE_TOKEN 未配置。"
    planned_count = sum(1 for step in plan.steps if step.required)
    if planned_count == 0:
        return "数据维护 dry-run 完成：当前没有需要执行的更新步骤。"
    return f"数据维护 dry-run 完成：计划执行 {planned_count} 个步骤。"


def _build_tushare_client():
    import os

    import tushare as ts

    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is not set")
    return ts.pro_api(token=token)


if __name__ == "__main__":
    main()
