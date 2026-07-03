from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from neural.jepa.event_option_component_live import EventOptionComponentRegistry, META_GATE_SCORE_COL, TOPK_SCORE_COL
except Exception:  # pragma: no cover - direct script execution from neural/jepa
    from event_option_component_live import EventOptionComponentRegistry, META_GATE_SCORE_COL, TOPK_SCORE_COL


DEFAULT_REGISTRY = Path("neural/models/jepa/jepa_production_event_options/component_registry.json")

EXPIRY_SUFFIX = {"zero_dte": "0dte", "front_weekly": "weekly"}
BOT_TICKER = {"SPXW": "SPX", "SPX": "SPX", "SPY": "SPY", "QQQ": "QQQ"}


def annotate_contract_profile(
    frame: pd.DataFrame,
    *,
    policy_ticker: str,
    delta_bucket: int,
    policy_source: str | None = None,
    policy_max_day: int | None = None,
    policy_cooldown_minutes: int | None = None,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    ticker = str(policy_ticker).upper()
    bucket = int(delta_bucket)
    out["policy_ticker"] = ticker
    out["bot_ticker"] = BOT_TICKER.get(ticker, ticker)
    out["event_delta_bucket"] = f"d{bucket:02d}"
    out["event_delta_target"] = float(bucket) / 100.0
    if "expiry_mode" in out.columns:
        out["option_snapshot_suffix"] = out["expiry_mode"].astype(str).map(EXPIRY_SUFFIX).fillna(out["expiry_mode"].astype(str))
    else:
        out["option_snapshot_suffix"] = ""
    if "action" in out.columns:
        out["event_direction"] = out["action"].astype(str).str.upper().map({"CALL": "LONG", "PUT": "SHORT"}).fillna("")
    if policy_source is not None:
        out["event_option_policy_source"] = str(policy_source)
    if policy_max_day is not None:
        out["policy_max_day"] = int(policy_max_day)
    if policy_cooldown_minutes is not None:
        out["policy_cooldown_minutes"] = int(policy_cooldown_minutes)
    return out


def component_max_trades_per_day(
    registry: EventOptionComponentRegistry,
    component_name: str,
    default: int,
) -> int:
    try:
        component = registry.component(component_name)
        deploy_config = component.registry_entry.get("deploy_config")
        if not isinstance(deploy_config, dict):
            deploy_config = component.metadata.get("deploy_config")
        if isinstance(deploy_config, dict) and deploy_config.get("max_trades_per_day") is not None:
            value = int(float(deploy_config["max_trades_per_day"]))
            return value if value > 0 else int(default)
    except Exception:
        return int(default)
    return int(default)


def latest_rows(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    work = frame.copy()
    sort_cols = [col for col in ["timestamp", "trade_date", "time", "minute"] if col in work.columns]
    if sort_cols:
        work = work.sort_values(sort_cols, kind="stable")
    keep_keys = [col for col in keys if col in work.columns]
    if not keep_keys:
        return work.tail(1).copy()
    return work.groupby(keep_keys, sort=False, as_index=False).tail(1).reset_index(drop=True)


def filter_snapshot(frame: pd.DataFrame, ticker: str, expiry_modes: list[str] | None = None) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    work = frame[frame["ticker"].astype(str).str.upper().eq(str(ticker).upper())].copy()
    if expiry_modes and "expiry_mode" in work.columns:
        allowed = {str(item) for item in expiry_modes}
        work = work[work["expiry_mode"].astype(str).isin(allowed)].copy()
    return latest_rows(work, ["ticker", "expiry_mode"])


def append_encoder(
    registry: EventOptionComponentRegistry,
    snapshots: pd.DataFrame,
    *,
    component_name: str,
    tickers: set[str],
    label: str,
    issues: list[str],
) -> pd.DataFrame:
    if snapshots.empty or component_name not in registry.components:
        return snapshots
    if "ticker" not in snapshots.columns:
        return snapshots
    present = set(snapshots["ticker"].astype(str).str.upper().unique())
    if not (present & tickers):
        return snapshots
    try:
        return registry.append_phys_td_jepa_features(component_name, snapshots)
    except Exception as exc:  # pragma: no cover - defensive live diagnostic path
        issues.append(f"{label} append failed: {type(exc).__name__}: {exc}")
        return snapshots


def append_required_encoders(registry: EventOptionComponentRegistry, snapshots: pd.DataFrame, issues: list[str]) -> pd.DataFrame:
    enriched = append_encoder(
        registry,
        snapshots,
        component_name="PTDJ.core_encoder",
        tickers={"SPY", "QQQ"},
        label="PTDJ",
        issues=issues,
    )
    return append_encoder(
        registry,
        enriched,
        component_name="TDVP.all13_encoder",
        tickers={"QQQ"},
        label="TDVP",
        issues=issues,
    )


def concat_frames(parts: list[pd.DataFrame]) -> pd.DataFrame:
    parts = [part for part in parts if part is not None and not part.empty]
    return pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()


def apply_score_threshold(frame: pd.DataFrame, score_col: str, threshold: object) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    try:
        value = float(threshold)
    except (TypeError, ValueError):
        return frame.copy()
    if not math.isfinite(value):
        return frame.copy()
    return frame[pd.to_numeric(frame[score_col], errors="coerce").fillna(float("-inf")) >= value].copy()


def gate_source(
    registry: EventOptionComponentRegistry,
    snapshots: pd.DataFrame,
    *,
    component: str,
    source: str,
    priority: int,
    strict: bool,
    issues: list[str],
    ticker: str,
    delta_bucket: int | None = None,
) -> pd.DataFrame:
    if component not in registry.components:
        issues.append(f"{ticker}: missing component {component}")
        return pd.DataFrame()
    try:
        scored = registry.score_gate_source(
            component,
            snapshots,
            source_variant=source,
            source_priority=priority,
            strict=strict,
            only_pass=True,
        )
        if delta_bucket is not None:
            scored = annotate_contract_profile(scored, policy_ticker=ticker, delta_bucket=int(delta_bucket))
        return scored
    except Exception as exc:
        issues.append(f"{ticker} {component} scoring failed: {type(exc).__name__}: {exc}")
        return pd.DataFrame()


def monthly_backfill_policy_names(registry: EventOptionComponentRegistry) -> list[str]:
    expected = ["SPXW.monthly_backfill18", "SPY.monthly_backfill18", "QQQ.monthly_backfill18"]
    names = [name for name in expected if name in registry.components]
    return names if len(names) == len(expected) else []


def score_monthly_backfill_policy(
    registry: EventOptionComponentRegistry,
    snapshots: pd.DataFrame,
    *,
    policy_name: str,
    strict: bool,
    issues: list[str],
) -> pd.DataFrame:
    try:
        policy = registry.monthly_volume_backfill_policy(policy_name)
    except Exception as exc:
        issues.append(f"{policy_name}: policy load failed: {type(exc).__name__}: {exc}")
        return pd.DataFrame()

    ticker = str(policy.get("ticker", policy_name.split(".", 1)[0])).upper()
    snap = filter_snapshot(snapshots, ticker, ["zero_dte"])
    if snap.empty:
        issues.append(f"{ticker}: no zero_dte snapshot row available")
        return pd.DataFrame()

    parts: list[pd.DataFrame] = []
    for role, component_key, name_key, delta_key, priority in [
        ("primary", "primary_component", "primary_name", "primary_delta_bucket", 0),
        ("fallback", "fallback_component", "fallback_name", "fallback_delta_bucket", 1),
    ]:
        component = str(policy.get(component_key, ""))
        if not component:
            issues.append(f"{policy_name}: missing {component_key}")
            continue
        delta_bucket = int(float(policy.get(delta_key, 25 if role == "primary" else 50)))
        source = str(policy.get(name_key, role))
        scored = gate_source(
            registry,
            snap,
            component=component,
            source=source,
            priority=priority,
            strict=strict,
            issues=issues,
            ticker=ticker,
            delta_bucket=delta_bucket,
        )
        if scored.empty:
            continue
        role_max_day = component_max_trades_per_day(
            registry,
            component,
            int(policy.get("max_day", 3)),
        )
        scored = annotate_contract_profile(
            scored,
            policy_ticker=ticker,
            delta_bucket=delta_bucket,
            policy_source=f"{ticker}_DENSE15_BACKFILL18",
            policy_max_day=role_max_day,
            policy_cooldown_minutes=int(policy.get("cooldown_minutes", 30)),
        )
        scored["monthly_policy_max_day"] = int(policy.get("max_day", 3))
        scored["component_policy_max_day"] = int(role_max_day)
        scored["source_stream"] = source
        scored["monthly_backfill_role"] = role
        scored["backfill_policy_component"] = policy_name
        scored["backfill_min_month_trades"] = int(policy.get("min_month_trades", 18))
        scored["runtime_state_required"] = "month_to_date_count,per_day_count,cooldown,dedupe"
        scored["live_ready_state"] = "needs_runtime_replay"
        parts.append(scored)

    return concat_frames(parts)


def score_dense_monthly_backfill_candidates(
    registry: EventOptionComponentRegistry,
    snapshots: pd.DataFrame,
    *,
    strict: bool,
    issues: list[str],
) -> pd.DataFrame:
    parts = [
        score_monthly_backfill_policy(
            registry,
            snapshots,
            policy_name=name,
            strict=strict,
            issues=issues,
        )
        for name in monthly_backfill_policy_names(registry)
    ]
    return concat_frames(parts)


def static_multi_delta_policy_names(registry: EventOptionComponentRegistry) -> list[str]:
    names = [
        name
        for name, component in registry.components.items()
        if component.kind == "event_static_multi_delta_union_policy"
    ]
    return sorted(names)


def score_static_multi_delta_policy(
    registry: EventOptionComponentRegistry,
    snapshots: pd.DataFrame,
    *,
    policy_name: str,
    strict: bool,
    issues: list[str],
) -> pd.DataFrame:
    try:
        policy = registry.json_component_payload(policy_name, "event_static_multi_delta_union_policy")
    except Exception as exc:
        issues.append(f"{policy_name}: static policy load failed: {type(exc).__name__}: {exc}")
        return pd.DataFrame()

    ticker = str(policy.get("ticker", policy_name.split(".", 1)[0])).upper()
    expiry_modes = policy.get("expiry_modes", ["zero_dte"])
    if not isinstance(expiry_modes, list) or not expiry_modes:
        expiry_modes = ["zero_dte"]
    snap = filter_snapshot(snapshots, ticker, [str(mode) for mode in expiry_modes])
    if snap.empty:
        issues.append(f"{ticker}: no {'/'.join(str(mode) for mode in expiry_modes)} snapshot row available")
        return pd.DataFrame()

    sources = policy.get("sources", [])
    if not isinstance(sources, list) or not sources:
        issues.append(f"{policy_name}: no sources configured")
        return pd.DataFrame()

    parts: list[pd.DataFrame] = []
    for fallback_priority, raw_source in enumerate(sources):
        if not isinstance(raw_source, dict):
            issues.append(f"{policy_name}: invalid source entry at index {fallback_priority}")
            continue
        component = str(raw_source.get("component", "")).strip()
        if not component:
            issues.append(f"{policy_name}: source {fallback_priority} missing component")
            continue
        source = str(raw_source.get("source_name", raw_source.get("variant", component)))
        priority = int(raw_source.get("priority", fallback_priority))
        delta_bucket = int(float(raw_source.get("delta_bucket", policy.get("delta_bucket", 25))))
        scored = gate_source(
            registry,
            snap,
            component=component,
            source=source,
            priority=priority,
            strict=strict,
            issues=issues,
            ticker=ticker,
            delta_bucket=delta_bucket,
        )
        min_score = raw_source.get("min_score", policy.get("min_score"))
        if min_score is not None and not scored.empty:
            scored = apply_score_threshold(scored, "score", min_score)
        if scored.empty:
            continue
        scored = annotate_contract_profile(
            scored,
            policy_ticker=ticker,
            delta_bucket=delta_bucket,
            policy_source=str(policy.get("policy_source", policy_name)),
            policy_max_day=int(policy.get("max_day", 999)),
            policy_cooldown_minutes=int(policy.get("cooldown_minutes", 0)),
        )
        scored["static_policy_component"] = str(policy_name)
        scored["static_policy_profile"] = str(policy.get("profile", "static_multi_delta_union"))
        scored["runtime_state_required"] = "per_day_count,cooldown,dedupe"
        scored["live_ready_state"] = "needs_execution_state"
        parts.append(scored)

    return concat_frames(parts)


def score_static_multi_delta_candidates(
    registry: EventOptionComponentRegistry,
    snapshots: pd.DataFrame,
    *,
    strict: bool,
    issues: list[str],
) -> pd.DataFrame:
    parts = [
        score_static_multi_delta_policy(
            registry,
            snapshots,
            policy_name=name,
            strict=strict,
            issues=issues,
        )
        for name in static_multi_delta_policy_names(registry)
    ]
    return concat_frames(parts)


def score_spxw(registry: EventOptionComponentRegistry, snapshots: pd.DataFrame, strict: bool, issues: list[str]) -> pd.DataFrame:
    snap = filter_snapshot(snapshots, "SPXW", ["front_weekly"])
    if snap.empty:
        issues.append("SPXW: no front_weekly snapshot row available")
        return pd.DataFrame()
    sources: list[pd.DataFrame] = []
    for component, source, priority in [
        ("SPXW.vol25_gate", "base", 0),
        ("SPXW.wide_d35_gate", "wideqfw", 2),
    ]:
        if component not in registry.components:
            issues.append(f"SPXW: missing component {component}")
            continue
        try:
            scored = registry.score_gate_source(
                component,
                snap,
                source_variant=source,
                source_priority=priority,
                strict=strict,
                only_pass=True,
            )
            if not scored.empty:
                scored = annotate_contract_profile(scored, policy_ticker="SPXW", delta_bucket=35)
                sources.append(scored)
        except Exception as exc:
            issues.append(f"SPXW {component} scoring failed: {type(exc).__name__}: {exc}")
    union = concat_frames(sources)
    if union.empty:
        return union
    selected = registry.materialize_trade_union_config("SPXW.h2_union_selector", union)
    if selected.empty:
        return selected
    selected = annotate_contract_profile(
        selected,
        policy_ticker="SPXW",
        delta_bucket=35,
        policy_source="SPXW_H2_CAP",
        policy_max_day=4,
        policy_cooldown_minutes=15,
    )
    selected["live_ready_state"] = "needs_cap_backfill_and_execution_state"
    selected["required_state_components"] = "SPXW.base_intraday_circuit,SPXW.cap4_monthly_backfill"
    selected["spxw_backfill_role"] = "primary"
    selected["source_stream"] = "cap4"
    selected["backfill_min_month_trades"] = 18

    fallback = pd.DataFrame()
    if "SPXW.vol25_gate" in registry.components:
        try:
            fallback = registry.score_gate_source(
                "SPXW.vol25_gate",
                snap,
                source_variant="base_fallback",
                source_priority=99,
                strict=strict,
                only_pass=True,
            )
            if not fallback.empty:
                fallback = annotate_contract_profile(
                    fallback,
                    policy_ticker="SPXW",
                    delta_bucket=35,
                    policy_source="SPXW_H2_CAP",
                    policy_max_day=4,
                    policy_cooldown_minutes=15,
                )
                fallback["spxw_backfill_role"] = "fallback"
                fallback["source_stream"] = "base"
                fallback["backfill_min_month_trades"] = 18
                fallback["live_ready_state"] = "needs_cap_backfill_and_execution_state"
                fallback["required_state_components"] = "SPXW.base_intraday_circuit,SPXW.cap4_monthly_backfill"
        except Exception as exc:
            issues.append(f"SPXW fallback scoring failed: {type(exc).__name__}: {exc}")
    return concat_frames([selected, fallback])


def score_spy(registry: EventOptionComponentRegistry, snapshots: pd.DataFrame, strict: bool, issues: list[str]) -> pd.DataFrame:
    policy = registry.static_gate_policy("SPY.static_ptdj_delta35")
    snap = filter_snapshot(snapshots, "SPY", ["zero_dte", "front_weekly"])
    if snap.empty:
        issues.append("SPY: no zero_dte/front_weekly snapshot row available")
        return pd.DataFrame()
    component = str(policy["source_component"])
    try:
        scored = registry.score_gate_source(
            component,
            snap,
            source_variant=str(policy.get("source_name", "ptdj")),
            source_priority=0,
            strict=strict,
            only_pass=True,
        )
    except Exception as exc:
        issues.append(f"SPY {component} scoring failed: {type(exc).__name__}: {exc}")
        return pd.DataFrame()
    if scored.empty:
        return scored
    scored = annotate_contract_profile(
        scored,
        policy_ticker="SPY",
        delta_bucket=35,
        policy_source="SPY_PTDJ",
        policy_max_day=int(policy["max_day"]),
        policy_cooldown_minutes=int(policy["cooldown_minutes"]),
    )
    scored["live_ready_state"] = "needs_execution_state"
    return scored


def score_qqq(registry: EventOptionComponentRegistry, snapshots: pd.DataFrame, strict: bool, issues: list[str]) -> pd.DataFrame:
    policy = registry.mtd_rescue_policy("QQQ.mtd_rescue")
    snap = filter_snapshot(snapshots, "QQQ", ["zero_dte", "front_weekly"])
    if snap.empty:
        issues.append("QQQ: no zero_dte/front_weekly snapshot row available")
        return pd.DataFrame()

    meta_union = concat_frames(
        [
            gate_source(
                registry,
                snap,
                component="QQQ.ptdj_d80_gate",
                source="ptdj_v1",
                priority=0,
                strict=strict,
                issues=issues,
                ticker="QQQ",
                delta_bucket=80,
            ),
            gate_source(
                registry,
                snap,
                component="QQQ.physics_gate",
                source="physics",
                priority=1,
                strict=strict,
                issues=issues,
                ticker="QQQ",
                delta_bucket=80,
            ),
        ]
    )
    meta_selected = pd.DataFrame()
    if not meta_union.empty and "QQQ.meta_s1_gate" in registry.components:
        meta_args = registry.component("QQQ.meta_s1_gate").metadata.get("args", {})
        meta_union = registry.materialize_max_day_cooldown(
            meta_union,
            max_day=int(meta_args.get("max_day", 999)),
            cooldown_minutes=int(meta_args.get("cooldown_minutes", 0)),
        )
        try:
            meta_scored = registry.score_meta_gate_component("QQQ.meta_s1_gate", meta_union, strict=strict)
            meta_selected = apply_score_threshold(
                meta_scored,
                META_GATE_SCORE_COL,
                registry.component("QQQ.meta_s1_gate").registry_entry.get("selected_threshold"),
            )
            if not meta_selected.empty:
                meta_selected["mtd_source"] = "meta_s1"
        except Exception as exc:
            issues.append(f"QQQ QQQ.meta_s1_gate scoring failed: {type(exc).__name__}: {exc}")

    current_union = concat_frames(
        [
            gate_source(
                registry,
                snap,
                component="QQQ.ptdj_d80_gate",
                source="ptdj_v1",
                priority=0,
                strict=strict,
                issues=issues,
                ticker="QQQ",
                delta_bucket=80,
            ),
            gate_source(
                registry,
                snap,
                component="QQQ.tdvp_gate",
                source="tdvp",
                priority=1,
                strict=strict,
                issues=issues,
                ticker="QQQ",
                delta_bucket=80,
            ),
        ]
    )
    current_selected = pd.DataFrame()
    if not current_union.empty and "QQQ.current_config_selector" in registry.components:
        try:
            current_selected = registry.materialize_trade_union_config("QQQ.current_config_selector", current_union)
            if not current_selected.empty:
                current_selected["mtd_source"] = "current"
                current_selected["runtime_state_note"] = "QQQ.current_intraday_circuit requires live known-exit state"
        except Exception as exc:
            issues.append(f"QQQ QQQ.current_config_selector materialization failed: {type(exc).__name__}: {exc}")

    online_current = current_selected.copy()
    if not online_current.empty:
        online_current["source_variant"] = "current"
        online_current["source_priority"] = 1
    online_union = concat_frames(
        [
            gate_source(
                registry,
                snap,
                component="QQQ.d65_gate",
                source="d65",
                priority=0,
                strict=strict,
                issues=issues,
                ticker="QQQ",
                delta_bucket=65,
            ),
            online_current,
            gate_source(
                registry,
                snap,
                component="QQQ.ptdj_d80_gate",
                source="ptdj_d80",
                priority=2,
                strict=strict,
                issues=issues,
                ticker="QQQ",
                delta_bucket=80,
            ),
        ]
    )
    online_selected = pd.DataFrame()
    if not online_union.empty and "QQQ.online_threshold_regressor" in registry.components:
        topk_args = registry.component("QQQ.online_threshold_regressor").metadata.get("args", {})
        online_union = registry.materialize_max_day_cooldown(
            online_union,
            max_day=int(topk_args.get("max_day", 999)),
            cooldown_minutes=int(topk_args.get("cooldown_minutes", 0)),
        )
        try:
            online_scored = registry.score_topk_component("QQQ.online_threshold_regressor", online_union, strict=strict)
            online_selected = apply_score_threshold(
                online_scored,
                TOPK_SCORE_COL,
                registry.component("QQQ.online_threshold_regressor").registry_entry.get("selected_score_threshold"),
            )
            if not online_selected.empty:
                online_selected["mtd_source"] = "online"
        except Exception as exc:
            issues.append(f"QQQ QQQ.online_threshold_regressor scoring failed: {type(exc).__name__}: {exc}")

    out = concat_frames([meta_selected, current_selected, online_selected])
    if out.empty:
        return out
    out = annotate_contract_profile(
        out,
        policy_ticker="QQQ",
        delta_bucket=80,
        policy_source="QQQ_MTD_RESCUE",
        policy_max_day=int(policy["max_day"]),
        policy_cooldown_minutes=int(policy["cooldown_minutes"]),
    )
    if "source_variant" in out.columns:
        is_d65 = out["source_variant"].astype(str).eq("d65")
        out.loc[is_d65, "event_delta_bucket"] = "d65"
        out.loc[is_d65, "event_delta_target"] = 0.65
    out["live_ready_state"] = "needs_mtd_rescue_and_execution_state"
    out["required_policy"] = "QQQ.mtd_rescue"
    out["mtd_rescue_trigger_threshold_return"] = float(policy["trigger_threshold_return"])
    out["runtime_state_required"] = "prior_completed_day_mtd,cooldown,dedupe,current_intraday_circuit"
    return out


def score_event_option_live_candidates(
    registry: EventOptionComponentRegistry,
    snapshots: pd.DataFrame,
    *,
    strict_features: bool = False,
) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    issues: list[str] = []
    static_policy_names = static_multi_delta_policy_names(registry)
    dense_policy_names = monthly_backfill_policy_names(registry)
    if static_policy_names:
        enriched = append_required_encoders(registry, snapshots.copy(), issues)
        candidates = score_static_multi_delta_candidates(
            registry,
            enriched,
            strict=bool(strict_features),
            issues=issues,
        )
    elif dense_policy_names:
        enriched = snapshots.copy()
        candidates = score_dense_monthly_backfill_candidates(
            registry,
            enriched,
            strict=bool(strict_features),
            issues=issues,
        )
    else:
        enriched = append_required_encoders(registry, snapshots, issues)
        parts = [
            score_spxw(registry, enriched, bool(strict_features), issues),
            score_spy(registry, enriched, bool(strict_features), issues),
            score_qqq(registry, enriched, bool(strict_features), issues),
        ]
        candidates = concat_frames(parts)
    if not candidates.empty:
        candidates["event_candidate_id"] = (
            candidates.get("policy_ticker", pd.Series("", index=candidates.index)).astype(str)
            + "|"
            + candidates.get("date", candidates.get("trade_date", pd.Series("", index=candidates.index))).astype(str)
            + "|"
            + candidates.get("time", pd.Series("", index=candidates.index)).astype(str)
            + "|"
            + candidates.get("expiry_mode", pd.Series("", index=candidates.index)).astype(str)
            + "|"
            + candidates.get("action", pd.Series("", index=candidates.index)).astype(str)
            + "|"
            + candidates.get("mtd_source", pd.Series("", index=candidates.index)).fillna("").astype(str)
            + "|"
            + candidates.get("source_variant", pd.Series("", index=candidates.index)).astype(str)
        )
    return candidates, issues, enriched


def serializable_summary(
    *,
    registry: EventOptionComponentRegistry,
    snapshot_path: Path,
    snapshots: pd.DataFrame,
    candidates: pd.DataFrame,
    issues: list[str],
) -> dict[str, Any]:
    by_ticker: dict[str, dict[str, Any]] = {}
    if not candidates.empty:
        for ticker, part in candidates.groupby("policy_ticker", sort=True):
            by_ticker[str(ticker)] = {
                "candidate_rows": int(len(part)),
                "sources": sorted(part.get("source_variant", pd.Series(dtype=str)).astype(str).unique().tolist()),
                "actions": sorted(part.get("action", pd.Series(dtype=str)).astype(str).unique().tolist()),
            }
    return {
        "snapshot_path": str(snapshot_path),
        "snapshot_rows": int(len(snapshots)),
        "candidate_rows": int(len(candidates)),
        "by_ticker": by_ticker,
        "registry": registry.summary(),
        "issues": issues,
        "live_ready": False,
        "live_ready_reason": "diagnostic scorer only; exact stateful bot replay equivalence is incomplete",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score event-option live snapshots with exported component registry.")
    parser.add_argument("--snapshots", required=True, help="Path to event_option_snapshots_latest.parquet")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--strict-features", action="store_true")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshots)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    registry = EventOptionComponentRegistry.from_path(Path(args.registry))
    snapshots = pd.read_parquet(snapshot_path)
    candidates, issues, enriched = score_event_option_live_candidates(
        registry,
        snapshots,
        strict_features=bool(args.strict_features),
    )
    if not candidates.empty:
        candidates.to_parquet(output_dir / "event_option_live_candidates.parquet", index=False)
        candidates.to_csv(output_dir / "event_option_live_candidates.csv", index=False)
    summary = serializable_summary(
        registry=registry,
        snapshot_path=snapshot_path,
        snapshots=snapshots,
        candidates=candidates,
        issues=issues,
    )
    (output_dir / "event_option_live_scorer_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
