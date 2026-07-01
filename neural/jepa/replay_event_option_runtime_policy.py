from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import apply_event_nested_volume_backfill as nested_volume_backfill
import apply_event_stream_selector as stream_selector
from apply_event_monthly_volume_backfill import apply_backfill, load_trades as load_backfill_trades
from apply_event_static_union_cooldown import apply_static_union, load_trade_source
from apply_event_static_union_mtd_rescue import add_base_prior_mtd
from evaluate_xinput_level_filter import month_range
from walkforward_event_option_gate import metrics


DEFAULT_POLICY = Path("neural/models/jepa/jepa_production_event_options/event_option_policy.json")
DEFAULT_REGISTRY = Path("neural/models/jepa/jepa_production_event_options/component_registry.json")
DEFAULT_OUTPUT = Path("research_papers/JEPA/results/_diagnostics/event_option_runtime_policy_replay_2026janmay")

DEFAULT_SPXW_PRIMARY = Path(
    "research_papers/JEPA/results/"
    "event_option_spxw_h2_union_selector_backfill_base_t18_cap4_cd15_2026janmay_risk5000/combined_trades.csv"
)
DEFAULT_SPXW_FALLBACK = Path(
    "research_papers/JEPA/results/"
    "event_option_spxw_base_intraday_side_circuit_m19_2025h2_2026jun_risk5000/intraday_circuit_trades.csv"
)
DEFAULT_SPXW_EXPECTED = Path(
    "research_papers/JEPA/results/"
    "event_option_spxw_h2_union_selector_cap4_backfill_base_t18_2026janmay_risk5000/monthly_volume_backfill_trades.csv"
)

DEFAULT_SPY_EXPECTED = Path(
    "research_papers/JEPA/results/event_option_spy_static_ptdj_delta35_2026janmay_risk5000/combined_trades.csv"
)

DEFAULT_QQQ_META = Path(
    "research_papers/JEPA/results/event_trade_union_qqq_meta_grid_s1_pf0p0_wr0p0_2026jun/trade_union_meta_trades.csv"
)
DEFAULT_QQQ_CURRENT = Path(
    "research_papers/JEPA/results/"
    "event_option_qqq_nested_config_intraday_side_circuit_m18_pf11_wr42_2025h2hist_v2_2026janjun_risk5000/"
    "intraday_circuit_trades.csv"
)
DEFAULT_QQQ_ONLINE = Path(
    "research_papers/JEPA/results/"
    "event_option_qqq_union_d65_current_ptdjd80_scorethr_online_2026janmay_risk5000/"
    "trade_union_topk_regressor_trades.csv"
)
DEFAULT_QQQ_EXPECTED = Path(
    "research_papers/JEPA/results/"
    "event_option_qqq_static_union_metas1_current_online_mtdrescue1_cd45_2026janmay_risk5000/combined_trades.csv"
)

DEFAULT_COMBINED_EXPECTED = Path(
    "research_papers/JEPA/results/"
    "event_option_h2_spxw_cap4_qqq_mtdrescue1_spy_candidate_2026janmay_risk5000/combined_trades.csv"
)

DEFAULT_CANDIDATE_RESULT = Path(
    "research_papers/JEPA/results/"
    "event_option_current_best_plus_qqq_full20familyselector_partialonly_2026janjun_diag_risk5000"
)
DEFAULT_CANDIDATE_OUTPUT = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "event_option_current_best_full20family_partialonly_runtime_replay_2026janjun"
)
DEFAULT_CANDIDATE_SPXW_SELECTOR = Path(
    "research_papers/JEPA/results/"
    "event_option_spxw_stream_selector_s1_maxday7_base_s1_2026janjun_partial_risk5000/selector_metadata.json"
)
DEFAULT_CANDIDATE_SPY_NESTED = Path(
    "research_papers/JEPA/results/"
    "event_option_spy_nested_wincls_primary_fallback_m19_2026janmay_risk5000/metrics.json"
)
DEFAULT_CANDIDATE_SPY_JUNE_SELECTOR = Path(
    "research_papers/JEPA/results/"
    "event_option_spy_june_selector_nested_vs_topk_s2_202606_partial_risk5000/selector_metadata.json"
)
DEFAULT_CANDIDATE_QQQ_BACKFILL_CONFIG = Path(
    "research_papers/JEPA/results/"
    "event_option_qqq_current_backfill_full20familyselector_partialonly_auto_partial19_md8_cd30_2026janjun_diag/"
    "monthly_volume_backfill_config.csv"
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def ensure_path(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_hashes(args: argparse.Namespace) -> dict[str, dict[str, str]]:
    paths = {
        "policy": Path(args.policy),
        "registry": Path(args.registry),
        "spxw_primary": Path(args.spxw_primary),
        "spxw_fallback": Path(args.spxw_fallback),
        "spxw_expected": Path(args.spxw_expected),
        "spy_expected": Path(args.spy_expected),
        "qqq_meta": Path(args.qqq_meta),
        "qqq_current": Path(args.qqq_current),
        "qqq_online": Path(args.qqq_online),
        "qqq_expected": Path(args.qqq_expected),
        "combined_expected": Path(args.combined_expected),
    }
    out: dict[str, dict[str, str]] = {}
    for name, path in paths.items():
        checked = ensure_path(path, name)
        out[name] = {"path": str(checked), "sha256": file_sha256(checked)}
    return out


def filter_months(frame: pd.DataFrame, start_month: str, end_month: str) -> pd.DataFrame:
    months = set(month_range(str(start_month), str(end_month)))
    work = frame.copy()
    if "month" not in work.columns and "test_month" in work.columns:
        work["month"] = work["test_month"].astype(str)
    if "test_month" not in work.columns and "month" in work.columns:
        work["test_month"] = work["month"].astype(str)
    return work[work["month"].astype(str).isin(months)].copy()


def replay_spxw(args: argparse.Namespace) -> pd.DataFrame:
    policy_args = SimpleNamespace(
        primary_name="cap4",
        fallback_name="base",
        start_month=str(args.start_month),
        end_month=str(args.end_month),
        min_month_trades=int(args.spxw_min_month_trades),
        max_day=int(args.spxw_max_day),
        cooldown_minutes=int(args.spxw_cooldown_minutes),
    )
    primary = load_backfill_trades(ensure_path(Path(args.spxw_primary), "SPXW primary stream"), "cap4")
    fallback = load_backfill_trades(ensure_path(Path(args.spxw_fallback), "SPXW fallback stream"), "base")
    primary = primary[primary["ticker"].astype(str).str.upper().eq("SPXW")].copy()
    fallback = fallback[fallback["ticker"].astype(str).str.upper().eq("SPXW")].copy()
    return apply_backfill(primary, fallback, policy_args)


def replay_qqq(args: argparse.Namespace) -> pd.DataFrame:
    base_parts = [
        load_trade_source(f"meta_s1={args.qqq_meta}", "QQQ", 0),
        load_trade_source(f"current={args.qqq_current}", "QQQ", 1),
    ]
    rescue_parts = [
        load_trade_source(f"online={args.qqq_online}", "QQQ", 2),
    ]
    base_trades = pd.concat([part for part in base_parts if not part.empty], ignore_index=True, sort=False)
    rescue_trades = pd.concat([part for part in rescue_parts if not part.empty], ignore_index=True, sort=False)
    base_trades = filter_months(base_trades, str(args.start_month), str(args.end_month))
    rescue_trades = filter_months(rescue_trades, str(args.start_month), str(args.end_month))
    base_selected = apply_static_union(base_trades, int(args.qqq_max_day), int(args.qqq_cooldown_minutes))
    all_trades = pd.concat([base_trades, rescue_trades], ignore_index=True, sort=False)
    all_trades = add_base_prior_mtd(all_trades, base_selected)
    base_names = set(base_trades["static_source"].astype(str).unique())
    all_trades["mtd_rescue_active"] = (
        pd.to_numeric(all_trades["base_prior_mtd_return"], errors="coerce").fillna(0.0)
        <= float(args.qqq_trigger_threshold)
    )
    keep = all_trades["static_source"].astype(str).isin(base_names) | all_trades["mtd_rescue_active"].astype(bool)
    selected = apply_static_union(all_trades[keep].copy(), int(args.qqq_max_day), int(args.qqq_cooldown_minutes))
    if not selected.empty:
        selected["mtd_rescue_trigger_threshold"] = float(args.qqq_trigger_threshold)
        selected = selected.sort_values(["date", "entry_minute", "ticker", "static_source"], kind="stable").reset_index(drop=True)
    return selected


def load_expected(path: Path, start_month: str, end_month: str) -> pd.DataFrame:
    df = pd.read_csv(
        ensure_path(path, "expected trade stream"),
        dtype={"ticker": str, "date": str, "month": str, "test_month": str, "time": str},
        low_memory=False,
    )
    return filter_months(df, str(start_month), str(end_month))


def _namespace_with_defaults(raw: dict[str, Any], defaults: dict[str, Any]) -> SimpleNamespace:
    payload = {**defaults, **raw}
    return SimpleNamespace(**payload)


def replay_stream_selector(metadata_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata = read_json(ensure_path(metadata_path, "stream selector metadata"))
    args = _namespace_with_defaults(
        metadata.get("args", {}),
        {
            "select_months": 2,
            "risk_capital": 5000.0,
            "min_select_trades": 38,
            "min_select_month_trades": 19,
            "min_select_win_rate": 0.45,
            "min_select_pf": 1.30,
            "require_select_positive_months": False,
            "min_call_rate": 0.20,
            "max_call_rate": 0.80,
            "score_pf_weight": 3.0,
            "score_pf_cap": 4.0,
            "score_win_weight": 20.0,
            "score_return_weight": 0.10,
            "score_positive_month_weight": 4.0,
            "score_volume_weight": 0.10,
            "max_select_top5_share": float("inf"),
            "max_select_drawdown_to_pnl": float("inf"),
        },
    )
    streams: dict[str, pd.DataFrame] = {}
    source_specs: dict[str, str] = {}
    for spec in args.source:
        name, path = stream_selector.parse_source(str(spec))
        streams[name] = stream_selector.load_stream(
            path,
            name,
            str(args.ticker),
            str(args.history_start_month),
            str(args.end_month),
        )
        source_specs[name] = str(path)
    all_months = sorted(set().union(*[set(frame["test_month"].astype(str).unique()) for frame in streams.values()]))
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    for month in month_range(str(args.start_month), str(args.end_month)):
        previous = [m for m in all_months if m < str(month)]
        select_months = previous[-int(args.select_months):]
        selected_name = next(iter(streams))
        selected_score = -1e30
        selected_metrics = metrics(pd.DataFrame(), select_months)
        mode = "NO_HISTORY"
        if len(select_months) >= int(args.select_months):
            mode = "SELECTED"
            for name, frame in streams.items():
                select_frame = frame[frame["test_month"].astype(str).isin(select_months)].copy()
                row = metrics(select_frame, select_months)
                score = stream_selector.score_row(row, args)
                if score > selected_score:
                    selected_name = name
                    selected_score = score
                    selected_metrics = row
        test = streams[selected_name][streams[selected_name]["test_month"].astype(str).eq(str(month))].copy()
        if not test.empty:
            test["stream_selector_mode"] = mode
            test["stream_selector_source"] = selected_name
            test["stream_selector_select_months"] = ",".join(select_months)
            out_parts.append(test)
        test_metrics = metrics(test, [str(month)])
        row = {
            "ticker": str(args.ticker).upper(),
            "test_month": str(month),
            "mode": mode,
            "selected_source": selected_name,
            "source_path": source_specs.get(selected_name, ""),
            "train_months": ",".join([m for m in previous if m not in select_months]),
            "select_months": ",".join(select_months),
            "select_score": float(selected_score),
        }
        row.update({f"select_{key}": value for key, value in selected_metrics.items()})
        row.update({f"test_{key}": value for key, value in test_metrics.items()})
        fold_rows.append(row)
    trades = pd.concat(out_parts, ignore_index=True, sort=False) if out_parts else pd.DataFrame()
    return trades, pd.DataFrame(fold_rows)


def replay_nested_backfill(metrics_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    payload = read_json(ensure_path(metrics_path, "nested backfill metrics"))
    args = _namespace_with_defaults(
        payload.get("args", {}),
        {
            "select_months": 3,
            "target_month_trades": 19,
            "max_day": 8,
            "cooldown_minutes": 30,
            "risk_capital": 5000.0,
            "min_select_trades": 54,
            "min_select_month_trades": 19,
            "min_select_win_rate": 0.45,
            "min_select_pf": 1.30,
            "require_select_positive_months": False,
            "min_call_rate": 0.20,
            "max_call_rate": 0.80,
        },
    )
    ticker = str(args.ticker).upper()
    sources: dict[str, pd.DataFrame] = {}
    for spec in args.source:
        name, path = nested_volume_backfill.parse_source(str(spec))
        frame = load_backfill_trades(path, name)
        frame = frame[frame["ticker"].astype(str).str.upper().eq(ticker)].copy()
        frame = frame[
            (frame["month"].astype(str) >= str(args.history_start_month))
            & (frame["month"].astype(str) <= str(args.end_month))
        ].copy()
        sources[name] = frame
    pairs = [nested_volume_backfill.parse_pair(str(item)) for item in args.pair]
    eval_months = month_range(str(args.start_month), str(args.end_month))
    all_months = sorted(set().union(*[set(frame["month"].astype(str).unique()) for frame in sources.values()]))
    out_parts: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    for month in eval_months:
        previous = [m for m in all_months if m < str(month)]
        select_months = previous[-int(args.select_months):]
        best_pair = pairs[0]
        best_select = metrics(pd.DataFrame(), select_months)
        best_score = -1e30
        mode = "NO_HISTORY"
        if len(select_months) >= int(args.select_months):
            mode = "SELECTED"
            for primary, fallback in pairs:
                selected_history = nested_volume_backfill.run_pair(
                    sources,
                    primary,
                    fallback,
                    args,
                    select_months[0],
                    select_months[-1],
                )
                selected_history = selected_history[selected_history["month"].astype(str).isin(select_months)].copy()
                row = metrics(selected_history, select_months)
                score = nested_volume_backfill.score_metrics_for_selection(row, args)
                if score > best_score:
                    best_pair = (primary, fallback)
                    best_select = row
                    best_score = score
        test = nested_volume_backfill.run_pair(sources, best_pair[0], best_pair[1], args, str(month), str(month))
        if not test.empty:
            test["nested_primary"] = best_pair[0]
            test["nested_fallback"] = best_pair[1]
            test["nested_mode"] = mode
            test["nested_select_months"] = ",".join(select_months)
            out_parts.append(test)
        test_metrics = metrics(test, [str(month)])
        row = {
            "ticker": ticker,
            "test_month": str(month),
            "mode": mode,
            "primary": best_pair[0],
            "fallback": best_pair[1],
            "select_months": ",".join(select_months),
            "select_score": float(best_score),
        }
        row.update({f"select_{key}": value for key, value in best_select.items()})
        row.update({f"test_{key}": value for key, value in test_metrics.items()})
        fold_rows.append(row)
    trades = pd.concat(out_parts, ignore_index=True, sort=False) if out_parts else pd.DataFrame()
    return trades, pd.DataFrame(fold_rows)


def _as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def replay_monthly_backfill_from_config(config_path: Path) -> pd.DataFrame:
    cfg = pd.read_csv(ensure_path(config_path, "monthly backfill config")).iloc[0].to_dict()
    args = SimpleNamespace(
        primary_name=str(cfg["primary_name"]),
        fallback_name=str(cfg["fallback_name"]),
        start_month=str(cfg["start_month"]),
        end_month=str(cfg["end_month"]),
        min_month_trades=int(cfg["min_month_trades"]),
        auto_partial_month_target=_as_bool(cfg.get("auto_partial_month_target", False)),
        partial_month_observed_floor=int(cfg.get("partial_month_observed_floor", 0)),
        backfill_only_partial_months=_as_bool(cfg.get("backfill_only_partial_months", False)),
        max_day=int(cfg["max_day"]),
        cooldown_minutes=int(cfg["cooldown_minutes"]),
        min_entry_minute=int(cfg.get("min_entry_minute", 0)),
        risk_capital=float(cfg.get("risk_capital", 5000.0)),
    )
    primary = load_backfill_trades(Path(str(cfg["primary_trades"])), str(cfg["primary_name"]))
    fallback = load_backfill_trades(Path(str(cfg["fallback_trades"])), str(cfg["fallback_name"]))
    ticker = str(cfg.get("ticker", "")).upper()
    if ticker:
        primary = primary[primary["ticker"].astype(str).str.upper().eq(ticker)].copy()
        fallback = fallback[fallback["ticker"].astype(str).str.upper().eq(ticker)].copy()
    return apply_backfill(primary, fallback, args)


def canonical_for_compare(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    for col in ["ticker", "date", "time", "action", "expiry_mode"]:
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].astype(str)
    work["ticker"] = work["ticker"].str.upper()
    work["action"] = work["action"].str.upper()
    if "entry_minute" not in work.columns:
        if "minute" in work.columns:
            work["entry_minute"] = pd.to_numeric(work["minute"], errors="coerce")
        elif "minute_x" in work.columns:
            work["entry_minute"] = pd.to_numeric(work["minute_x"], errors="coerce")
        else:
            parsed = pd.to_datetime(work["time"].str[:5], format="%H:%M", errors="coerce")
            work["entry_minute"] = parsed.dt.hour * 60 + parsed.dt.minute
    work["entry_minute"] = pd.to_numeric(work["entry_minute"], errors="coerce").fillna(0).astype(int)
    sort_cols = ["ticker", "date", "entry_minute", "time", "action", "expiry_mode"]
    work = work.sort_values(sort_cols, kind="stable").reset_index(drop=True)
    key_cols = ["ticker", "date", "time", "action", "expiry_mode"]
    work["_key_occurrence"] = work.groupby(key_cols, sort=False).cumcount()
    return work


def compare_stream(name: str, actual: pd.DataFrame, expected: pd.DataFrame) -> dict[str, Any]:
    a = canonical_for_compare(actual)
    e = canonical_for_compare(expected)
    key_cols = ["ticker", "date", "time", "action", "expiry_mode", "_key_occurrence"]
    a_keys = a[key_cols].astype(str).agg("|".join, axis=1)
    e_keys = e[key_cols].astype(str).agg("|".join, axis=1)
    missing = sorted(set(e_keys).difference(set(a_keys)))
    extra = sorted(set(a_keys).difference(set(e_keys)))
    merged = e.assign(_cmp_key=e_keys).merge(
        a.assign(_cmp_key=a_keys),
        on="_cmp_key",
        how="inner",
        suffixes=("_expected", "_actual"),
    )
    return_diff = pd.Series(dtype=float)
    score_diff = pd.Series(dtype=float)
    if not merged.empty and {"realized_return_expected", "realized_return_actual"}.issubset(merged.columns):
        return_diff = (
            pd.to_numeric(merged["realized_return_expected"], errors="coerce").fillna(0.0)
            - pd.to_numeric(merged["realized_return_actual"], errors="coerce").fillna(0.0)
        ).abs()
    if not merged.empty and {"score_expected", "score_actual"}.issubset(merged.columns):
        score_diff = (
            pd.to_numeric(merged["score_expected"], errors="coerce").fillna(0.0)
            - pd.to_numeric(merged["score_actual"], errors="coerce").fillna(0.0)
        ).abs()
    passed = (
        int(len(a)) == int(len(e))
        and not missing
        and not extra
        and (return_diff.empty or float(return_diff.max()) <= 1e-9)
    )
    return {
        "name": name,
        "passed": bool(passed),
        "actual_rows": int(len(a)),
        "expected_rows": int(len(e)),
        "matched_rows": int(len(merged)),
        "missing_rows": int(len(missing)),
        "extra_rows": int(len(extra)),
        "max_abs_realized_return_diff": float(return_diff.max()) if not return_diff.empty else 0.0,
        "max_abs_score_diff": float(score_diff.max()) if not score_diff.empty else 0.0,
        "missing_preview": missing[:10],
        "extra_preview": extra[:10],
    }


def candidate_input_hashes(args: argparse.Namespace) -> dict[str, dict[str, str]]:
    paths = {
        "policy": Path(args.policy),
        "registry": Path(args.registry),
        "candidate_result": Path(args.candidate_result_dir) / "combined_trades.csv",
        "candidate_spxw_selector": Path(args.candidate_spxw_selector),
        "candidate_spy_nested": Path(args.candidate_spy_nested),
        "candidate_spy_june_selector": Path(args.candidate_spy_june_selector),
        "candidate_qqq_backfill_config": Path(args.candidate_qqq_backfill_config),
    }
    out: dict[str, dict[str, str]] = {}
    for name, path in paths.items():
        checked = ensure_path(path, name)
        out[name] = {"path": str(checked), "sha256": file_sha256(checked)}
    return out


def run_current_best_candidate_replay(args: argparse.Namespace, policy: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    result_dir = Path(args.candidate_result_dir)
    output_dir = Path(args.output_dir)

    spxw, spxw_folds = replay_stream_selector(Path(args.candidate_spxw_selector))
    spy_janmay, spy_janmay_folds = replay_nested_backfill(Path(args.candidate_spy_nested))
    spy_june, spy_june_folds = replay_stream_selector(Path(args.candidate_spy_june_selector))
    qqq = replay_monthly_backfill_from_config(Path(args.candidate_qqq_backfill_config))
    spy = pd.concat([spy_janmay, spy_june], ignore_index=True, sort=False)
    combined = pd.concat([spxw, spy, qqq], ignore_index=True, sort=False)
    if not combined.empty:
        combined = combined.sort_values(["date", "entry_minute", "ticker"], kind="stable").reset_index(drop=True)

    spxw.to_csv(output_dir / "replayed_spxw_trades.csv", index=False)
    spy_janmay.to_csv(output_dir / "replayed_spy_janmay_trades.csv", index=False)
    spy_june.to_csv(output_dir / "replayed_spy_june_trades.csv", index=False)
    spy.to_csv(output_dir / "replayed_spy_trades.csv", index=False)
    qqq.to_csv(output_dir / "replayed_qqq_trades.csv", index=False)
    combined.to_csv(output_dir / "replayed_combined_trades.csv", index=False)
    pd.concat([spxw_folds, spy_janmay_folds, spy_june_folds], ignore_index=True, sort=False).to_csv(
        output_dir / "replayed_selector_folds.csv",
        index=False,
    )

    spxw_expected = Path(args.candidate_spxw_selector).with_name("stream_selector_trades.csv")
    spy_janmay_expected = Path(args.candidate_spy_nested).with_name("nested_volume_backfill_trades.csv")
    spy_june_expected = Path(args.candidate_spy_june_selector).with_name("stream_selector_trades.csv")
    qqq_config = pd.read_csv(ensure_path(Path(args.candidate_qqq_backfill_config), "candidate QQQ config")).iloc[0].to_dict()
    qqq_expected = Path(str(qqq_config["output_dir"])) / "monthly_volume_backfill_trades.csv"
    combined_expected = result_dir / "combined_trades.csv"

    comparisons = [
        compare_stream("CANDIDATE_SPXW_SELECTOR", spxw, load_expected(spxw_expected, args.start_month, args.end_month)),
        compare_stream(
            "CANDIDATE_SPY_JANMAY_NESTED",
            spy_janmay,
            load_expected(spy_janmay_expected, args.start_month, args.end_month),
        ),
        compare_stream("CANDIDATE_SPY_JUNE_SELECTOR", spy_june, load_expected(spy_june_expected, args.start_month, args.end_month)),
        compare_stream("CANDIDATE_QQQ_PARTIAL_BACKFILL", qqq, load_expected(qqq_expected, args.start_month, args.end_month)),
        compare_stream("CANDIDATE_COMBINED", combined, load_expected(combined_expected, args.start_month, args.end_month)),
    ]
    months = month_range(str(args.start_month), str(args.end_month))
    by_ticker = {
        ticker: metrics(part, months)
        for ticker, part in combined.groupby("ticker", sort=True)
    } if not combined.empty else {}
    overall = metrics(combined, months)
    missing_live = registry.get("missing_for_full_live_equivalence", [])
    invalidated = (registry.get("invalidated_components") or {}).get("components", [])
    stateful_replay_passed = all(row["passed"] for row in comparisons)
    policy_status = str(policy.get("status", "")).lower()
    registry_status = str(registry.get("status", "")).lower()
    strict_live_ready_passed = (
        bool(stateful_replay_passed)
        and "live_ready" in policy_status
        and "research" not in policy_status
        and "incomplete" not in policy_status
        and "live_ready" in registry_status
        and "incomplete" not in registry_status
        and not missing_live
        and not invalidated
    )
    return {
        "stateful_replay_passed": bool(stateful_replay_passed),
        "strict_live_ready_passed": bool(strict_live_ready_passed),
        "policy": policy.get("policy", ""),
        "policy_status": policy.get("status", ""),
        "registry_status": registry.get("status", ""),
        "missing_live_equivalence_count": int(len(missing_live)) if isinstance(missing_live, list) else -1,
        "invalidated_component_count": int(len(invalidated)) if isinstance(invalidated, list) else -1,
        "comparisons": comparisons,
        "metrics": {
            "overall": overall,
            "by_ticker": by_ticker,
            "net_pnl": float(overall.get("pnl_return", 0.0)) * float(args.risk_capital),
            "risk_capital": float(args.risk_capital),
            "months": months,
        },
        "inputs": vars(args),
        "input_hashes": candidate_input_hashes(args),
        "note": (
            "This replay reconstructs the frozen Jan-Jun 2026 candidate from its saved source metadata and "
            "stateful policy transforms. It proves deterministic replay of the research package, not live "
            "feature-scorer equivalence for a future deploy month."
        ),
    }


def write_summary(output_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Event-Option Runtime Policy Replay",
        "",
        "This replay checks stateful runtime policy transforms against frozen causal trade streams. It is not new performance evidence and it does not retrain any model.",
        "",
        "## Result",
        "",
        f"- Stateful replay passed: {payload['stateful_replay_passed']}",
        f"- Strict live-ready passed: {payload['strict_live_ready_passed']}",
        f"- Registry status: {payload['registry_status']}",
        f"- Policy status: {payload['policy_status']}",
        f"- Missing live-equivalence items: {payload['missing_live_equivalence_count']}",
        "",
        "## Comparisons",
        "",
        "| Stream | Passed | Actual | Expected | Missing | Extra | Max Return Diff |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["comparisons"]:
        lines.append(
            f"| {row['name']} | {row['passed']} | {row['actual_rows']} | {row['expected_rows']} | "
            f"{row['missing_rows']} | {row['extra_rows']} | {row['max_abs_realized_return_diff']:.3g} |"
        )
    lines += [
        "",
        "## Metrics",
        "",
        "```json",
        json.dumps(payload["metrics"], indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay stateful event-option runtime policy transforms.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--spxw-primary", default=str(DEFAULT_SPXW_PRIMARY))
    parser.add_argument("--spxw-fallback", default=str(DEFAULT_SPXW_FALLBACK))
    parser.add_argument("--spxw-expected", default=str(DEFAULT_SPXW_EXPECTED))
    parser.add_argument("--spxw-min-month-trades", type=int, default=18)
    parser.add_argument("--spxw-max-day", type=int, default=4)
    parser.add_argument("--spxw-cooldown-minutes", type=int, default=15)
    parser.add_argument("--spy-expected", default=str(DEFAULT_SPY_EXPECTED))
    parser.add_argument("--qqq-meta", default=str(DEFAULT_QQQ_META))
    parser.add_argument("--qqq-current", default=str(DEFAULT_QQQ_CURRENT))
    parser.add_argument("--qqq-online", default=str(DEFAULT_QQQ_ONLINE))
    parser.add_argument("--qqq-expected", default=str(DEFAULT_QQQ_EXPECTED))
    parser.add_argument("--qqq-max-day", type=int, default=4)
    parser.add_argument("--qqq-cooldown-minutes", type=int, default=45)
    parser.add_argument("--qqq-trigger-threshold", type=float, default=1.0)
    parser.add_argument("--combined-expected", default=str(DEFAULT_COMBINED_EXPECTED))
    parser.add_argument("--candidate-current-best", action="store_true")
    parser.add_argument("--candidate-result-dir", default=str(DEFAULT_CANDIDATE_RESULT))
    parser.add_argument("--candidate-spxw-selector", default=str(DEFAULT_CANDIDATE_SPXW_SELECTOR))
    parser.add_argument("--candidate-spy-nested", default=str(DEFAULT_CANDIDATE_SPY_NESTED))
    parser.add_argument("--candidate-spy-june-selector", default=str(DEFAULT_CANDIDATE_SPY_JUNE_SELECTOR))
    parser.add_argument("--candidate-qqq-backfill-config", default=str(DEFAULT_CANDIDATE_QQQ_BACKFILL_CONFIG))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    policy = read_json(Path(args.policy))
    registry = read_json(Path(args.registry))

    if bool(args.candidate_current_best):
        payload = run_current_best_candidate_replay(args, policy, registry)
        (output_dir / "runtime_policy_replay_summary.json").write_text(
            json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8"
        )
        write_summary(output_dir, payload)
        print(json.dumps(payload, indent=2, allow_nan=True))
        return 0 if payload["stateful_replay_passed"] else 2

    spxw = replay_spxw(args)
    qqq = replay_qqq(args)
    spy = load_expected(Path(args.spy_expected), str(args.start_month), str(args.end_month))
    combined = pd.concat([spxw, spy, qqq], ignore_index=True, sort=False)
    if not combined.empty:
        combined = combined.sort_values(["date", "entry_minute", "ticker"], kind="stable").reset_index(drop=True)

    spxw.to_csv(output_dir / "replayed_spxw_trades.csv", index=False)
    qqq.to_csv(output_dir / "replayed_qqq_trades.csv", index=False)
    spy.to_csv(output_dir / "replayed_spy_trades.csv", index=False)
    combined.to_csv(output_dir / "replayed_combined_trades.csv", index=False)

    comparisons = [
        compare_stream("SPXW_CAP4_BACKFILL", spxw, load_expected(Path(args.spxw_expected), args.start_month, args.end_month)),
        compare_stream("QQQ_MTD_RESCUE", qqq, load_expected(Path(args.qqq_expected), args.start_month, args.end_month)),
        compare_stream("SPY_PTDJ", spy, load_expected(Path(args.spy_expected), args.start_month, args.end_month)),
        compare_stream("COMBINED", combined, load_expected(Path(args.combined_expected), args.start_month, args.end_month)),
    ]
    months = month_range(str(args.start_month), str(args.end_month))
    by_ticker = {
        ticker: metrics(part, months)
        for ticker, part in combined.groupby("ticker", sort=True)
    } if not combined.empty else {}
    overall = metrics(combined, months)
    missing_live = registry.get("missing_for_full_live_equivalence", [])
    invalidated = (registry.get("invalidated_components") or {}).get("components", [])
    stateful_replay_passed = all(row["passed"] for row in comparisons)
    policy_status = str(policy.get("status", "")).lower()
    registry_status = str(registry.get("status", "")).lower()
    strict_live_ready_passed = (
        bool(stateful_replay_passed)
        and not missing_live
        and not invalidated
        and "live_ready" in registry_status
        and "incomplete" not in registry_status
        and "research" not in registry_status
        and "live_ready" in policy_status
        and "incomplete" not in policy_status
        and "research" not in policy_status
    )
    payload = {
        "stateful_replay_passed": bool(stateful_replay_passed),
        "strict_live_ready_passed": bool(strict_live_ready_passed),
        "policy": policy.get("policy", ""),
        "policy_status": policy.get("status", ""),
        "registry_status": registry.get("status", ""),
        "missing_live_equivalence_count": int(len(missing_live)) if isinstance(missing_live, list) else -1,
        "invalidated_component_count": int(len(invalidated)) if isinstance(invalidated, list) else -1,
        "comparisons": comparisons,
        "metrics": {
            "overall": overall,
            "by_ticker": by_ticker,
            "net_pnl": float(overall.get("pnl_return", 0.0)) * float(args.risk_capital),
            "risk_capital": float(args.risk_capital),
            "months": months,
        },
        "inputs": vars(args),
        "input_hashes": input_hashes(args),
        "note": (
            "This is an exact replay of frozen stateful policy transforms. It does not prove that deploy-month "
            "model scores are identical to each historical walk-forward fold, because those fold models are "
            "intentionally not reused as deploy artifacts."
        ),
    }
    (output_dir / "runtime_policy_replay_summary.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8"
    )
    write_summary(output_dir, payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if stateful_replay_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
