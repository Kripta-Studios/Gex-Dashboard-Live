from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc
import hashlib
import json
import math
import pickle
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __package__:
    from .event_option_component_live import (
        DEFAULT_ENTRY_START_MINUTE_ET,
        live_observable_feature_issues_for_columns,
    )
    from .evaluate_xinput_level_filter import month_add, month_range
    from .walkforward_event_option_gate import (
        DeployConfig,
        LEAKY_PATTERNS,
        build_fold_grid,
        deploy,
        metrics,
        parse_hhmm_to_minute,
        score_metrics,
    )
else:
    from event_option_component_live import (
        DEFAULT_ENTRY_START_MINUTE_ET,
        live_observable_feature_issues_for_columns,
    )
    from evaluate_xinput_level_filter import month_add, month_range
    from walkforward_event_option_gate import (
        DeployConfig,
        LEAKY_PATTERNS,
        build_fold_grid,
        deploy,
        metrics,
        parse_hhmm_to_minute,
        score_metrics,
    )


INDEX_TICKERS = ("SPXW", "SPY", "QQQ")


def parse_ticker_int_map(values: Iterable[str], *, field_name: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        if "=" not in text:
            raise ValueError(f"{field_name} values must use TICKER=INTEGER, got {text!r}")
        ticker, value = text.split("=", 1)
        ticker = ticker.strip().upper()
        if not ticker:
            raise ValueError(f"{field_name} contains an empty ticker: {text!r}")
        try:
            parsed = int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{field_name} contains a non-integer value: {text!r}") from exc
        if parsed < 0:
            raise ValueError(f"{field_name} values must be non-negative: {text!r}")
        out[ticker] = parsed
    return out


def parse_ticker_int_grid_map(values: Iterable[str], *, field_name: str) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        if "=" not in text:
            raise ValueError(f"{field_name} values must use TICKER=INT[,INT...], got {text!r}")
        ticker, value = text.split("=", 1)
        ticker = ticker.strip().upper()
        try:
            grid = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
        except ValueError as exc:
            raise ValueError(f"{field_name} contains a non-integer grid: {text!r}") from exc
        if not ticker or not grid or any(item <= 0 for item in grid):
            raise ValueError(f"{field_name} requires a ticker and positive grid values: {text!r}")
        out[ticker] = grid
    return out


def ticker_cooldown_minutes(args: argparse.Namespace, ticker: str) -> int:
    overrides = getattr(args, "ticker_cooldown_map", {}) or {}
    return int(overrides.get(str(ticker).upper(), int(args.cooldown_minutes)))


def ticker_max_day_grid(args: argparse.Namespace, ticker: str) -> list[int]:
    overrides = getattr(args, "ticker_max_day_grid_map", {}) or {}
    return [int(value) for value in overrides.get(str(ticker).upper(), args.max_day_grid)]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _split_months(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        raw = value
    else:
        raw = str(value or "").split(",")
    return sorted({str(item).strip() for item in raw if len(str(item).strip()) == 6 and str(item).strip().isdigit()})


def freeze_fold_policy_artifact(
    artifact_dir: Path,
    *,
    ticker: str,
    test_month: str,
    profile: "ProfileConfig",
    train_months: list[str],
    selection_months: list[str],
    deploy_config: DeployConfig,
    call_model: object,
    put_model: object,
    medians: pd.Series,
    feature_cols: list[str],
    args: argparse.Namespace,
) -> dict[str, str]:
    """Freeze the selected policy before any outer-fold outcome is scored."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "event_option_gate_direction_model.pkl"
    manifest_path = artifact_dir / "fold_policy.json"
    metadata = {
        "schema_version": 1,
        "component": "nested_event_option_gate_direction_model",
        "ticker": str(ticker).upper(),
        "evaluation_month": str(test_month),
        "profile": asdict(profile),
        "training_months": [str(month) for month in train_months],
        "selection_months": [str(month) for month in selection_months],
        "deploy_config": asdict(deploy_config),
        "deploy_config_name": deploy_config.name,
        "cooldown_minutes": ticker_cooldown_minutes(args, ticker),
        "feature_cols": [str(col) for col in feature_cols],
        "feature_medians": {
            str(key): float(value) if np.isfinite(float(value)) else 0.0
            for key, value in medians.fillna(0.0).items()
        },
        "policy_frozen_before_evaluation": True,
    }
    with model_path.open("wb") as handle:
        pickle.dump(
            {
                "call_model": call_model,
                "put_model": put_model,
                "medians": medians,
                "feature_cols": feature_cols,
                "metadata": metadata,
            },
            handle,
            protocol=pickle.HIGHEST_PROTOCOL,
        )
    manifest = {
        **metadata,
        "model_path": model_path.name,
        "model_sha256": sha256_file(model_path),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    return {
        "policy_artifact_path": manifest_path.as_posix(),
        "policy_artifact_sha256": sha256_file(manifest_path),
        "model_artifact_path": model_path.as_posix(),
        "model_artifact_sha256": str(manifest["model_sha256"]),
    }


def write_policy_selection_provenance(
    output_dir: Path,
    folds: pd.DataFrame,
    *,
    expected_months: list[str],
    expected_tickers: list[str],
) -> dict:
    fold_dir = output_dir / "fold_policy_artifacts"
    fold_dir.mkdir(parents=True, exist_ok=True)
    expected_ticker_set = {str(ticker).upper() for ticker in expected_tickers}
    provenance_folds: list[dict] = []

    for month in [str(value) for value in expected_months]:
        part = folds[folds.get("month", pd.Series(dtype=str)).astype(str).eq(month)].copy()
        policies: list[dict] = []
        training_months: set[str] = set()
        selection_months: set[str] = set()
        observed_tickers: set[str] = set()
        component_artifacts_ok = True
        for row in part.to_dict("records"):
            ticker = str(row.get("ticker", "")).upper()
            if not ticker:
                continue
            observed_tickers.add(ticker)
            row_training = _split_months(row.get("training_months", row.get("train_months", "")))
            row_selection = _split_months(row.get("selection_months", row.get("val_months", "")))
            training_months.update(row_training)
            selection_months.update(row_selection)
            selected = str(row.get("selected", "")).strip().lower() in {"true", "1"}
            artifact_hash = str(row.get("policy_artifact_sha256", "") or "").strip()
            if selected and not artifact_hash:
                component_artifacts_ok = False
            policies.append(
                {
                    "ticker": ticker,
                    "selected": selected,
                    "profile": str(row.get("profile", "")),
                    "deploy_config": str(row.get("deploy_config", "")),
                    "training_months": row_training,
                    "selection_months": row_selection,
                    "component_policy_artifact_path": str(row.get("policy_artifact_path", "") or ""),
                    "component_policy_artifact_sha256": artifact_hash,
                }
            )

        sources = sorted(training_months | selection_months)
        complete = observed_tickers == expected_ticker_set
        strictly_prior = bool(sources) and all(source < month for source in sources)
        frozen = bool(complete and strictly_prior and component_artifacts_ok)
        fold_payload = {
            "schema_version": 1,
            "evaluation_month": month,
            "training_months": sorted(training_months),
            "selection_months": sorted(selection_months),
            "policy_frozen_before_evaluation": frozen,
            "ticker_policies": sorted(policies, key=lambda row: row["ticker"]),
        }
        fold_path = fold_dir / f"fold_policy_{month}.json"
        fold_path.write_text(
            json.dumps(fold_payload, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        provenance_folds.append(
            {
                "evaluation_month": month,
                "training_months": sorted(training_months),
                "selection_months": sorted(selection_months),
                "policy_frozen_before_evaluation": frozen,
                "policy_artifact_path": fold_path.as_posix(),
                "policy_artifact_sha256": sha256_file(fold_path),
            }
        )

    passed = bool(provenance_folds) and all(
        bool(fold["policy_frozen_before_evaluation"]) for fold in provenance_folds
    )
    provenance = {
        "schema_version": 1,
        "passed": passed,
        "mode": "nested_walk_forward",
        "evaluation_months": [str(month) for month in expected_months],
        "selection_protocol_frozen_before_evaluation": True,
        "trade_artifact_kind": "nested_walk_forward_fold_outputs",
        "folds": provenance_folds,
    }
    (output_dir / "policy_selection_provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    return provenance


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    delta_bucket: int
    label_mode: str
    expiry_modes: tuple[str, ...]
    train_scope: str


@dataclass
class PreparedProfile:
    config: ProfileConfig
    frame: pd.DataFrame
    feature_cols: list[str]


def _profile_name(delta_bucket: int, label_mode: str, expiry_modes: Iterable[str], train_scope: str) -> str:
    expiry = "mixed" if not tuple(expiry_modes) else "_".join(expiry_modes)
    return f"{train_scope}_{expiry}_d{int(delta_bucket):02d}_{label_mode}"


def default_profiles(kind: str, all_tickers: list[str]) -> list[ProfileConfig]:
    kind = str(kind).lower()
    profiles: list[ProfileConfig] = []

    def add(delta_bucket: int, label_mode: str, expiry_modes: tuple[str, ...], train_scope: str) -> None:
        profiles.append(
            ProfileConfig(
                name=_profile_name(delta_bucket, label_mode, expiry_modes, train_scope),
                delta_bucket=int(delta_bucket),
                label_mode=str(label_mode),
                expiry_modes=tuple(expiry_modes),
                train_scope=str(train_scope),
            )
        )

    if kind == "narrow":
        scopes = ("target", "index", "all")
        for scope in scopes:
            add(35, "return", ("front_weekly",), scope)
            add(35, "win", tuple(), scope)
            add(35, "win", ("zero_dte",), scope)
        for scope in ("index", "all"):
            add(50, "win", ("zero_dte",), scope)
            add(80, "win", ("zero_dte",), scope)
    elif kind == "compact":
        scopes = ("target", "index", "all")
        for scope in scopes:
            for expiry in (tuple(), ("zero_dte",), ("front_weekly",)):
                add(35, "return", expiry, scope)
                add(35, "win", expiry, scope)
            for expiry in (tuple(), ("zero_dte",)):
                add(50, "win", expiry, scope)
                add(80, "win", expiry, scope)
    elif kind == "production_zero_dte":
        # Compact, pre-declared production search space.  It varies only
        # contract delta, target type, and target-vs-pooled training while
        # keeping the executable 0DTE universe fixed.  This avoids duplicate
        # mixed/zero-DTE profiles and seed-searching aliases of the same model.
        for scope in ("target", "index"):
            for delta in (15, 25, 35, 50, 65, 80):
                for label_mode in ("return", "win"):
                    add(delta, label_mode, ("zero_dte",), scope)
    elif kind == "broad":
        scopes = ("target", "index", "all")
        for scope in scopes:
            for delta in (15, 25, 35, 50, 65, 80):
                for label_mode in ("return", "win"):
                    for expiry in (tuple(), ("zero_dte",), ("front_weekly",)):
                        add(delta, label_mode, expiry, scope)
    else:
        raise ValueError(f"unknown profile kind: {kind}")

    # Keep deterministic order and drop accidental duplicates.
    seen: set[str] = set()
    unique: list[ProfileConfig] = []
    for profile in profiles:
        if profile.name in seen:
            continue
        seen.add(profile.name)
        unique.append(profile)
    if not all_tickers:
        return unique
    return unique


def filter_profiles(
    profiles: Iterable[ProfileConfig],
    allowlist: Iterable[str] = (),
) -> list[ProfileConfig]:
    ordered = list(profiles)
    requested = [str(value).strip() for value in allowlist if str(value).strip()]
    if not requested:
        return ordered
    by_name = {profile.name: profile for profile in ordered}
    unknown = sorted(set(requested).difference(by_name))
    if unknown:
        raise ValueError(f"unknown --profile-allowlist entries: {unknown}")
    requested_set = set(requested)
    return [profile for profile in ordered if profile.name in requested_set]


def load_raw(path: str | Path, tickers: list[str]) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    if tickers:
        df = df[df["ticker"].isin([t.upper() for t in tickers])].copy()
    df["month"] = df["trade_date"].astype(str).str[:6]
    df["date"] = df["trade_date"].astype(str)
    return df.reset_index(drop=True)


def build_features(
    df: pd.DataFrame,
    *,
    live_observable_features_only: bool = True,
    entry_start_minute_et: int = DEFAULT_ENTRY_START_MINUTE_ET,
    feature_exclude_prefixes: Iterable[str] = (),
) -> tuple[pd.DataFrame, list[str]]:
    work = df.copy()
    cats = [c for c in ["ticker", "expiry_mode", "nearest_level_name"] if c in work.columns]
    if cats:
        work = pd.concat([work, pd.get_dummies(work[cats].astype(str), prefix=cats, dtype=float)], axis=1)
    exclude_prefixes = tuple(str(value).lower() for value in feature_exclude_prefixes if str(value).strip())
    selected: list[str] = []
    excluded = {
        "trade_date",
        "date",
        "expiration",
        "timestamp",
        "time",
        "underlying_ticker",
        "nearest_level_name",
        "expiry_mode",
        "call_return",
        "put_return",
    }
    for col in work.columns:
        low = str(col).lower()
        if col in excluded:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if exclude_prefixes and low.startswith(exclude_prefixes):
            continue
        if pd.api.types.is_numeric_dtype(work[col]):
            selected.append(col)
    if bool(live_observable_features_only):
        selected = [
            col
            for col in selected
            if not live_observable_feature_issues_for_columns(
                "profile_selector",
                [col],
                entry_start_minute_et=int(entry_start_minute_et),
            )
        ]
    return work, selected


def prepare_profile(
    raw: pd.DataFrame,
    profile: ProfileConfig,
    clip_return: float,
    *,
    live_observable_features_only: bool = True,
    entry_start_minute_et: int = DEFAULT_ENTRY_START_MINUTE_ET,
    feature_exclude_prefixes: Iterable[str] = (),
) -> PreparedProfile:
    df = raw
    if profile.expiry_modes:
        df = df[df["expiry_mode"].astype(str).isin(profile.expiry_modes)].copy()
    else:
        df = df.copy()
    call_col = f"call_d{int(profile.delta_bucket):02d}_opt_exit_ret"
    put_col = f"put_d{int(profile.delta_bucket):02d}_opt_exit_ret"
    if call_col not in df.columns or put_col not in df.columns:
        raise KeyError(f"missing label columns for {profile.name}: {call_col}, {put_col}")
    df["call_return"] = pd.to_numeric(df[call_col], errors="coerce")
    df["put_return"] = pd.to_numeric(df[put_col], errors="coerce")
    finite_labels = np.isfinite(df["call_return"]) & np.isfinite(df["put_return"])
    price_mode = df.get("option_price_mode", pd.Series("legacy_ohlc", index=df.index)).astype(str).str.lower()
    executable = price_mode.eq("executable_quote")
    if executable.any():
        call_available = f"call_d{int(profile.delta_bucket):02d}_available"
        put_available = f"put_d{int(profile.delta_bucket):02d}_available"
        if call_available not in df.columns or put_available not in df.columns:
            raise ValueError("executable_quote dataset is missing observable current-contract availability fields")
        observable = (
            pd.to_numeric(df[call_available], errors="coerce").fillna(0.0).gt(0.0)
            & pd.to_numeric(df[put_available], errors="coerce").fillna(0.0).gt(0.0)
        )
        df = df[(~executable) | observable].copy()
        finite_labels = np.isfinite(df["call_return"]) & np.isfinite(df["put_return"])
        if (price_mode.reindex(df.index).eq("executable_quote") & ~finite_labels).any():
            raise ValueError(
                "executable_quote rows with observable entry contracts must have finite conservative outcomes"
            )
    df = df[finite_labels].copy()
    frame, feature_cols = build_features(
        df.reset_index(drop=True),
        live_observable_features_only=bool(live_observable_features_only),
        entry_start_minute_et=int(entry_start_minute_et),
        feature_exclude_prefixes=feature_exclude_prefixes,
    )
    return PreparedProfile(config=profile, frame=frame, feature_cols=feature_cols)


def train_tickers_for(profile: ProfileConfig, target_ticker: str, all_tickers: list[str]) -> list[str]:
    target_ticker = str(target_ticker).upper()
    if profile.train_scope == "target":
        return [target_ticker]
    if profile.train_scope == "index":
        return [t for t in INDEX_TICKERS if t in set(all_tickers)]
    if profile.train_scope == "all":
        return list(all_tickers)
    raise ValueError(f"unknown train_scope: {profile.train_scope}")


def threshold_args_for(profile: ProfileConfig, args: argparse.Namespace, ticker: str) -> argparse.Namespace:
    cfg = argparse.Namespace(**vars(args))
    if profile.label_mode == "win":
        cfg.threshold_grid = [float(v) for v in args.win_threshold_grid]
        cfg.threshold_quantiles = [float(v) for v in args.win_threshold_quantiles]
    else:
        cfg.threshold_grid = [float(v) for v in args.return_threshold_grid]
        cfg.threshold_quantiles = [float(v) for v in args.return_threshold_quantiles]
    cfg.max_day_grid = ticker_max_day_grid(args, ticker)
    return cfg


def fit_profile_fold(
    prepared: PreparedProfile,
    ticker: str,
    test_month: str,
    all_tickers: list[str],
    args: argparse.Namespace,
    score_test: bool,
    artifact_dir: Path | None = None,
) -> dict:
    profile = prepared.config
    frame = prepared.frame
    feature_cols = prepared.feature_cols
    val_months = [month_add(str(test_month), -i) for i in range(int(args.val_months), 0, -1)]
    first_val = val_months[0]
    train_tickers = train_tickers_for(profile, ticker, all_tickers)

    train = frame[(frame["month"].astype(str) < first_val) & (frame["ticker"].astype(str).isin(train_tickers))].copy()
    val = frame[
        (frame["ticker"].astype(str) == str(ticker))
        & (frame["month"].astype(str).isin(val_months))
    ].copy()
    test = frame[
        (frame["ticker"].astype(str) == str(ticker))
        & (frame["month"].astype(str) == str(test_month))
    ].copy()
    train_months = sorted(str(month) for month in train["month"].astype(str).unique())
    cooldown_minutes = ticker_cooldown_minutes(args, ticker)

    base = {
        "ticker": str(ticker),
        "month": str(test_month),
        "profile": profile.name,
        "delta_bucket": int(profile.delta_bucket),
        "label_mode": profile.label_mode,
        "expiry_modes": ",".join(profile.expiry_modes) if profile.expiry_modes else "mixed",
        "train_scope": profile.train_scope,
        "train_tickers": ",".join(train_tickers),
        "training_months": ",".join(train_months),
        "val_months": ",".join(val_months),
        "selection_months": ",".join(val_months),
        "cooldown_minutes": int(cooldown_minutes),
        "train_rows": int(len(train)),
        "val_rows": int(len(val)),
        "test_rows": int(len(test)),
        "feature_count": int(len(feature_cols)),
    }
    if len(train) < int(args.min_train_rows) or len(val) < int(args.min_val_rows) or test.empty:
        return {
            **base,
            "status": "insufficient_rows",
            "val_score": -1e18,
            "deploy_config": "",
            "val_metrics": metrics(pd.DataFrame(), val_months),
            "test_trades": pd.DataFrame(),
            "test_metrics": metrics(pd.DataFrame(), [str(test_month)]),
        }

    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    if profile.label_mode == "win":
        y_call = (train["call_return"].astype(float) > 0.0).astype(int)
        y_put = (train["put_return"].astype(float) > 0.0).astype(int)
    else:
        clip = float(args.clip_return)
        y_call = train["call_return"].astype(float).clip(-clip, clip) if clip > 0.0 else train["call_return"].astype(float)
        y_put = train["put_return"].astype(float).clip(-clip, clip) if clip > 0.0 else train["put_return"].astype(float)

    params = dict(
        n_estimators=int(args.n_estimators),
        learning_rate=float(args.learning_rate),
        num_leaves=int(args.num_leaves),
        min_child_samples=int(args.min_child_samples),
        subsample=float(args.subsample),
        colsample_bytree=float(args.colsample_bytree),
        reg_lambda=float(args.reg_lambda),
        random_state=int(args.seed) + int(str(test_month)[-2:]) + (zlib.crc32(profile.name.encode("utf-8")) % 10000),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    lgb_device_type = str(getattr(args, "lgb_device_type", "") or "").strip()
    if lgb_device_type:
        params["device_type"] = lgb_device_type
    if lgb_device_type == "gpu":
        params["gpu_use_dp"] = bool(getattr(args, "lgb_gpu_use_dp", True))
    if profile.label_mode == "win":
        call_model = lgb.LGBMClassifier(**{**params, "objective": "binary"})
        put_model = lgb.LGBMClassifier(**{**params, "objective": "binary", "random_state": int(params["random_state"]) + 10_000})
    else:
        call_model = lgb.LGBMRegressor(**{**params, "objective": str(args.objective)})
        put_model = lgb.LGBMRegressor(**{**params, "objective": str(args.objective), "random_state": int(params["random_state"]) + 10_000})
    call_model.fit(x_train, y_call)
    put_model.fit(x_train, y_put)

    def score_part(part: pd.DataFrame) -> pd.DataFrame:
        if part.empty:
            return part.copy()
        x = part[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
        out = part.copy()
        if profile.label_mode == "win":
            out["pred_call_return"] = call_model.predict_proba(x)[:, 1]
            out["pred_put_return"] = put_model.predict_proba(x)[:, 1]
        else:
            out["pred_call_return"] = call_model.predict(x)
            out["pred_put_return"] = put_model.predict(x)
        call_action = out["pred_call_return"].astype(float) >= out["pred_put_return"].astype(float)
        out["action"] = np.where(call_action, "CALL", "PUT")
        out["score"] = np.where(call_action, out["pred_call_return"], out["pred_put_return"])
        out["realized_return"] = np.where(call_action, out["call_return"], out["put_return"])
        bucket = int(profile.delta_bucket)
        call_exit = f"call_d{bucket:02d}_opt_exit_minutes"
        put_exit = f"put_d{bucket:02d}_opt_exit_minutes"
        if call_exit in out.columns and put_exit in out.columns:
            out["exit_minutes"] = np.where(call_action, out[call_exit], out[put_exit])
        return out

    val_scored = score_part(val)
    grid_args = threshold_args_for(profile, args, ticker)
    fold_grid = build_fold_grid(val_scored, grid_args)
    best_cfg = fold_grid[0]
    best_score = -1e18
    best_metrics: dict = {}
    for cfg in fold_grid:
        val_trades = deploy(val_scored, cfg, int(cooldown_minutes))
        row = metrics(val_trades, val_months)
        score = score_metrics(
            row,
            int(args.min_val_trades),
            int(args.min_month_trades),
            float(args.min_val_pf),
            float(args.min_val_win_rate),
            float(args.min_call_rate),
            float(args.max_call_rate),
        )
        positive_month_rate = float(row.get("positive_month_rate", float("nan")))
        if (
            not np.isfinite(positive_month_rate)
            or positive_month_rate < float(args.min_val_positive_month_rate)
        ):
            score = -1e18 + int(row.get("trades", 0))
        if np.isfinite(float(row.get("daily_win_rate", float("nan")))):
            score += float(args.daily_win_weight) * float(row["daily_win_rate"])
        if np.isfinite(float(row.get("top5_share_of_pnl", float("nan")))):
            score -= float(args.top5_share_penalty) * max(float(row["top5_share_of_pnl"]) - 1.0, 0.0)
        if score > best_score:
            best_cfg = cfg
            best_score = float(score)
            best_metrics = row

    valid_val_selection = bool(best_score > -1e17)
    if not valid_val_selection and not bool(args.allow_invalid_val_deploy):
        return {
            **base,
            "status": "invalid_validation",
            "val_score": float(best_score),
            "deploy_config": getattr(best_cfg, "name", ""),
            "val_metrics": best_metrics or metrics(pd.DataFrame(), val_months),
            "test_trades": pd.DataFrame(),
            "test_metrics": metrics(pd.DataFrame(), [str(test_month)]),
        }

    artifact_fields: dict[str, str] = {}
    if artifact_dir is not None:
        artifact_fields = freeze_fold_policy_artifact(
            artifact_dir,
            ticker=ticker,
            test_month=str(test_month),
            profile=profile,
            train_months=train_months,
            selection_months=val_months,
            deploy_config=best_cfg,
            call_model=call_model,
            put_model=put_model,
            medians=medians,
            feature_cols=feature_cols,
            args=args,
        )

    test_trades = pd.DataFrame()
    test_metrics = metrics(pd.DataFrame(), [str(test_month)])
    if score_test:
        test_scored = score_part(test)
        test_trades = deploy(test_scored, best_cfg, int(cooldown_minutes))
        if not test_trades.empty:
            test_trades = test_trades.copy()
            test_trades["test_month"] = str(test_month)
            test_trades["profile"] = profile.name
            test_trades["profile_deploy_config"] = best_cfg.name
            test_trades["delta_bucket"] = int(profile.delta_bucket)
            test_trades["label_mode"] = profile.label_mode
            test_trades["profile_expiry_modes"] = ",".join(profile.expiry_modes) if profile.expiry_modes else "mixed"
            test_trades["train_scope"] = profile.train_scope
        test_metrics = metrics(test_trades, [str(test_month)])

    gc.collect()

    return {
        **base,
        "status": "ok",
        "val_score": float(best_score),
        "deploy_config": best_cfg.name,
        "val_metrics": best_metrics,
        "test_trades": test_trades,
        "test_metrics": test_metrics,
        **artifact_fields,
    }


def flatten_result(row: dict, include_test: bool = False) -> dict:
    out = {k: v for k, v in row.items() if k not in {"val_metrics", "test_metrics", "test_trades"}}
    out.update({f"val_{k}": v for k, v in dict(row.get("val_metrics") or {}).items()})
    if include_test:
        out.update({f"test_{k}": v for k, v in dict(row.get("test_metrics") or {}).items()})
    return out


def write_daily_plot(output_dir: Path, trades: pd.DataFrame, risk_capital: float) -> None:
    if trades.empty:
        return
    work = trades.copy()
    work["dt"] = pd.to_datetime(work["date"].astype(str), format="%Y%m%d", errors="coerce")
    work["pnl"] = work["realized_return"].astype(float) * float(risk_capital)
    daily = work.groupby("dt")["pnl"].sum().sort_index()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
    daily = daily.reindex(idx).fillna(0.0)
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2.4, 1.0]})
    axes[0].plot(daily.index, daily.cumsum(), color="#111827", linewidth=2.4, label="TOTAL")
    for ticker, part in work.groupby("ticker"):
        curve = part.groupby("dt")["pnl"].sum().sort_index().reindex(idx).fillna(0.0).cumsum()
        axes[0].plot(curve.index, curve.values, linewidth=1.6, label=str(ticker))
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[0].set_title(f"Nested Event-Profile Selector Net PnL, risk_capital={risk_capital:g}")
    axes[0].set_ylabel("Cumulative PnL")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)
    colors = np.where(daily >= 0.0, "#16a34a", "#dc2626")
    axes[1].bar(daily.index, daily.values, color=colors, width=0.8)
    axes[1].axhline(0.0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("Daily PnL")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "nested_profile_daily_net_pnl.png", dpi=160)
    plt.close(fig)


def write_summary(output_dir: Path, trades: pd.DataFrame, folds: pd.DataFrame, candidates: pd.DataFrame, metadata: dict) -> None:
    args_meta = metadata.get("args", {})
    expected = month_range(str(args_meta.get("start_month")), str(args_meta.get("end_month")))
    overall = metrics(trades, expected)
    per_ticker = {
        str(ticker): metrics(part, expected)
        for ticker, part in trades.groupby("ticker", sort=True)
    } if not trades.empty else {}
    payload = {
        "overall": overall,
        "per_ticker": per_ticker,
        "metadata": metadata,
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Nested Event Option Profile Selector",
        "",
        "For each ticker-month, every candidate profile is trained only on months before the validation window. Profile and threshold are selected only from validation months, then applied to the test month.",
        "",
        "## Overall",
        "",
        "```json",
        json.dumps(overall, indent=2, allow_nan=True),
        "```",
        "",
        "## Per Ticker",
        "",
        "```json",
        json.dumps(per_ticker, indent=2, allow_nan=True),
        "```",
        "",
        "## Selected Folds",
        "",
        "```csv",
        folds.to_csv(index=False),
        "```",
        "",
        "## Candidate Validation Rows",
        "",
        f"{len(candidates)} validation-only candidate rows written to `candidate_validation.csv`.",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(metadata, indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def load_checkpoint(output_dir: Path) -> tuple[list[pd.DataFrame], list[dict], list[dict], set[tuple[str, str]]]:
    trades_path = output_dir / "event_option_profile_trades.csv"
    folds_path = output_dir / "selected_folds.csv"
    candidates_path = output_dir / "candidate_validation.csv"

    all_trades: list[pd.DataFrame] = []
    selected_rows: list[dict] = []
    candidate_rows: list[dict] = []
    completed: set[tuple[str, str]] = set()

    if trades_path.exists():
        trades = pd.read_csv(
            trades_path,
            dtype={"ticker": str, "date": str, "trade_date": str, "month": str, "test_month": str},
        )
        if not trades.empty:
            all_trades.append(trades)
    if folds_path.exists():
        folds = pd.read_csv(folds_path, dtype={"ticker": str, "month": str})
        selected_rows = folds.to_dict("records")
        for row in selected_rows:
            ticker = str(row.get("ticker", "")).upper()
            month = str(row.get("month", ""))
            if ticker and month:
                completed.add((ticker, month))
    if candidates_path.exists():
        candidates = pd.read_csv(candidates_path, dtype={"ticker": str, "month": str})
        candidate_rows = candidates.to_dict("records")
    return all_trades, selected_rows, candidate_rows, completed


def main() -> int:
    parser = argparse.ArgumentParser(description="Nested walk-forward selector over event option gate profiles.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--train-universe", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument(
        "--profile-kind",
        choices=["narrow", "compact", "production_zero_dte", "broad"],
        default="narrow",
    )
    parser.add_argument(
        "--profile-allowlist",
        nargs="*",
        default=[],
        help="Optional exact profile names to retain from --profile-kind, preserving canonical order.",
    )
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--clip-return", type=float, default=2.0)
    parser.add_argument("--min-train-rows", type=int, default=500)
    parser.add_argument("--min-val-rows", type=int, default=30)
    parser.add_argument("--min-val-trades", type=int, default=45)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-val-pf", type=float, default=0.0)
    parser.add_argument("--min-val-win-rate", type=float, default=0.0)
    parser.add_argument("--min-val-positive-month-rate", type=float, default=0.0)
    parser.add_argument("--min-call-rate", type=float, default=0.15)
    parser.add_argument("--max-call-rate", type=float, default=0.85)
    parser.add_argument("--daily-win-weight", type=float, default=0.25)
    parser.add_argument("--top5-share-penalty", type=float, default=0.10)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument(
        "--ticker-cooldown-minutes",
        nargs="*",
        default=[],
        metavar="TICKER=MINUTES",
        help="Per-ticker live-contract overrides, e.g. SPXW=0 QQQ=30 SPY=0.",
    )
    parser.add_argument("--objective", default="regression_l1")
    parser.add_argument("--n-estimators", type=int, default=240)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=31)
    parser.add_argument("--min-child-samples", type=int, default=80)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.85)
    parser.add_argument("--reg-lambda", type=float, default=5.0)
    parser.add_argument("--lgb-jobs", type=int, default=8)
    parser.add_argument(
        "--lgb-device-type",
        default="",
        choices=["", "cpu", "gpu"],
        help="Optional LightGBM training backend. The selected value is frozen in fold metadata.",
    )
    parser.add_argument(
        "--lgb-gpu-use-dp",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use double precision for the OpenCL GPU learner when --lgb-device-type=gpu.",
    )
    parser.add_argument("--profile-workers", type=int, default=1)
    parser.add_argument(
        "--live-observable-features-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exclude features whose offline value is unavailable or inconsistent at the live decision minute.",
    )
    parser.add_argument(
        "--entry-time-min-et",
        default="10:30",
        help="Earliest decision time used by the live-observable feature contract.",
    )
    parser.add_argument(
        "--feature-exclude-prefixes",
        nargs="*",
        default=[],
        help="Drop numeric feature columns beginning with any of these prefixes.",
    )
    parser.add_argument("--return-threshold-grid", nargs="+", type=float, default=[-0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20])
    parser.add_argument("--return-threshold-quantiles", nargs="+", type=float, default=[0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    parser.add_argument("--win-threshold-grid", nargs="+", type=float, default=[0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75])
    parser.add_argument("--win-threshold-quantiles", nargs="+", type=float, default=[0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 12, 8, 6, 4, 2])
    parser.add_argument(
        "--ticker-max-day-grids",
        nargs="*",
        default=[],
        metavar="TICKER=N[,N...]",
        help="Per-ticker predeclared daily-cap search spaces, e.g. SPXW=1,2,4 QQQ=1,2 SPY=1,2.",
    )
    parser.add_argument("--allow-invalid-val-deploy", action="store_true")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    args.ticker_cooldown_map = parse_ticker_int_map(
        args.ticker_cooldown_minutes,
        field_name="--ticker-cooldown-minutes",
    )
    args.ticker_max_day_grid_map = parse_ticker_int_grid_map(
        args.ticker_max_day_grids,
        field_name="--ticker-max-day-grids",
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    test_tickers = [str(t).upper() for t in args.tickers]
    train_universe = [str(t).upper() for t in args.train_universe]
    all_tickers = sorted(set(test_tickers) | set(train_universe))
    raw = load_raw(args.data, all_tickers)
    entry_start_minute = parse_hhmm_to_minute(
        str(args.entry_time_min_et),
        DEFAULT_ENTRY_START_MINUTE_ET,
    )
    if bool(args.live_observable_features_only) and "minute" in raw.columns:
        raw = raw[pd.to_numeric(raw["minute"], errors="coerce") >= int(entry_start_minute)].copy()
    profiles = filter_profiles(
        default_profiles(args.profile_kind, all_tickers),
        args.profile_allowlist,
    )
    prepared_profiles = [
        prepare_profile(
            raw,
            profile,
            float(args.clip_return),
            live_observable_features_only=bool(args.live_observable_features_only),
            entry_start_minute_et=int(entry_start_minute),
            feature_exclude_prefixes=args.feature_exclude_prefixes,
        )
        for profile in profiles
    ]
    months = [m for m in sorted(raw["month"].astype(str).unique()) if str(args.start_month) <= m <= str(args.end_month)]

    metadata = {
        "args": vars(args),
        "all_tickers": all_tickers,
        "profile_count": len(profiles),
        "profiles": [asdict(p) for p in profiles],
        "data_rows": int(len(raw)),
        "entry_start_minute_et": int(entry_start_minute),
        "features_by_profile": {
            prepared.config.name: prepared.feature_cols for prepared in prepared_profiles
        },
    }
    if bool(args.no_resume):
        all_trades: list[pd.DataFrame] = []
        selected_rows: list[dict] = []
        candidate_rows: list[dict] = []
        completed: set[tuple[str, str]] = set()
    else:
        all_trades, selected_rows, candidate_rows, completed = load_checkpoint(output_dir)
        if completed:
            print(f"[resume] loaded completed folds={len(completed)} from {output_dir}", flush=True)

    for ticker in test_tickers:
        for test_month in months:
            fold_key = (str(ticker).upper(), str(test_month))
            if fold_key in completed:
                print(f"[resume] skip {ticker} {test_month}", flush=True)
                continue
            fold_candidates: list[dict] = []
            if int(args.profile_workers) > 1:
                with ThreadPoolExecutor(max_workers=int(args.profile_workers)) as pool:
                    futures = {
                        pool.submit(fit_profile_fold, prepared, ticker, str(test_month), all_tickers, args, False): prepared.config.name
                        for prepared in prepared_profiles
                    }
                    for future in as_completed(futures):
                        result = future.result()
                        candidate_rows.append(flatten_result(result, include_test=False))
                        fold_candidates.append(result)
            else:
                for prepared in prepared_profiles:
                    result = fit_profile_fold(prepared, ticker, str(test_month), all_tickers, args, score_test=False)
                    candidate_rows.append(flatten_result(result, include_test=False))
                    fold_candidates.append(result)
            valid = [row for row in fold_candidates if row.get("status") == "ok" and float(row.get("val_score", -1e18)) > -1e17]
            if valid:
                selected = max(valid, key=lambda row: float(row.get("val_score", -1e18)))
                selected_profile = next(p for p in prepared_profiles if p.config.name == selected["profile"])
                selected = fit_profile_fold(
                    selected_profile,
                    ticker,
                    str(test_month),
                    all_tickers,
                    args,
                    score_test=True,
                    artifact_dir=output_dir / "fold_model_artifacts" / str(test_month) / str(ticker).upper(),
                )
                selected_row = flatten_result(selected, include_test=True)
                selected_row["selected"] = True
                if not selected["test_trades"].empty:
                    all_trades.append(selected["test_trades"])
                print(
                    f"[PROFILE_SELECTOR] {ticker} {test_month} profile={selected['profile']} "
                    f"cfg={selected['deploy_config']} val_pf={selected_row.get('val_profit_factor', float('nan')):.3f} "
                    f"test_trades={selected_row.get('test_trades', 0)} "
                    f"test_pf={selected_row.get('test_profit_factor', float('nan')):.3f} "
                    f"test_ret={selected_row.get('test_pnl_return', 0.0):.2f}",
                    flush=True,
                )
            else:
                selected_row = {
                    "ticker": ticker,
                    "month": str(test_month),
                    "profile": "ABSTAIN_NO_VALID_PROFILE",
                    "selected": False,
                    "test_trades": 0,
                    "test_pnl_return": 0.0,
                    "test_profit_factor": float("nan"),
                    "test_win_rate": float("nan"),
                }
                print(f"[PROFILE_SELECTOR] {ticker} {test_month} abstain no valid profile", flush=True)
            selected_rows.append(selected_row)

            trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
            folds = pd.DataFrame(selected_rows)
            candidates = pd.DataFrame(candidate_rows)
            if not trades.empty:
                trades.to_csv(output_dir / "event_option_profile_trades.csv", index=False)
            folds.to_csv(output_dir / "selected_folds.csv", index=False)
            candidates.to_csv(output_dir / "candidate_validation.csv", index=False)
            write_summary(output_dir, trades, folds, candidates, metadata)

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    folds = pd.DataFrame(selected_rows)
    candidates = pd.DataFrame(candidate_rows)
    if not trades.empty:
        trades.to_csv(output_dir / "event_option_profile_trades.csv", index=False)
        write_daily_plot(output_dir, trades, float(args.risk_capital))
    folds.to_csv(output_dir / "selected_folds.csv", index=False)
    candidates.to_csv(output_dir / "candidate_validation.csv", index=False)
    provenance = write_policy_selection_provenance(
        output_dir,
        folds,
        expected_months=months,
        expected_tickers=test_tickers,
    )
    metadata["policy_selection_provenance"] = provenance
    write_summary(output_dir, trades, folds, candidates, metadata)
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
