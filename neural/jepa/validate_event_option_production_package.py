from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_POLICY = Path("neural/models/jepa/jepa_production_event_options/event_option_policy.json")
DEFAULT_REGISTRY = Path("neural/models/jepa/jepa_production_event_options/component_registry.json")
DEFAULT_RAW_THETADATA_COVERAGE = Path(
    "research_papers/JEPA/results/_diagnostics/thetadata_0dte_raw_coverage_spxw_spy_qqq/raw_coverage.json"
)
LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES = {
    "phys_event_seq_in_day",
    "phys_event_frac_in_day",
    "phys_minutes_since_first_event",
    "phys_spot_ret_from_first_event_bps",
    "phys_same_day_event_count",
}
IB_LEVEL_FEATURE_PREFIXES = (
    "dist_ib_",
    "dist_fib_",
    "phys_ib_",
    "phys_fib_",
    "nearest_level_name_",
)
IB_LEVEL_CONTEXT_SUFFIXES = (
    "_ib_range_bps",
    "_nearest_level_abs_bps",
)
IB_LEVEL_FEATURES = {
    "ib_range_bps",
    "nearest_level_abs_bps",
    "phys_nearest_level_vs_ib_range",
}
IB_COMPLETE_MINUTE_ET = 10 * 60 + 30
SUMMARY_FILE_NAME = "SUMMARY.json"


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return read_json(path)
    except Exception:
        return {}


def resolve_repo_path(raw: str | Path) -> Path:
    path = Path(str(raw).replace("\\", "/"))
    return path if path.is_absolute() else Path.cwd() / path


def parse_hhmm_to_minute(value: Any, default: int) -> int:
    try:
        parts = str(value).strip()[:5].split(":")
        if len(parts) != 2:
            return int(default)
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return int(default)


def load_component_feature_cols(registry: dict[str, Any]) -> dict[str, list[str]]:
    components = registry.get("available_components")
    if not isinstance(components, dict):
        return {}
    out: dict[str, list[str]] = {}
    for name, entry in components.items():
        if not isinstance(entry, dict):
            continue
        raw_paths = [entry.get("metadata"), entry.get("path")]
        feature_cols: list[str] = []
        for raw_path in raw_paths:
            if not raw_path:
                continue
            path = resolve_repo_path(str(raw_path))
            if not path.exists() or path.suffix.lower() != ".json":
                continue
            try:
                payload = read_json(path)
            except Exception:
                continue
            cols = payload.get("feature_cols", payload.get("features", []))
            if isinstance(cols, list):
                feature_cols = [str(col) for col in cols]
                break
        if feature_cols:
            out[str(name)] = feature_cols
    return out


def assert_live_observable_feature_contract(
    policy: dict[str, Any],
    registry: dict[str, Any],
    issues: list[str],
) -> None:
    """Reject live-ready packages that score on features not observable live.

    These checks target feature construction contracts, not distribution drift:
    - phys_event_* intraday-state features are not built from the same row
      sequence in offline candidate datasets and live snapshot history.
    - IB/fib level features are only fully observable once the 9:30-10:30 ET
      initial balance is complete.
    """
    live_contract = policy.get("live_contract") if isinstance(policy.get("live_contract"), dict) else {}
    entry_start = parse_hhmm_to_minute(live_contract.get("entry_time_min_et", "10:00"), 10 * 60)
    by_component = load_component_feature_cols(registry)
    for component, features in sorted(by_component.items()):
        feature_set = set(features)
        bad_intraday = sorted(feature_set & LIVE_INCONSISTENT_INTRADAY_STATE_FEATURES)
        if bad_intraday:
            issues.append(
                f"{component}: uses live-inconsistent intraday state features {bad_intraday}"
            )
        ib_features = sorted(
            col
            for col in feature_set
            if (
                col in IB_LEVEL_FEATURES
                or any(col.startswith(prefix) for prefix in IB_LEVEL_FEATURE_PREFIXES)
                or (col.startswith("ctx_") and any(col.endswith(suffix) for suffix in IB_LEVEL_CONTEXT_SUFFIXES))
            )
        )
        if ib_features and entry_start < IB_COMPLETE_MINUTE_ET:
            preview = ", ".join(ib_features[:12])
            extra = "" if len(ib_features) <= 12 else f" ... +{len(ib_features) - 12}"
            issues.append(
                f"{component}: uses initial-balance/fib features before IB completion "
                f"(entry_time_min_et={live_contract.get('entry_time_min_et', '10:00')}); "
                f"features={preview}{extra}"
            )


def _dataset_summary_for_label_data(label_data: Path) -> dict[str, Any]:
    """Return the build summary for the original event-option dataset, if present."""
    direct = read_json_if_exists(label_data.parent / SUMMARY_FILE_NAME)
    if isinstance(direct.get("args"), dict):
        return direct
    raw_input = direct.get("input")
    if raw_input:
        raw_path = resolve_repo_path(str(raw_input))
        nested = read_json_if_exists(raw_path.parent / SUMMARY_FILE_NAME)
        if isinstance(nested.get("args"), dict):
            return nested
    return direct


def _candidate_universe_filter(policy: dict[str, Any]) -> dict[str, Any]:
    live_contract = policy.get("live_contract") if isinstance(policy.get("live_contract"), dict) else {}
    raw = live_contract.get("candidate_universe_filter")
    return raw if isinstance(raw, dict) else {}


def _read_trade_minutes(path: Path) -> pd.Series:
    if not path.exists():
        return pd.Series(dtype=float)
    try:
        trades = pd.read_csv(path, usecols=lambda c: c in {"minute", "entry_minute", "time"}, low_memory=False)
    except Exception:
        return pd.Series(dtype=float)
    for col in ("minute", "entry_minute"):
        if col in trades.columns:
            values = pd.to_numeric(trades[col], errors="coerce")
            if values.notna().any():
                return values
    if "time" in trades.columns:
        parsed = pd.to_datetime(trades["time"].astype(str).str[:5], format="%H:%M", errors="coerce")
        return parsed.dt.hour * 60 + parsed.dt.minute
    return pd.Series(dtype=float)


def assert_candidate_universe_causality(
    policy: dict[str, Any],
    validation: dict[str, Any],
    trades_path: Path,
    issues: list[str],
) -> None:
    """Reject live packages whose historical candidate universe cannot exist live.

    A common trap is a dataset filtered with full initial-balance/fib levels while
    also allowing entries before 10:30 ET. That leaks the final 9:30-10:30 range
    through the row-selection process even when IB columns are not model inputs.
    """
    integrity = validation.get("integrity") if isinstance(validation.get("integrity"), dict) else {}
    label_data_raw = integrity.get("label_data")
    if not label_data_raw:
        return
    label_data = resolve_repo_path(str(label_data_raw))
    summary = _dataset_summary_for_label_data(label_data)
    args = summary.get("args") if isinstance(summary.get("args"), dict) else {}
    near_level_only = bool(args.get("near_level_only", False))
    if not near_level_only:
        return

    try:
        source_start_minute = int(float(args.get("start_minute", 0)))
    except (TypeError, ValueError):
        source_start_minute = 0
    try:
        near_level_bps = float(args.get("near_level_bps", 20.0))
    except (TypeError, ValueError):
        near_level_bps = 20.0

    candidate_filter = _candidate_universe_filter(policy)
    raw_live_filter = candidate_filter.get("near_level_abs_bps_max")
    try:
        live_near_level_bps = float(raw_live_filter)
    except (TypeError, ValueError):
        live_near_level_bps = float("nan")
    if not pd.notna(live_near_level_bps):
        issues.append(
            "candidate universe mismatch: label_data was built with near_level_only=true "
            f"(near_level_bps={near_level_bps:g}) but live_contract.candidate_universe_filter."
            "near_level_abs_bps_max is missing"
        )
    elif live_near_level_bps > near_level_bps:
        issues.append(
            "candidate universe mismatch: live near_level_abs_bps_max "
            f"{live_near_level_bps:g} is wider than label_data near_level_bps {near_level_bps:g}"
        )

    live_contract = policy.get("live_contract") if isinstance(policy.get("live_contract"), dict) else {}
    entry_start = parse_hhmm_to_minute(live_contract.get("entry_time_min_et", "10:00"), 10 * 60)
    uses_ib_level_universe = source_start_minute < IB_COMPLETE_MINUTE_ET
    if uses_ib_level_universe and entry_start < IB_COMPLETE_MINUTE_ET:
        issues.append(
            "candidate universe lookahead: label_data near_level_only uses complete IB/fib levels "
            f"from 09:30-10:30 ET but live entry_time_min_et={live_contract.get('entry_time_min_et', '10:00')}; "
            "earliest safe matching entry is 10:30 ET"
        )

    minutes = _read_trade_minutes(trades_path)
    if uses_ib_level_universe and not minutes.empty:
        pre_ib_count = int((pd.to_numeric(minutes, errors="coerce") < IB_COMPLETE_MINUTE_ET).sum())
        if pre_ib_count > 0:
            issues.append(
                "candidate universe lookahead: completed-month trades include "
                f"{pre_ib_count} entries before 10:30 ET from a near_level_only IB/fib-filtered dataset"
            )


def _month_values(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(value) for value in raw if len(str(value)) == 6 and str(value).isdigit()]


def assert_policy_selection_causality(
    policy: dict[str, Any],
    registry: dict[str, Any],
    validation_months: list[str],
    issues: list[str],
) -> None:
    """Require evidence that every reported month was unseen by its selector.

    Model weights frozen before an evaluation window are insufficient when the
    threshold, action, time window, cooldown, or risk guard was optimized on
    that same window.  A live-ready package must describe either a single
    fixed pre-OOS selection or a nested monthly walk-forward protocol.
    """

    provenance = policy.get("policy_selection_provenance")
    if not isinstance(provenance, dict):
        issues.append("policy_selection_provenance missing; cannot prove policy-selection OOS")
        provenance = {}
    if provenance.get("passed") is not True:
        issues.append("policy_selection_provenance.passed is not true")

    mode = str(provenance.get("mode", "")).strip().lower()
    expected = [str(month) for month in validation_months]
    declared_eval = _month_values(provenance.get("evaluation_months"))
    if declared_eval != expected:
        issues.append(
            "policy_selection_provenance.evaluation_months does not match "
            "completed_month_validation.months"
        )

    if mode == "fixed_pre_oos":
        train_months = _month_values(provenance.get("training_months"))
        select_months = _month_values(provenance.get("selection_months"))
        source_months = sorted(set(train_months + select_months))
        overlap = sorted(set(source_months) & set(expected))
        if overlap:
            issues.append(f"fixed policy selection uses reported OOS months: {overlap}")
        if expected and any(month >= min(expected) for month in source_months):
            issues.append("fixed policy training/selection months are not strictly before the OOS window")
        if provenance.get("policy_frozen_before_evaluation") is not True:
            issues.append("fixed policy was not declared frozen before evaluation")
    elif mode == "nested_walk_forward":
        if provenance.get("selection_protocol_frozen_before_evaluation") is not True:
            issues.append("nested selection protocol was not frozen before evaluation")
        if str(provenance.get("trade_artifact_kind", "")) != "nested_walk_forward_fold_outputs":
            issues.append(
                "nested policy selection must declare trade_artifact_kind=nested_walk_forward_fold_outputs"
            )
        raw_folds = provenance.get("folds")
        folds = raw_folds if isinstance(raw_folds, list) else []
        by_month = {
            str(fold.get("evaluation_month")): fold
            for fold in folds
            if isinstance(fold, dict) and fold.get("evaluation_month") is not None
        }
        for month in expected:
            fold = by_month.get(month)
            if not isinstance(fold, dict):
                issues.append(f"nested policy-selection fold missing for {month}")
                continue
            sources = _month_values(fold.get("training_months")) + _month_values(fold.get("selection_months"))
            bad = sorted({source for source in sources if source >= month})
            if bad:
                issues.append(f"nested fold {month} uses non-prior training/selection months: {bad}")
            if not sources:
                issues.append(f"nested fold {month} has no declared training/selection months")
            if fold.get("policy_frozen_before_evaluation") is not True:
                issues.append(f"nested fold {month} was not frozen before its evaluation month")
            if not str(fold.get("policy_artifact_sha256", "")).strip():
                issues.append(f"nested fold {month} policy_artifact_sha256 missing")
    else:
        issues.append(f"unsupported policy_selection_provenance.mode={mode!r}")

    # Registry metadata provides a second, independently inspectable signal.
    # For fixed-policy evidence, any component selection overlap is fatal.
    if mode != "nested_walk_forward":
        components = registry.get("available_components")
        if isinstance(components, dict):
            for name, entry in sorted(components.items()):
                if not isinstance(entry, dict):
                    continue
                overlap = sorted(set(_month_values(entry.get("select_months"))) & set(expected))
                if overlap:
                    issues.append(f"{name}: select_months overlap reported OOS months {overlap}")


def assert_executable_quote_contract(
    policy: dict[str, Any],
    validation: dict[str, Any],
    issues: list[str],
) -> None:
    label_contract = policy.get("validated_label_exit_contract")
    label_contract = label_contract if isinstance(label_contract, dict) else {}
    if str(label_contract.get("option_price_mode", "")).strip().lower() != "executable_quote":
        issues.append("validated labels are not executable_quote (ask entry / bid mark and exit)")
    if str(label_contract.get("entry_price_field", "")).strip().lower() != "ask":
        issues.append("validated_label_exit_contract.entry_price_field must be ask")
    if str(label_contract.get("mark_price_field", "")).strip().lower() != "bid":
        issues.append("validated_label_exit_contract.mark_price_field must be bid")
    if str(label_contract.get("exit_price_field", "")).strip().lower() != "bid":
        issues.append("validated_label_exit_contract.exit_price_field must be bid")

    live_contract = policy.get("live_contract") if isinstance(policy.get("live_contract"), dict) else {}
    if str(live_contract.get("position_overlap_policy", "")).strip().lower() != "reject_while_open":
        issues.append("live_contract.position_overlap_policy must be reject_while_open")

    integrity = validation.get("integrity") if isinstance(validation.get("integrity"), dict) else {}
    label_data_raw = integrity.get("label_data")
    if label_data_raw:
        summary = _dataset_summary_for_label_data(resolve_repo_path(str(label_data_raw)))
        args = summary.get("args") if isinstance(summary.get("args"), dict) else {}
        if str(args.get("option_price_mode", "")).strip().lower() != "executable_quote":
            issues.append("label dataset SUMMARY.args.option_price_mode is not executable_quote")


def _profit_factor(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    gains = float(numeric[numeric > 0.0].sum())
    losses = abs(float(numeric[numeric < 0.0].sum()))
    if losses <= 0.0:
        return float("inf") if gains > 0.0 else 0.0
    return gains / losses


def recompute_trade_metrics(
    trades: pd.DataFrame,
    *,
    validation_months: list[str],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    if trades.empty or "ticker" not in trades.columns or "realized_return" not in trades.columns:
        return out
    work = trades.copy()
    work["ticker"] = work["ticker"].astype(str).str.upper()
    if "month" in work.columns:
        work["month"] = work["month"].astype(str).str.replace(r"\.0$", "", regex=True)
    elif "trade_date" in work.columns:
        work["month"] = work["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:6]
    else:
        work["month"] = ""
    work = work[work["month"].isin([str(month) for month in validation_months])].copy()
    work["realized_return"] = pd.to_numeric(work["realized_return"], errors="coerce")
    work = work.dropna(subset=["realized_return"])
    for ticker, part in work.groupby("ticker", sort=True):
        values = part["realized_return"].astype(float)
        counts = part.groupby("month", sort=True).size().reindex(validation_months, fill_value=0)
        pnl = part.groupby("month", sort=True)["realized_return"].sum().reindex(validation_months, fill_value=0.0)
        out[str(ticker)] = {
            "trades": float(len(part)),
            "win_rate": float((values > 0.0).mean()) if len(part) else 0.0,
            "profit_factor": float(_profit_factor(values)),
            "pnl_return": float(values.sum()),
            "min_month_trades": float(counts.min()) if len(counts) else 0.0,
            "positive_month_rate": float((pnl > 0.0).mean()) if len(pnl) else 0.0,
        }
    return out


def assert_trade_artifact_live_equivalence(
    policy: dict[str, Any],
    validation: dict[str, Any],
    trades: pd.DataFrame,
    validation_months: list[str],
    required_tickers: list[str],
    min_win_rate: float,
    min_profit_factor: float,
    min_month_trades: int,
    issues: list[str],
) -> None:
    if trades.empty:
        issues.append("combined trades are empty; metrics cannot be recomputed")
        return
    required = {"ticker", "minute", "exit_minutes", "realized_return"}
    missing = sorted(required - set(trades.columns))
    if missing:
        issues.append(f"combined trades missing live-equivalence columns: {missing}")
        return

    if "month" in trades.columns:
        artifact_month = trades["month"].astype(str).str.replace(r"\.0$", "", regex=True)
    elif "trade_date" in trades.columns:
        artifact_month = trades["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:6]
    else:
        artifact_month = pd.Series("", index=trades.index)
    extra_months = sorted(set(artifact_month) - set(str(month) for month in validation_months))
    if extra_months:
        issues.append(f"combined trades contain undeclared months outside validation window: {extra_months}")
    trades = trades[artifact_month.isin([str(month) for month in validation_months])].copy()
    if trades.empty:
        issues.append("combined trades contain no rows in the declared validation months")
        return

    metrics = recompute_trade_metrics(trades, validation_months=validation_months)
    advertised = validation.get("by_ticker") if isinstance(validation.get("by_ticker"), dict) else {}
    for ticker in required_tickers:
        row = metrics.get(ticker)
        if not isinstance(row, dict):
            issues.append(f"{ticker}: no recomputable trades")
            continue
        expected = advertised.get(ticker) if isinstance(advertised, dict) else None
        if not isinstance(expected, dict):
            issues.append(f"{ticker}: advertised completed-month metrics missing")
        else:
            assert_metric_payload_matches(
                f"recomputed.{ticker}",
                {key: row[key] for key in ("trades", "win_rate", "profit_factor", "pnl_return", "min_month_trades", "positive_month_rate")},
                expected,
                issues,
            )
        assert_strict_metric_gate(f"recomputed.{ticker}.win_rate", row["win_rate"], min_win_rate, issues)
        assert_strict_metric_gate(f"recomputed.{ticker}.profit_factor", row["profit_factor"], min_profit_factor, issues)
        if row["min_month_trades"] <= float(min_month_trades):
            issues.append(
                f"recomputed.{ticker}.min_month_trades {row['min_month_trades']:.0f} "
                f"<= strict live target {min_month_trades}"
            )
        if row["positive_month_rate"] < 1.0:
            issues.append(f"recomputed.{ticker}.positive_month_rate {row['positive_month_rate']:.6g} < 1")

    live_contract = policy.get("live_contract") if isinstance(policy.get("live_contract"), dict) else {}
    candidate_filter = _candidate_universe_filter(policy)
    try:
        cadence = int(float(live_contract.get("entry_sample_minutes", 0)))
    except (TypeError, ValueError):
        cadence = 0
    try:
        filter_cadence = int(float(candidate_filter.get("entry_sample_minutes", 0)))
    except (TypeError, ValueError):
        filter_cadence = 0
    anchor = parse_hhmm_to_minute(candidate_filter.get("entry_sample_anchor_minute_et", ""), -1)
    if cadence <= 0 or filter_cadence != cadence or anchor < 0:
        issues.append("live entry sampling cadence/anchor is missing or inconsistent")
    else:
        minutes = pd.to_numeric(trades["minute"], errors="coerce")
        off_grid = int((minutes.isna() | (((minutes - anchor) % cadence) != 0)).sum())
        if off_grid:
            issues.append(f"combined trades contain {off_grid} entries off the live {cadence}-minute grid")

    work = trades.copy()
    date_col = "trade_date" if "trade_date" in work.columns else "date" if "date" in work.columns else ""
    if not date_col:
        issues.append("combined trades missing trade_date/date for overlap audit")
        return
    work["_minute"] = pd.to_numeric(work["minute"], errors="coerce")
    work["_exit_minutes"] = pd.to_numeric(work["exit_minutes"], errors="coerce")
    invalid_durations = int(
        (work["_minute"].isna() | work["_exit_minutes"].isna() | (work["_exit_minutes"] < 0.0)).sum()
    )
    if invalid_durations:
        issues.append(f"combined trades contain {invalid_durations} invalid/missing entry or exit durations")
    work = work.dropna(subset=["_minute", "_exit_minutes"]).copy()
    work = work[work["_exit_minutes"] >= 0.0].copy()
    overlap_count = 0
    for (_ticker, _date), part in work.groupby(["ticker", date_col], sort=False):
        open_until = float("-inf")
        ordered = part.sort_values("_minute", kind="stable")[["_minute", "_exit_minutes"]]
        for minute_raw, exit_raw in ordered.itertuples(index=False, name=None):
            minute = float(minute_raw)
            exit_minutes = max(0.0, float(exit_raw))
            if minute < open_until:
                overlap_count += 1
                continue
            open_until = minute + exit_minutes
    if overlap_count:
        issues.append(
            f"combined trades contain {overlap_count} overlapping same-ticker entries rejected by live runtime"
        )


def same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.absolute() == right.absolute()


def assert_result_dir_matches(label: str, raw: Any, expected: Path, issues: list[str]) -> None:
    if not raw:
        issues.append(f"{label}.result_dir missing")
        return
    actual = resolve_repo_path(str(raw))
    if not same_path(actual, expected):
        issues.append(f"{label}.result_dir {actual} != expected {expected}")


def nearly_equal(left: float, right: float, tolerance: float = 1e-9) -> bool:
    scale = max(1.0, abs(left), abs(right))
    return abs(left - right) <= tolerance * scale


def assert_metric_payload_matches(
    label: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    issues: list[str],
) -> None:
    for key, expected_value in expected.items():
        if key not in actual:
            issues.append(f"{label}.{key} missing")
            continue
        actual_value = actual.get(key)
        if isinstance(expected_value, (int, float)) and not isinstance(expected_value, bool):
            try:
                actual_float = float(actual_value)
            except (TypeError, ValueError):
                issues.append(f"{label}.{key} {actual_value!r} is not numeric")
                continue
            if not nearly_equal(float(expected_value), actual_float):
                issues.append(f"{label}.{key} {actual_float:.12g} != expected {float(expected_value):.12g}")
        elif actual_value != expected_value:
            issues.append(f"{label}.{key} {actual_value!r} != expected {expected_value!r}")


def assert_metric_gate(name: str, value: float, minimum: float, issues: list[str]) -> None:
    if value < minimum:
        issues.append(f"{name} {value:.6g} < {minimum:.6g}")


def assert_strict_metric_gate(name: str, value: float, minimum: float, issues: list[str]) -> None:
    if value <= minimum:
        issues.append(f"{name} {value:.6g} <= {minimum:.6g}")


def _exit_contract_value(exit_contract: dict[str, Any], key: str, default: float | None = None) -> float | None:
    value = exit_contract.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def assert_exit_contract_consistency(policy: dict[str, Any], issues: list[str]) -> None:
    exit_contract = policy.get("validated_label_exit_contract")
    if not isinstance(exit_contract, dict):
        issues.append("validated_label_exit_contract missing or invalid")
        return
    for key in ["horizon_minutes", "option_take_profit_pct", "option_stop_loss_pct"]:
        if _exit_contract_value(exit_contract, key) is None:
            issues.append(f"validated_label_exit_contract.{key} missing or nonnumeric")
    min_hold = _exit_contract_value(exit_contract, "min_hold_minutes", 0.0)
    if min_hold is None or min_hold < 0.0:
        issues.append("validated_label_exit_contract.min_hold_minutes missing, nonnumeric, or negative")

    exit_validation = policy.get("exit_contract_validation")
    if isinstance(exit_validation, dict) and isinstance(exit_validation.get("contract"), dict):
        validation_contract = exit_validation["contract"]
        comparisons = {
            "take_profit_pct": (
                _exit_contract_value(validation_contract, "take_profit_pct"),
                _exit_contract_value(exit_contract, "option_take_profit_pct"),
            ),
            "stop_loss_pct": (
                _exit_contract_value(validation_contract, "stop_loss_pct"),
                _exit_contract_value(exit_contract, "option_stop_loss_pct"),
            ),
            "horizon_minutes": (
                _exit_contract_value(validation_contract, "horizon_minutes"),
                _exit_contract_value(exit_contract, "horizon_minutes"),
            ),
            "min_hold_minutes": (
                _exit_contract_value(validation_contract, "min_hold_minutes", 0.0),
                _exit_contract_value(exit_contract, "min_hold_minutes", 0.0),
            ),
        }
        for key, (actual, expected) in comparisons.items():
            if actual is None or expected is None:
                issues.append(f"exit_contract_validation.contract.{key} cannot be compared")
                continue
            if not nearly_equal(float(actual), float(expected)):
                issues.append(
                    f"exit_contract_validation.contract.{key} {float(actual):.12g} != validated {float(expected):.12g}"
                )

    live_contract = policy.get("live_contract") if isinstance(policy.get("live_contract"), dict) else {}
    live_exit = live_contract.get("event_option_exit_contract") if isinstance(live_contract.get("event_option_exit_contract"), dict) else {}
    if not live_exit:
        return
    comparisons = {
        "take_profit_pct": (
            _exit_contract_value(live_exit, "take_profit_pct"),
            _exit_contract_value(exit_contract, "option_take_profit_pct"),
        ),
        "stop_loss_pct_abs": (
            abs(_exit_contract_value(live_exit, "stop_loss_pct", 0.0) or 0.0),
            _exit_contract_value(exit_contract, "option_stop_loss_pct"),
        ),
        "max_hold_minutes": (
            _exit_contract_value(live_exit, "max_hold_minutes"),
            _exit_contract_value(exit_contract, "horizon_minutes"),
        ),
        "min_hold_minutes": (
            _exit_contract_value(live_exit, "min_hold_minutes", 0.0),
            _exit_contract_value(exit_contract, "min_hold_minutes", 0.0),
        ),
    }
    for key, (actual, expected) in comparisons.items():
        if actual is None or expected is None:
            issues.append(f"live_contract.event_option_exit_contract.{key} cannot be compared")
            continue
        if not nearly_equal(float(actual), float(expected)):
            issues.append(
                f"live_contract.event_option_exit_contract.{key} {float(actual):.12g} != validated {float(expected):.12g}"
            )


def exit_validation_metrics(policy: dict[str, Any]) -> dict[str, Any] | None:
    validation = policy.get("exit_contract_validation")
    if not isinstance(validation, dict):
        return None
    per_ticker = validation.get("per_ticker")
    if not isinstance(per_ticker, dict):
        return None
    return validation



def assert_raw_coverage_true_0dte(payload: dict[str, Any], tickers: list[str], issues: list[str]) -> None:
    try:
        schema_version = int(payload.get("schema_version", 0) or 0)
    except (TypeError, ValueError):
        schema_version = 0
    if schema_version < 2:
        issues.append(
            "raw ThetaData coverage audit schema_version < 2; expected true 0DTE audit with expiration==date"
        )
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    for ticker in tickers:
        row = options.get(ticker)
        if not isinstance(row, dict):
            issues.append(f"raw ThetaData coverage missing options section for {ticker}")
            continue
        if row.get("zero_dte_option_files") is None or row.get("non_zero_dte_option_files") is None:
            issues.append(f"raw ThetaData coverage for {ticker} lacks 0DTE/non-0DTE file counters")

def assert_event_option_package(args: argparse.Namespace) -> dict[str, Any]:
    policy_path = Path(args.policy)
    registry_path = Path(args.registry)
    issues: list[str] = []

    policy = read_json(policy_path)
    registry = read_json(registry_path)
    validation = policy.get("completed_month_validation")
    if not isinstance(validation, dict):
        raise ValueError(f"{policy_path} missing completed_month_validation")
    result_dir = resolve_repo_path(str(validation.get("result_dir", "")))
    if not result_dir.exists():
        issues.append(f"validation result_dir missing: {result_dir}")

    verification_file = str(validation.get("verification_file", "verification.json")).strip() or "verification.json"
    curve_health_file = str(validation.get("curve_health_file", "curve_health/curve_health.json")).strip() or "curve_health/curve_health.json"
    verification_path = result_dir / verification_file
    curve_path = result_dir / curve_health_file
    trades_path = result_dir / "combined_trades.csv"
    verification = read_json(verification_path) if verification_path.exists() else {}
    curve = read_json(curve_path) if curve_path.exists() else {}

    if not verification.get("passed", False):
        issues.append(f"formal verifier did not pass: {verification_path}")
    if not curve.get("passed", False) and not bool(args.allow_failed_curve_health):
        issues.append(f"curve-health did not pass: {curve_path}")
    validation_months = [str(month) for month in validation.get("months", [])]
    if verification:
        assert_result_dir_matches("verification", verification.get("result_dir"), result_dir, issues)
        verifier_months = verification.get("gates", {}).get("months")
        if validation_months and [str(month) for month in verifier_months or []] != validation_months:
            issues.append("verification.gates.months does not match policy completed_month_validation.months")
    if curve:
        assert_result_dir_matches("curve_health", curve.get("result_dir"), result_dir, issues)

    completed_by_ticker = validation.get("by_ticker", {})
    if not isinstance(completed_by_ticker, dict):
        completed_by_ticker = {}
    exit_validation = exit_validation_metrics(policy)
    by_ticker = exit_validation.get("per_ticker", {}) if exit_validation else completed_by_ticker
    metrics_label = "exit_contract_validation" if exit_validation else "completed_month_validation"
    if not exit_validation and float(args.min_avg_hold_minutes) > 0.0:
        issues.append("exit_contract_validation missing; cannot verify avg_hold_minutes gate")
    if not isinstance(by_ticker, dict):
        issues.append(f"{metrics_label}.by_ticker missing or invalid")
        by_ticker = {}
    required_tickers = [str(t).upper() for t in args.tickers]
    for ticker in required_tickers:
        row = by_ticker.get(ticker)
        if not isinstance(row, dict):
            issues.append(f"{ticker}: missing metrics")
            continue
        assert_metric_gate(f"{ticker}.win_rate", float(row.get("win_rate", 0.0)), float(args.min_win_rate), issues)
        assert_metric_gate(
            f"{ticker}.profit_factor",
            float(row.get("profit_factor", 0.0)),
            float(args.min_profit_factor),
            issues,
        )
        if int(row.get("min_month_trades", 0)) < int(args.min_month_trades):
            issues.append(f"{ticker}.min_month_trades {row.get('min_month_trades')} < {args.min_month_trades}")
        if exit_validation:
            assert_strict_metric_gate(
                f"{ticker}.avg_hold_minutes",
                float(row.get("avg_hold_minutes", 0.0)),
                float(args.min_avg_hold_minutes),
                issues,
            )
            if float(row.get("avg_return", 0.0)) <= 0.0:
                issues.append(f"{ticker}.avg_return {row.get('avg_return')} <= 0")
        else:
            if float(row.get("positive_month_rate", 0.0)) < 1.0 and not bool(args.allow_nonpositive_months):
                issues.append(f"{ticker}.positive_month_rate {row.get('positive_month_rate')} < 1.0")
            if float(row.get("pnl_return", 0.0)) <= 0.0:
                issues.append(f"{ticker}.pnl_return {row.get('pnl_return')} <= 0")

    trades = pd.DataFrame()
    if trades_path.exists():
        live_audit_cols = {
            "ticker",
            "date",
            "trade_date",
            "month",
            "minute",
            "exit_minutes",
            "realized_return",
            "topk_mode",
        }
        trades = pd.read_csv(trades_path, usecols=lambda c: c in live_audit_cols, low_memory=False)
        if "topk_mode" in trades.columns:
            bad = trades["topk_mode"].astype(str).eq("TOPK_REGRESSOR").sum()
            if int(bad) > 0 and not bool(args.allow_topk_regressor_rows):
                issues.append(f"{trades_path}: contains {int(bad)} TOPK_REGRESSOR rows")
    else:
        issues.append(f"combined trades missing: {trades_path}")

    assert_exit_contract_consistency(policy, issues)

    missing_live = registry.get("missing_for_full_live_equivalence", [])
    invalidated = (registry.get("invalidated_components") or {}).get("components", [])
    if args.require_live_ready:
        if "_diagnostics" in str(result_dir).replace("\\", "/"):
            issues.append(f"live-ready result_dir must not be under _diagnostics: {result_dir}")
        if not bool(args.allow_live_inconsistent_features):
            assert_live_observable_feature_contract(policy, registry, issues)
            assert_candidate_universe_causality(policy, validation, trades_path, issues)
        assert_policy_selection_causality(policy, registry, validation_months, issues)
        assert_executable_quote_contract(policy, validation, issues)
        assert_trade_artifact_live_equivalence(
            policy,
            validation,
            trades,
            validation_months,
            required_tickers,
            max(float(args.min_win_rate), 0.50),
            max(float(args.min_profit_factor), 1.30),
            max(int(args.min_month_trades), 18),
            issues,
        )
        if missing_live:
            issues.append("registry missing_for_full_live_equivalence is not empty")
        if invalidated:
            issues.append("registry invalidated_components is not empty")
        status = str(policy.get("status", "")).lower()
        registry_status = str(registry.get("status", "")).lower()
        if "live_ready" not in status or "incomplete" in status or "research" in status:
            issues.append(f"policy status is not live-ready: {policy.get('status')}")
        if "live_ready" not in registry_status or "incomplete" in registry_status:
            issues.append(f"registry status is not live-ready: {registry.get('status')}")
        policy_deploy_month = str(policy.get("deploy_month", ""))
        registry_deploy_month = str(registry.get("deploy_month", ""))
        if not policy_deploy_month:
            issues.append("policy deploy_month missing")
        if registry_deploy_month != policy_deploy_month:
            issues.append(
                f"registry deploy_month {registry.get('deploy_month')} != policy deploy_month {policy.get('deploy_month')}"
            )
        for month in validation_months:
            if policy_deploy_month and month >= policy_deploy_month:
                issues.append(f"completed_month_validation month {month} is not before deploy_month {policy_deploy_month}")

        if not bool(args.ignore_raw_thetadata_coverage):
            raw_coverage_path = Path(args.raw_thetadata_coverage)
            if not raw_coverage_path.exists():
                issues.append(f"raw ThetaData coverage audit missing: {raw_coverage_path}")
            else:
                raw_coverage = read_json(raw_coverage_path)
                assert_raw_coverage_true_0dte(raw_coverage, required_tickers, issues)
                combined = raw_coverage.get("combined") if isinstance(raw_coverage.get("combined"), dict) else {}
                raw_completed = {str(month) for month in combined.get("completed_months", [])}
                raw_missing = [month for month in validation_months if month not in raw_completed]
                if raw_missing:
                    partial = [str(month) for month in combined.get("partial_months", [])]
                    latest = combined.get("latest_common_date_all_tickers")
                    issues.append(
                        "completed_month_validation includes months not completed in raw all-ticker 0DTE coverage: "
                        f"{raw_missing}; raw_latest_common_date={latest}; raw_partial_months={partial}"
                    )
        package_dir = policy_path.parent
        metrics_sidecar_path = package_dir / "completed_month_metrics.json"
        curve_sidecar_path = package_dir / "completed_month_curve_health.json"
        if not metrics_sidecar_path.exists():
            issues.append(f"completed-month metrics sidecar missing: {metrics_sidecar_path}")
        else:
            metrics_sidecar = read_json(metrics_sidecar_path)
            if isinstance(validation.get("overall"), dict) and isinstance(metrics_sidecar.get("overall"), dict):
                assert_metric_payload_matches(
                    "completed_month_metrics.overall",
                    validation["overall"],
                    metrics_sidecar["overall"],
                    issues,
                )
            else:
                issues.append("completed_month_metrics.overall missing or invalid")
            side_by_ticker = metrics_sidecar.get("by_ticker")
            if not isinstance(side_by_ticker, dict):
                issues.append("completed_month_metrics.by_ticker missing or invalid")
            else:
                for ticker, expected_metrics in completed_by_ticker.items():
                    actual_metrics = side_by_ticker.get(ticker)
                    if not isinstance(expected_metrics, dict) or not isinstance(actual_metrics, dict):
                        issues.append(f"completed_month_metrics.by_ticker.{ticker} missing or invalid")
                        continue
                    assert_metric_payload_matches(
                        f"completed_month_metrics.by_ticker.{ticker}",
                        expected_metrics,
                        actual_metrics,
                        issues,
                    )
            try:
                risk_capital = float(policy.get("risk_capital_dollars", 0.0))
                side_risk = float(metrics_sidecar.get("risk_capital", 0.0))
                expected_net = float(validation.get("overall", {}).get("pnl_return", 0.0)) * risk_capital
                side_net = float(metrics_sidecar.get("net_pnl", 0.0))
                if not nearly_equal(side_risk, risk_capital):
                    issues.append(
                        f"completed_month_metrics.risk_capital {side_risk:.12g} != expected {risk_capital:.12g}"
                    )
                if not nearly_equal(side_net, expected_net):
                    issues.append(f"completed_month_metrics.net_pnl {side_net:.12g} != expected {expected_net:.12g}")
            except (TypeError, ValueError):
                issues.append("completed_month_metrics risk/net_pnl fields are invalid")
            if verification and metrics_sidecar.get("integrity") != verification.get("integrity"):
                issues.append("completed_month_metrics.integrity does not match verification.json")

        if not curve_sidecar_path.exists():
            issues.append(f"completed-month curve-health sidecar missing: {curve_sidecar_path}")
        else:
            curve_sidecar = read_json(curve_sidecar_path)
            if curve and curve_sidecar != curve:
                issues.append("completed_month_curve_health.json does not match result_dir curve_health.json")

        live_equivalence = policy.get("live_equivalence")
        replay = live_equivalence.get("runtime_policy_replay") if isinstance(live_equivalence, dict) else None
        if isinstance(replay, str):
            replay = {"summary_path": replay}
        if not isinstance(replay, dict):
            issues.append("policy live_equivalence.runtime_policy_replay missing")
        else:
            summary = replay
            summary_path_value = replay.get("summary_path") or replay.get("path")
            if summary_path_value:
                summary_path = resolve_repo_path(str(summary_path_value))
                if not summary_path.exists():
                    issues.append(f"runtime replay summary missing: {summary_path}")
                    summary = {}
                else:
                    summary = read_json(summary_path)
            passed = bool(summary.get("stateful_replay_passed", summary.get("passed", False)))
            if not passed:
                issues.append("runtime replay did not pass")
            comparisons = summary.get("comparisons")
            comparison = summary.get("comparison") if isinstance(summary.get("comparison"), dict) else {}
            if isinstance(comparisons, list) and comparisons:
                failed = [str(row.get("name", "?")) for row in comparisons if not row.get("passed", False)]
            elif isinstance(comparison.get("by_ticker"), dict) and comparison.get("by_ticker"):
                failed = [str(name) for name, row in comparison["by_ticker"].items() if not row.get("passed", False)]
            else:
                failed = ["missing_comparisons"]
            if failed:
                issues.append(f"runtime replay comparisons failed: {failed}")
            replay_flag = replay.get("stateful_replay_passed", replay.get("passed", passed))
            if replay_flag is not True:
                issues.append("policy runtime replay flag is not true")

    if issues:
        raise RuntimeError("Event-option production package validation failed:\n- " + "\n- ".join(issues))

    return {
        "policy": policy.get("policy"),
        "status": policy.get("status"),
        "result_dir": str(result_dir),
        "verification_passed": bool(verification.get("passed", False)),
        "curve_health_passed": bool(curve.get("passed", False)),
        "registry_status": registry.get("status"),
        "missing_live_equivalence_count": len(missing_live) if isinstance(missing_live, list) else 0,
        "invalidated_component_count": len(invalidated) if isinstance(invalidated, list) else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the event-option production package before upload/deploy.")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-avg-hold-minutes", type=float, default=0.0)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--require-live-ready", action="store_true")
    parser.add_argument("--raw-thetadata-coverage", default=str(DEFAULT_RAW_THETADATA_COVERAGE))
    parser.add_argument("--ignore-raw-thetadata-coverage", action="store_true")
    parser.add_argument(
        "--allow-topk-regressor-rows",
        action="store_true",
        help="Allow causal TOPK_REGRESSOR rows for forward-only research candidates. Do not use for live-ready validation unless runtime replay covers them.",
    )
    parser.add_argument(
        "--allow-nonpositive-months",
        action="store_true",
        help="Research-only: do not require every validation month to have positive PnL.",
    )
    parser.add_argument(
        "--allow-failed-curve-health",
        action="store_true",
        help="Research-only: validate metric/artifact consistency even when curve-health flags remain.",
    )
    parser.add_argument(
        "--allow-live-inconsistent-features",
        action="store_true",
        help="Research-only: do not fail live-ready validation on noncausal or live-inconsistent feature columns.",
    )
    args = parser.parse_args()

    summary = assert_event_option_package(args)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
