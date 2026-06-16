from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json
from pathlib import Path
from typing import Literal

from strategy_agent.config import settings
from strategy_agent.data_update.daily_basic import update_daily_basic
from strategy_agent.data_update.market_series import update_fund_daily, update_index_daily
from strategy_agent.data_update.meta import refresh_meta
from strategy_agent.data_update.plan import DataUpdatePlan, UpdateProfile, plan_data_update
from strategy_agent.data_update.qfq import build_daily_qfq
from strategy_agent.data_update.selection import build_selection_data
from strategy_agent.data_update.stock_history import update_adj_factor, update_stock_daily
from strategy_agent.data_update.tushare_policy import TushareRetryPolicy


RunMode = Literal[
    "dry_run",
    "refresh_meta",
    "update_stock_daily",
    "update_adj_factor",
    "update_daily_basic",
    "update_fund_daily",
    "update_index_daily",
    "build_daily_qfq",
    "build_selection",
    "run_batch",
]
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
    max_codes: int = 20,
    sleep_seconds: float = 0.31,
    retry_max_attempts: int = 2,
    retry_delay_seconds: float = 2.0,
    stop_after_failures: int = 5,
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
    events = _events_for_mode(
        plan,
        mode=mode,
        max_codes=max_codes,
        sleep_seconds=sleep_seconds,
        retry_policy=_retry_policy(
            max_attempts=retry_max_attempts,
            delay_seconds=retry_delay_seconds,
            stop_after_failures=stop_after_failures,
        ),
        raw_root=raw_root,
        derived_root=derived_root,
        meta_dir=meta_dir,
        pro=pro,
    )
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
    parser.add_argument(
        "--mode",
        choices=[
            "dry_run",
            "refresh_meta",
            "update_stock_daily",
            "update_adj_factor",
            "update_daily_basic",
            "update_fund_daily",
            "update_index_daily",
            "build_daily_qfq",
            "build_selection",
            "run_batch",
        ],
        default="dry_run",
    )
    parser.add_argument("--profile", choices=["daily_light", "weekly_full"], default="daily_light")
    parser.add_argument("--max-codes", type=int, default=20)
    parser.add_argument("--sleep-seconds", type=float, default=0.31)
    parser.add_argument("--retry-max-attempts", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=2.0)
    parser.add_argument("--stop-after-failures", type=int, default=5)
    args = parser.parse_args()
    print(
        json.dumps(
            run_data_maintenance(
                mode=args.mode,
                profile=args.profile,
                max_codes=args.max_codes,
                sleep_seconds=args.sleep_seconds,
                retry_max_attempts=args.retry_max_attempts,
                retry_delay_seconds=args.retry_delay_seconds,
                stop_after_failures=args.stop_after_failures,
            ).to_dict(),
            ensure_ascii=False,
            indent=2,
        )
    )


def _events_for_mode(
    plan: DataUpdatePlan,
    *,
    mode: RunMode,
    max_codes: int = 20,
    sleep_seconds: float = 0.31,
    retry_policy: TushareRetryPolicy | None = None,
    raw_root: Path | None = None,
    derived_root: Path | None = None,
    meta_dir: Path | None = None,
    pro=None,
) -> list[MaintenanceStepEvent]:
    if mode == "dry_run":
        return _dry_run_events(plan)
    if mode == "refresh_meta":
        return _refresh_meta_events(plan, meta_dir=meta_dir, pro=pro)
    if mode == "update_stock_daily":
        return _update_stock_daily_events(
            plan,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
            raw_root=raw_root,
            derived_root=derived_root,
            meta_dir=meta_dir,
            pro=pro,
        )
    if mode == "update_adj_factor":
        return _update_adj_factor_events(
            plan,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
            raw_root=raw_root,
            derived_root=derived_root,
            meta_dir=meta_dir,
            pro=pro,
        )
    if mode == "update_daily_basic":
        return _update_daily_basic_events(
            plan,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
            raw_root=raw_root,
            meta_dir=meta_dir,
            pro=pro,
        )
    if mode == "update_fund_daily":
        return _update_fund_daily_events(
            plan,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
            raw_root=raw_root,
            meta_dir=meta_dir,
            pro=pro,
        )
    if mode == "update_index_daily":
        return _update_index_daily_events(
            plan,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
            raw_root=raw_root,
            pro=pro,
        )
    if mode == "build_daily_qfq":
        return _build_daily_qfq_events(plan, max_codes=max_codes, raw_root=raw_root, derived_root=derived_root)
    if mode == "build_selection":
        return _build_selection_events(plan)
    if mode == "run_batch":
        return _run_batch_events(
            plan,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
            raw_root=raw_root,
            derived_root=derived_root,
            meta_dir=meta_dir,
            pro=pro,
        )
    raise ValueError(f"Unsupported maintenance mode: {mode}")


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


def _update_stock_daily_events(
    plan: DataUpdatePlan,
    *,
    max_codes: int,
    sleep_seconds: float,
    retry_policy: TushareRetryPolicy | None,
    raw_root: Path | None = None,
    derived_root: Path | None = None,
    meta_dir: Path | None = None,
    pro=None,
) -> list[MaintenanceStepEvent]:
    if not plan.environment.token_present:
        return [
            MaintenanceStepEvent(
                name="environment",
                title="检查 Tushare 环境",
                state="blocked",
                message="TUSHARE_TOKEN 未配置，无法补股票日线。",
            )
        ]
    try:
        client = pro or _build_tushare_client()
        result = update_stock_daily(
            client,
            daily_dir=(raw_root or settings.raw_root) / "daily",
            qfq_dir=(derived_root or settings.derived_root) / "daily_qfq",
            meta_dir=meta_dir,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
        ).to_dict()
    except Exception as exc:  # noqa: BLE001
        return [
            MaintenanceStepEvent(
                name="update_stock_daily",
                title="补股票日线",
                state="failed",
                message=f"股票日线更新失败：{exc}",
            )
        ]
    return [_series_update_event("update_stock_daily", "补股票日线", result)]


def _update_adj_factor_events(
    plan: DataUpdatePlan,
    *,
    max_codes: int,
    sleep_seconds: float,
    retry_policy: TushareRetryPolicy | None,
    raw_root: Path | None = None,
    derived_root: Path | None = None,
    meta_dir: Path | None = None,
    pro=None,
) -> list[MaintenanceStepEvent]:
    if not plan.environment.token_present:
        return [
            MaintenanceStepEvent(
                name="environment",
                title="检查 Tushare 环境",
                state="blocked",
                message="TUSHARE_TOKEN 未配置，无法补复权因子。",
            )
        ]
    try:
        client = pro or _build_tushare_client()
        result = update_adj_factor(
            client,
            adj_factor_dir=(raw_root or settings.raw_root) / "adj_factor",
            qfq_dir=(derived_root or settings.derived_root) / "daily_qfq",
            meta_dir=meta_dir,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
        ).to_dict()
    except Exception as exc:  # noqa: BLE001
        return [
            MaintenanceStepEvent(
                name="update_adj_factor",
                title="补复权因子",
                state="failed",
                message=f"复权因子更新失败：{exc}",
            )
        ]
    return [_series_update_event("update_adj_factor", "补复权因子", result)]


def _update_daily_basic_events(
    plan: DataUpdatePlan,
    *,
    sleep_seconds: float,
    retry_policy: TushareRetryPolicy | None,
    raw_root: Path | None = None,
    meta_dir: Path | None = None,
    pro=None,
) -> list[MaintenanceStepEvent]:
    if not plan.environment.token_present:
        return [
            MaintenanceStepEvent(
                name="environment",
                title="检查 Tushare 环境",
                state="blocked",
                message="TUSHARE_TOKEN 未配置，无法补截面基础数据。",
            )
        ]
    try:
        client = pro or _build_tushare_client()
        target_dir = (raw_root or settings.raw_root) / "daily_basic"
        result = update_daily_basic(
            client,
            target_dir=target_dir,
            meta_dir=meta_dir,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
        ).to_dict()
    except Exception as exc:  # noqa: BLE001
        return [
            MaintenanceStepEvent(
                name="update_daily_basic",
                title="补截面基础数据",
                state="failed",
                message=f"截面基础数据更新失败：{exc}",
            )
        ]
    state: StepState = "succeeded" if result["ok"] else "failed"
    failures = result.get("failure_samples") or []
    failure_text = f" 错误样例：{'；'.join(failures)}" if failures else ""
    return [
        MaintenanceStepEvent(
            name="update_daily_basic",
            title="补截面基础数据",
            state=state,
            message=(
                "截面基础数据更新完成："
                f"请求 {len(result['requested_dates'])} 个交易日，"
                f"写入 {result['saved_count']} 个文件，"
                f"空结果 {result['empty_count']} 个，"
                f"失败 {result['failed_count']} 个。"
                f"{failure_text}"
            ),
        )
    ]


def _series_update_event(name: str, title: str, result: dict) -> MaintenanceStepEvent:
    state: StepState = "succeeded" if result["ok"] else "failed"
    failures = result.get("failure_samples") or []
    failure_text = f" 错误样例：{'；'.join(failures)}" if failures else ""
    return MaintenanceStepEvent(
        name=name,
        title=title,
        state=state,
        message=(
            f"{title}完成："
            f"请求 {len(result['requested_codes'])} 只股票，"
            f"更新 {result['updated_count']} 只，"
            f"跳过 {result['skipped_count']} 只，"
            f"空结果 {result['empty_count']} 只，"
            f"失败 {result['failed_count']} 只。"
            f"{failure_text}"
        ),
    )


def _update_fund_daily_events(
    plan: DataUpdatePlan,
    *,
    max_codes: int,
    sleep_seconds: float,
    retry_policy: TushareRetryPolicy | None,
    raw_root: Path | None = None,
    meta_dir: Path | None = None,
    pro=None,
) -> list[MaintenanceStepEvent]:
    if not plan.environment.token_present:
        return [
            MaintenanceStepEvent(
                name="environment",
                title="检查 Tushare 环境",
                state="blocked",
                message="TUSHARE_TOKEN 未配置，无法补 ETF 日线。",
            )
        ]
    try:
        client = pro or _build_tushare_client()
        result = update_fund_daily(
            client,
            target_dir=(raw_root or settings.raw_root) / "fund_daily",
            meta_dir=meta_dir,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
        ).to_dict()
    except Exception as exc:  # noqa: BLE001
        return [
            MaintenanceStepEvent(
                name="update_fund_daily",
                title="补 ETF 日线",
                state="failed",
                message=f"ETF 日线更新失败：{exc}",
            )
        ]
    return [_series_update_event("update_fund_daily", "补 ETF 日线", result)]


def _update_index_daily_events(
    plan: DataUpdatePlan,
    *,
    max_codes: int,
    sleep_seconds: float,
    retry_policy: TushareRetryPolicy | None,
    raw_root: Path | None = None,
    pro=None,
) -> list[MaintenanceStepEvent]:
    if not plan.environment.token_present:
        return [
            MaintenanceStepEvent(
                name="environment",
                title="检查 Tushare 环境",
                state="blocked",
                message="TUSHARE_TOKEN 未配置，无法补指数日线。",
            )
        ]
    try:
        client = pro or _build_tushare_client()
        result = update_index_daily(
            client,
            target_dir=(raw_root or settings.raw_root) / "index_daily",
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
        ).to_dict()
    except Exception as exc:  # noqa: BLE001
        return [
            MaintenanceStepEvent(
                name="update_index_daily",
                title="补指数日线",
                state="failed",
                message=f"指数日线更新失败：{exc}",
            )
        ]
    return [_series_update_event("update_index_daily", "补指数日线", result)]


def _build_daily_qfq_events(
    plan: DataUpdatePlan,
    *,
    max_codes: int,
    raw_root: Path | None = None,
    derived_root: Path | None = None,
) -> list[MaintenanceStepEvent]:
    try:
        result = build_daily_qfq(
            daily_dir=(raw_root or settings.raw_root) / "daily",
            adj_factor_dir=(raw_root or settings.raw_root) / "adj_factor",
            output_dir=(derived_root or settings.derived_root) / "daily_qfq",
            max_codes=max_codes,
        ).to_dict()
    except Exception as exc:  # noqa: BLE001
        return [
            MaintenanceStepEvent(
                name="build_daily_qfq",
                title="重建前复权日线",
                state="failed",
                message=f"前复权日线重建失败：{exc}",
            )
        ]
    state: StepState = "succeeded" if result["ok"] else "failed"
    return [
        MaintenanceStepEvent(
            name="build_daily_qfq",
            title="重建前复权日线",
            state=state,
            message=(
                "前复权日线重建完成："
                f"处理 {len(result['requested_codes'])} 只股票，"
                f"生成 {result['built_count']} 只，"
                f"跳过 {result['skipped_count']} 只，"
                f"失败 {result['failed_count']} 只。"
            ),
        )
    ]


def _build_selection_events(plan: DataUpdatePlan) -> list[MaintenanceStepEvent]:
    try:
        result = build_selection_data().to_dict()
    except Exception as exc:  # noqa: BLE001
        return [
            MaintenanceStepEvent(
                name="build_selection",
                title="构建选股截面",
                state="failed",
                message=f"选股截面构建失败：{exc}",
            )
        ]
    build_plan = result["plan"]
    latest_price_date = build_plan.get("latest_price_date") or "无"
    blocked_count = int(build_plan.get("blocked_after_price_date_count") or 0)
    blocked_text = f"，另有 {blocked_count} 个交易日需先补股票日线" if blocked_count else ""
    return [
        MaintenanceStepEvent(
            name="build_selection",
            title="构建选股截面",
            state="succeeded",
            message=(
                "选股截面检查完成："
                f"构建日截面 {result['built_daily_count']} 个，"
                f"构建月度因子 {result['built_monthly_count']} 个，"
                f"股票日线最新到 {latest_price_date}{blocked_text}。"
            ),
        )
    ]


def _run_batch_events(
    plan: DataUpdatePlan,
    *,
    max_codes: int,
    sleep_seconds: float,
    retry_policy: TushareRetryPolicy | None,
    raw_root: Path | None = None,
    derived_root: Path | None = None,
    meta_dir: Path | None = None,
    pro=None,
) -> list[MaintenanceStepEvent]:
    client = pro
    events: list[MaintenanceStepEvent] = []
    for step in [
        lambda: _update_stock_daily_events(
            plan,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
            raw_root=raw_root,
            derived_root=derived_root,
            meta_dir=meta_dir,
            pro=client,
        ),
        lambda: _update_adj_factor_events(
            plan,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
            raw_root=raw_root,
            derived_root=derived_root,
            meta_dir=meta_dir,
            pro=client,
        ),
        lambda: _update_fund_daily_events(
            plan,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
            raw_root=raw_root,
            meta_dir=meta_dir,
            pro=client,
        ),
        lambda: _update_index_daily_events(
            plan,
            max_codes=max_codes,
            sleep_seconds=sleep_seconds,
            retry_policy=retry_policy,
            raw_root=raw_root,
            pro=client,
        ),
        lambda: _build_daily_qfq_events(plan, max_codes=max_codes, raw_root=raw_root, derived_root=derived_root),
        lambda: _build_selection_events(plan),
    ]:
        events.extend(step())
        if events[-1].state in {"blocked", "failed"}:
            break
    return events


def _message(plan: DataUpdatePlan, *, mode: RunMode, events: list[MaintenanceStepEvent]) -> str:
    if mode == "refresh_meta":
        event = events[0] if events else None
        if event and event.state == "succeeded":
            return "基础信息刷新完成。"
        if event and event.state == "blocked":
            return "基础信息刷新已阻塞：TUSHARE_TOKEN 未配置。"
        return "基础信息刷新失败。"
    if mode == "update_stock_daily":
        event = events[0] if events else None
        if event and event.state == "succeeded":
            return "股票日线更新完成。"
        if event and event.state == "blocked":
            return "股票日线更新已阻塞：TUSHARE_TOKEN 未配置。"
        return "股票日线更新失败。"
    if mode == "update_adj_factor":
        event = events[0] if events else None
        if event and event.state == "succeeded":
            return "复权因子更新完成。"
        if event and event.state == "blocked":
            return "复权因子更新已阻塞：TUSHARE_TOKEN 未配置。"
        return "复权因子更新失败。"
    if mode == "update_daily_basic":
        event = events[0] if events else None
        if event and event.state == "succeeded":
            return "截面基础数据更新完成。"
        if event and event.state == "blocked":
            return "截面基础数据更新已阻塞：TUSHARE_TOKEN 未配置。"
        return "截面基础数据更新失败。"
    if mode == "update_fund_daily":
        event = events[0] if events else None
        if event and event.state == "succeeded":
            return "ETF 日线更新完成。"
        if event and event.state == "blocked":
            return "ETF 日线更新已阻塞：TUSHARE_TOKEN 未配置。"
        return "ETF 日线更新失败。"
    if mode == "update_index_daily":
        event = events[0] if events else None
        if event and event.state == "succeeded":
            return "指数日线更新完成。"
        if event and event.state == "blocked":
            return "指数日线更新已阻塞：TUSHARE_TOKEN 未配置。"
        return "指数日线更新失败。"
    if mode == "build_daily_qfq":
        event = events[0] if events else None
        if event and event.state == "succeeded":
            return "前复权日线重建完成。"
        return "前复权日线重建失败。"
    if mode == "build_selection":
        event = events[0] if events else None
        if event and event.state == "succeeded":
            return "选股截面构建检查完成。"
        return "选股截面构建失败。"
    if mode == "run_batch":
        if all(event.state == "succeeded" for event in events):
            return "数据维护批处理完成。"
        if any(event.state == "blocked" for event in events):
            return "数据维护批处理已阻塞。"
        return "数据维护批处理失败。"
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


def _retry_policy(*, max_attempts: int, delay_seconds: float, stop_after_failures: int) -> TushareRetryPolicy:
    return TushareRetryPolicy(
        max_attempts=max(1, int(max_attempts)),
        retry_delays=(max(0.0, float(delay_seconds)),),
        stop_after_failures=max(1, int(stop_after_failures)),
    )


if __name__ == "__main__":
    main()
