#!/usr/bin/env python3
"""Frozen volatility-complex extension of DIRECTIONAL_SEMANTIC_JEPA_V1."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import torch

try:
    from neural.jepa import evaluate_directional_semantic_jepa_v1 as parent
except ModuleNotFoundError:  # Direct execution from neural/jepa.
    import evaluate_directional_semantic_jepa_v1 as parent


REPO_ROOT = Path(__file__).resolve().parents[2]
PREDECLARATION = REPO_ROOT / "research_papers/JEPA/DIRECTIONAL_VOL_COMPLEX_V1_PREDECLARATION.md"
COVERAGE_AMENDMENT = (
    REPO_ROOT / "research_papers/JEPA/DIRECTIONAL_VOL_COMPLEX_V1_VIX_COVERAGE_AMENDMENT.md"
)
CAPTURE_SEAL = (
    REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "cboe_vol_complex_directional_v1_20260716_capture_seal/manifest.json"
)
DEFAULT_PARENT_DEVELOPMENT = parent.DEFAULT_DEVELOPMENT_OUTPUT
DEFAULT_DATA_ROOT = parent.DEFAULT_DATA_ROOT
DEFAULT_VIX_ROOT = DEFAULT_DATA_ROOT / "VIX"
DEFAULT_CBOE_ROOT = Path("D:/ThetaData/cboe_vol_complex_directional_v1_20260716")
DEFAULT_DEVELOPMENT_OUTPUT = (
    REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_vol_complex_v1_development_202208_202512"
)
DEFAULT_EVALUATION_OUTPUT = (
    REPO_ROOT
    / "research_papers/JEPA/results/_diagnostics/"
    "directional_vol_complex_v1_evaluation_202601_20260715"
)

CBOE_MANIFEST_SHA256 = "5c5e5c8b65ba7e8fe552049f12900b22d0581827f0b6190b066cd4fcc5c473ce"
CBOE_FILES = {
    "VIX1D_History.csv": "eea02196f50478dddeffd949ffad31120a53803e05015e510ea2eb7bf44a889e",
    "VIX9D_History.csv": "c97de274e586d66435655b6044be303933637e87091bfbbc40c5339cbaaa65bc",
    "VIX_History.csv": "5c8ff5d3480a202ed8b273198f4b2f7759c03ec1ec5f9f3fe30c4699916fc95c",
    "VIX3M_History.csv": "4f65c3fe109bd7069e1458125d83f40daf07c7bc2efe9c9c5241c24b6d30e9c7",
    "VIX6M_History.csv": "d27cd4fc1a8e715b2d73d5fa73f62c0972384221a100661543e41f8d69fc3544",
    "VIX1Y_History.csv": "7bfdccd530282133ca4c690f5dc097650618cb4796d5626aedfe5a5f67a3684a",
    "VVIX_History.csv": "b8086c53bb24fd48f7a644986f048a117bc43cb0324652f88df7790babc2e05f",
}
SERIES_FILES = {
    "vix1d": "VIX1D_History.csv",
    "vix9d": "VIX9D_History.csv",
    "vix": "VIX_History.csv",
    "vix3m": "VIX3M_History.csv",
    "vix6m": "VIX6M_History.csv",
    "vix1y": "VIX1Y_History.csv",
    "vvix": "VVIX_History.csv",
}
VIX_PROFILE = "VIX_INTRADAY_RESIDUAL"
VOL_PROFILE = "VOL_COMPLEX_RESIDUAL"
SELECTABLE_PROFILES = (VIX_PROFILE, VOL_PROFILE)
PARENT_CONTROL = "PARENT_SEMANTIC_CONTROL"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str | Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory_digest(inventory: pd.DataFrame, columns: list[str]) -> str:
    payload = inventory[columns].to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_cboe_capture(root: Path) -> dict:
    manifest_path = root / "manifest.json"
    if sha256_file(manifest_path) != CBOE_MANIFEST_SHA256:
        raise AssertionError("Cboe capture manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "cboe_vol_complex_directional_v1_capture"
        or manifest.get("status") != "PASS_CBOE_VOL_COMPLEX_CAPTURE"
        or not bool(manifest.get("outcome_free"))
        or bool(manifest.get("holdout_2026_outcomes_used", True))
    ):
        raise AssertionError("invalid Cboe capture contract")
    records = {str(record["file"]): record for record in manifest.get("files", [])}
    if set(records) != set(CBOE_FILES):
        raise AssertionError("Cboe capture file set mismatch")
    for name, expected_hash in CBOE_FILES.items():
        path = root / name
        if records[name].get("sha256") != expected_hash or sha256_file(path) != expected_hash:
            raise AssertionError(f"{name}: frozen source hash mismatch")
        if records[name].get("in_scope_ohlc_envelope_failures") != 0:
            raise AssertionError(f"{name}: frozen in-scope envelope gate changed")
        if str(records[name].get("date_max")) != parent.EVALUATION_END:
            raise AssertionError(f"{name}: frozen end date mismatch")
    compact = json.loads(CAPTURE_SEAL.read_text(encoding="utf-8"))
    if (
        compact.get("external_manifest_sha256") != CBOE_MANIFEST_SHA256
        or compact.get("files") != CBOE_FILES
        or not compact.get("vix_local_parity", {}).get("gate_pass")
    ):
        raise AssertionError("compact Cboe seal mismatch")
    return manifest


def load_cboe_series(root: Path) -> dict[str, pd.DataFrame]:
    verify_cboe_capture(root)
    result: dict[str, pd.DataFrame] = {}
    for series, filename in SERIES_FILES.items():
        raw = pd.read_csv(root / filename)
        value_column = "VVIX" if series == "vvix" else "CLOSE"
        if "DATE" not in raw or value_column not in raw:
            raise KeyError(f"{filename}: required daily close missing")
        frame = pd.DataFrame(
            {
                "source_date": pd.to_datetime(raw["DATE"], errors="coerce"),
                "value": pd.to_numeric(raw[value_column], errors="coerce"),
            }
        ).sort_values("source_date", kind="stable").reset_index(drop=True)
        if (
            frame.empty
            or frame["source_date"].isna().any()
            or frame["source_date"].duplicated().any()
            or not np.isfinite(frame["value"]).all()
            or not (frame["value"] > 0.0).all()
        ):
            raise AssertionError(f"{filename}: invalid daily value series")
        result[series] = frame
    return result


def _strict_prior_observation(frame: pd.DataFrame, trade_date: str) -> tuple[int, pd.Timestamp]:
    decision_date = pd.Timestamp(trade_date)
    dates = frame["source_date"].to_numpy(dtype="datetime64[ns]")
    position = int(np.searchsorted(dates, decision_date.to_datetime64(), side="left") - 1)
    if position < 5:
        raise AssertionError(f"{trade_date}: insufficient lagged volatility history")
    source_date = pd.Timestamp(frame.iloc[position]["source_date"])
    calendar_lag = int((decision_date - source_date).days)
    if source_date >= decision_date or not 1 <= calendar_lag <= 7:
        raise AssertionError(f"{trade_date}: non-causal/stale volatility close {source_date.date()}")
    return position, source_date


def build_term_feature_row(
    series_frames: dict[str, pd.DataFrame], trade_date: str
) -> tuple[dict[str, float], dict[str, str]]:
    values: dict[str, float] = {}
    source_dates: dict[str, str] = {}
    levels: dict[str, float] = {}
    for series in SERIES_FILES:
        frame = series_frames[series]
        position, source_date = _strict_prior_observation(frame, trade_date)
        current = float(frame.iloc[position]["value"])
        prior_one = float(frame.iloc[position - 1]["value"])
        prior_five = float(frame.iloc[position - 5]["value"])
        values[f"cboe_{series}_previous_close"] = current
        values[f"cboe_{series}_change_1obs"] = current - prior_one
        values[f"cboe_{series}_change_5obs"] = current - prior_five
        levels[series] = current
        source_dates[series] = source_date.strftime("%Y%m%d")

    adjacent = (("vix1d", "vix9d"), ("vix9d", "vix"), ("vix", "vix3m"), ("vix3m", "vix6m"), ("vix6m", "vix1y"))
    for near, far in adjacent:
        values[f"term_ratio_{near}_{far}"] = levels[near] / levels[far]
        values[f"term_slope_{far}_minus_{near}"] = levels[far] - levels[near]
    values["term_short_curvature"] = levels["vix1d"] - 2.0 * levels["vix9d"] + levels["vix"]
    values["term_vvix_vix_ratio"] = levels["vvix"] / levels["vix"]
    if not np.isfinite(list(values.values())).all():
        raise AssertionError(f"{trade_date}: non-finite volatility-complex features")
    return values, source_dates


def discover_vix_files(root: Path, end_date: str) -> pd.DataFrame:
    rows: list[dict] = []
    for path in sorted(root.glob("*/*/*.parquet")):
        day = parent.canonical_date(path.stem)
        if parent.START_DATE <= day <= end_date:
            rows.append(
                {
                    "trade_date": day,
                    "path": str(path.resolve()),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    inventory = pd.DataFrame(rows).sort_values("trade_date", kind="stable").reset_index(drop=True)
    if inventory.empty or inventory["trade_date"].duplicated().any():
        raise AssertionError("invalid/empty local VIX inventory")
    return inventory


def load_vix_sessions(
    inventory: pd.DataFrame, master_dates: set[str]
) -> dict[str, pd.DataFrame]:
    sessions: dict[str, pd.DataFrame] = {}
    for row in inventory.itertuples(index=False):
        day = str(row.trade_date)
        if day not in master_dates:
            continue
        sessions[day] = parent.validate_bar_frame(pd.read_parquet(row.path), "VIX", day)
    return dict(sorted(sessions.items()))


def vix_feature_names() -> list[str]:
    names = ["vix_level_1035", "vix_ret_1m"]
    for horizon in (5, 15, 30, 60):
        names.extend(
            [
                f"vix_ret_{horizon}m",
                f"vix_rv_{horizon}m",
                f"vix_range_{horizon}m",
                f"vix_close_location_{horizon}m",
            ]
        )
    names.extend(["vix_ret_since_open", "vix_gap_bps"])
    for horizon in (5, 15, 30, 60):
        names.append(f"vix_spx_divergence_{horizon}m")
    for horizon in (15, 30, 60):
        names.extend([f"vix_spx_corr_{horizon}m", f"vix_spx_beta_{horizon}m"])
    return names


def _return_correlation_beta(
    vix: pd.DataFrame, spx: pd.DataFrame, end_position: int, horizon: int
) -> tuple[float, float]:
    start = end_position - horizon
    vix_returns = np.diff(np.log(vix.iloc[start : end_position + 1]["close"].to_numpy(dtype=np.float64)))
    spx_returns = np.diff(np.log(spx.iloc[start : end_position + 1]["close"].to_numpy(dtype=np.float64)))
    if len(vix_returns) != horizon or len(spx_returns) != horizon:
        raise AssertionError("VIX/SPX correlation window mismatch")
    vix_std = float(np.std(vix_returns, ddof=0))
    spx_variance = float(np.var(spx_returns, ddof=0))
    if vix_std <= 1e-12 or spx_variance <= 1e-18:
        return 0.0, 0.0
    spx_std = math.sqrt(spx_variance)
    covariance = float(np.mean((vix_returns - vix_returns.mean()) * (spx_returns - spx_returns.mean())))
    return covariance / (vix_std * spx_std), covariance / spx_variance


def build_vix_feature_row(
    trade_date: str,
    vix_frame: pd.DataFrame,
    previous_vix_date: str,
    previous_vix_frame: pd.DataFrame,
    spx_frame: pd.DataFrame,
) -> dict[str, float]:
    trade_date = parent.canonical_date(trade_date)
    previous_vix_date = parent.canonical_date(previous_vix_date)
    decision = pd.Timestamp(
        f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]} {parent.DECISION_TIME}"
    )
    position = int(vix_frame.index.get_loc(decision))
    close = float(vix_frame.iloc[position]["close"])
    row: dict[str, float] = {
        "vix_level_1035": close,
        "vix_ret_1m": parent.log_return_bps(close, float(vix_frame.iloc[position - 1]["close"])),
    }
    vix_returns: dict[int, float] = {}
    for horizon in (5, 15, 30, 60):
        metrics = parent._window_metrics(vix_frame, position, horizon)
        vix_returns[horizon] = float(metrics["ret"])
        for metric, value in metrics.items():
            row[f"vix_{metric}_{horizon}m"] = float(value)
    row["vix_ret_since_open"] = parent.log_return_bps(close, float(vix_frame.iloc[0]["open"]))
    row["vix_gap_bps"] = parent.log_return_bps(
        float(vix_frame.iloc[0]["open"]), parent.session_close(previous_vix_frame, previous_vix_date)
    )
    spx_position = int(spx_frame.index.get_loc(decision))
    for horizon in (5, 15, 30, 60):
        spx_return = float(parent._window_metrics(spx_frame, spx_position, horizon)["ret"])
        row[f"vix_spx_divergence_{horizon}m"] = vix_returns[horizon] - spx_return
    for horizon in (15, 30, 60):
        correlation, beta = _return_correlation_beta(vix_frame, spx_frame, position, horizon)
        row[f"vix_spx_corr_{horizon}m"] = correlation
        row[f"vix_spx_beta_{horizon}m"] = beta
    names = vix_feature_names()
    if list(row) != names or not np.isfinite([row[name] for name in names]).all():
        raise AssertionError(f"{trade_date}: invalid VIX feature contract")
    return row


def build_vol_daily_frame(
    underlying_sessions: dict[str, dict[str, pd.DataFrame]],
    arrays_by_date: dict[str, np.ndarray],
    model: parent.SemanticJEPA,
    normalizer: parent.Normalizer,
    device: torch.device,
    vix_sessions: dict[str, pd.DataFrame],
    cboe_series: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, list[str], list[str], list[str], list[str]]:
    daily, technical_features, semantic_features = parent.build_daily_frame(
        underlying_sessions, arrays_by_date, model, normalizer, device
    )
    master_dates = sorted(daily["trade_date"].unique())
    exact_vix_dates = sorted(vix_sessions)
    previous_exact: dict[str, str] = {}
    prior: str | None = None
    for day in exact_vix_dates:
        if prior is not None:
            previous_exact[day] = prior
        prior = day

    vix_names = vix_feature_names()
    term_names: list[str] | None = None
    day_rows: list[dict] = []
    for day in master_dates:
        term, source_dates = build_term_feature_row(cboe_series, day)
        if term_names is None:
            term_names = list(term)
        elif list(term) != term_names:
            raise AssertionError("term feature order changed")
        row: dict[str, object] = {
            "trade_date": day,
            **term,
            "term_source_min_date": min(source_dates.values()),
            "term_source_max_date": max(source_dates.values()),
        }
        available = day in vix_sessions and day in previous_exact
        row["vol_source_available"] = bool(available)
        if available:
            previous_day = previous_exact[day]
            row.update(
                build_vix_feature_row(
                    day,
                    vix_sessions[day],
                    previous_day,
                    vix_sessions[previous_day],
                    underlying_sessions[day]["SPXW"],
                )
            )
        else:
            row.update({name: np.nan for name in vix_names})
        day_rows.append(row)
    if term_names is None:
        raise AssertionError("no volatility-complex rows")
    daily = daily.merge(pd.DataFrame(day_rows), on="trade_date", how="left", validate="many_to_one")
    if daily["vol_source_available"].isna().any():
        raise AssertionError("volatility-source availability merge failed")
    exact = daily["vol_source_available"].astype(bool)
    if daily.loc[exact, vix_names].isna().any().any() or not np.isfinite(daily.loc[exact, vix_names]).all().all():
        raise AssertionError("exact VIX rows contain invalid features")
    if daily.loc[~exact, vix_names].notna().any().any():
        raise AssertionError("missing VIX rows were imputed")
    if daily[term_names].isna().any().any() or not np.isfinite(daily[term_names]).all().all():
        raise AssertionError("term features contain invalid values")
    if not (daily["term_source_max_date"] < daily["trade_date"]).all():
        raise AssertionError("same-day/future Cboe close entered the daily frame")
    return daily, technical_features, semantic_features, vix_names, term_names


def _model_features(
    profile_id: str,
    technical_features: list[str],
    semantic_features: list[str],
    vix_features: list[str],
    term_features: list[str],
) -> list[str]:
    base = technical_features + semantic_features + vix_features
    if profile_id == VIX_PROFILE:
        return base
    if profile_id == VOL_PROFILE:
        return base + term_features
    raise KeyError(f"unknown volatility profile: {profile_id}")


def _trades_with_source_flags(
    test: pd.DataFrame, prediction: np.ndarray, profile_id: str, fallback: np.ndarray
) -> pd.DataFrame:
    trades = parent.predictions_to_trades(test, prediction, profile_id)
    available = test["vol_source_available"].to_numpy(dtype=bool)
    trades["vol_source_available"] = available
    trades["fallback_parent"] = fallback.astype(bool)
    trades["prediction_origin"] = np.where(fallback, parent.SEMANTIC_PROFILE, profile_id)
    if len(trades) != len(test) or (trades["fallback_parent"] & trades["vol_source_available"]).any():
        raise AssertionError("fallback/source flag contract failed")
    return trades


def run_walkforward(
    daily: pd.DataFrame,
    months: list[str],
    technical_features: list[str],
    semantic_features: list[str],
    vix_features: list[str],
    term_features: list[str],
    profiles_by_ticker: dict[str, str] | None = None,
    include_parent_control: bool = False,
) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    for ticker in sorted(daily["ticker"].unique()):
        ticker_frame = daily.loc[daily["ticker"].eq(ticker)].copy()
        requested = [profiles_by_ticker[ticker]] if profiles_by_ticker else list(SELECTABLE_PROFILES)
        for month in months:
            train = ticker_frame.loc[ticker_frame["month"] < month].copy()
            test = ticker_frame.loc[ticker_frame["month"].eq(month)].copy()
            if test.empty:
                continue
            if len(train) < 400:
                raise AssertionError(f"{ticker} {month}: insufficient parent training rows")
            parent_prediction, _ = parent.fit_residual_predictor(
                train,
                test,
                technical_features,
                technical_features + semantic_features,
            )
            exact_train = train.loc[train["vol_source_available"].astype(bool)].copy()
            exact_mask = test["vol_source_available"].to_numpy(dtype=bool)
            if len(exact_train) < 400:
                raise AssertionError(f"{ticker} {month}: insufficient exact-VIX training rows")
            for profile_id in requested:
                prediction = parent_prediction.copy()
                if exact_mask.any():
                    exact_prediction, _ = parent.fit_residual_predictor(
                        exact_train,
                        test.loc[exact_mask],
                        technical_features,
                        _model_features(
                            profile_id,
                            technical_features,
                            semantic_features,
                            vix_features,
                            term_features,
                        ),
                    )
                    prediction[exact_mask] = exact_prediction
                outputs.append(
                    _trades_with_source_flags(test, prediction, profile_id, ~exact_mask)
                )
            if include_parent_control:
                outputs.append(
                    _trades_with_source_flags(
                        test, parent_prediction, PARENT_CONTROL, ~exact_mask
                    )
                )
    if not outputs:
        raise AssertionError("volatility walk-forward produced no trades")
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["ticker", "trade_date", "profile_id"], kind="stable"
    ).reset_index(drop=True)


def select_profiles(trades: pd.DataFrame) -> tuple[dict[str, str], pd.DataFrame]:
    selectable = trades.loc[trades["profile_id"].isin(SELECTABLE_PROFILES)]
    monthly = parent.monthly_metrics(selectable)
    selections: dict[str, str] = {}
    ranking_rows: list[dict] = []
    for ticker in sorted(monthly["ticker"].unique()):
        candidates: list[dict] = []
        for profile_id in SELECTABLE_PROFILES:
            profile_monthly = monthly.loc[
                monthly["ticker"].eq(ticker) & monthly["profile_id"].eq(profile_id)
            ].sort_values("month")
            profile_trades = selectable.loc[
                selectable["ticker"].eq(ticker) & selectable["profile_id"].eq(profile_id)
            ]
            if len(profile_monthly) != 12 or int(profile_monthly["trades"].min()) < 13:
                raise AssertionError(f"{ticker} {profile_id}: incomplete development coverage")
            candidates.append(
                {
                    "ticker": ticker,
                    "profile_id": profile_id,
                    "positive_months": int((profile_monthly["net_bps"] > 0.0).sum()),
                    "monthly_net_q25": float(profile_monthly["net_bps"].quantile(0.25)),
                    "aggregate_profit_factor": parent.profit_factor(profile_trades["net_bps"]),
                    "aggregate_win_rate": float((profile_trades["net_bps"] > 0.0).mean()),
                    "aggregate_net_bps": float(profile_trades["net_bps"].sum()),
                    "min_month_trades": int(profile_monthly["trades"].min()),
                }
            )
        candidates.sort(
            key=lambda item: (
                -item["positive_months"],
                -item["monthly_net_q25"],
                -item["aggregate_profit_factor"],
                item["profile_id"],
            )
        )
        for rank, candidate in enumerate(candidates, start=1):
            candidate["rank"] = rank
            candidate["selected"] = rank == 1
            ranking_rows.append(candidate)
        selections[ticker] = candidates[0]["profile_id"]
    return selections, pd.DataFrame(ranking_rows)


def _verify_parent_contract(
    parent_dir: Path, device: torch.device
) -> tuple[dict, dict, parent.Normalizer, parent.SemanticJEPA, list[str], list[str]]:
    loaded = parent._load_development(parent_dir, device)
    metrics, provenance = loaded[:2]
    if set(metrics.get("selected_profiles", {}).values()) != {parent.SEMANTIC_PROFILE}:
        raise AssertionError("parent development did not freeze SEMANTIC_RESIDUAL")
    if provenance.get("semantic_jepa_sha256") != sha256_file(parent_dir / "semantic_jepa.pt"):
        raise AssertionError("parent JEPA hash mismatch")
    return loaded


def _build_inputs(
    *,
    data_root: Path,
    vix_root: Path,
    cboe_root: Path,
    parent_dir: Path,
    end_date: str,
    device: torch.device,
) -> tuple[
    pd.DataFrame,
    list[str],
    list[str],
    list[str],
    list[str],
    pd.DataFrame,
    pd.DataFrame,
    dict,
    dict,
]:
    parent_metrics, parent_provenance, normalizer, model, frozen_technical, frozen_semantic = (
        _verify_parent_contract(parent_dir, device)
    )
    underlying_inventory = parent.discover_source_files(data_root, end_date)
    expected_count = 859 if end_date == parent.DEVELOPMENT_END else 992
    observed_counts = underlying_inventory.groupby("ticker").size().to_dict()
    if observed_counts != {ticker: expected_count for ticker in parent.SOURCE_TICKERS}:
        raise AssertionError(f"underlying source census mismatch: {observed_counts}")
    if end_date == parent.DEVELOPMENT_END:
        parent._verify_development_sources(underlying_inventory, parent_dir, parent_provenance)
    usable_inventory = underlying_inventory.loc[
        ~underlying_inventory["trade_date"].isin(parent.INVALID_SOURCE_DAYS)
    ].copy()
    underlying_sessions = parent.load_sessions(usable_inventory)
    _, arrays_by_date = parent._arrays_for_dates(underlying_sessions, sorted(underlying_sessions))
    vix_inventory = discover_vix_files(vix_root, end_date)
    vix_sessions = load_vix_sessions(vix_inventory, set(underlying_sessions))
    cboe_series = load_cboe_series(cboe_root)
    daily, technical, semantic, vix_features, term_features = build_vol_daily_frame(
        underlying_sessions,
        arrays_by_date,
        model,
        normalizer,
        device,
        vix_sessions,
        cboe_series,
    )
    if technical != frozen_technical or semantic != frozen_semantic:
        raise AssertionError("parent feature contract changed")
    return (
        daily,
        technical,
        semantic,
        vix_features,
        term_features,
        underlying_inventory,
        vix_inventory,
        parent_metrics,
        parent_provenance,
    )


def _common_provenance(
    underlying_inventory: pd.DataFrame,
    vix_inventory: pd.DataFrame,
    parent_dir: Path,
) -> dict:
    return {
        "schema": "directional_vol_complex_v1_provenance",
        "created_at_utc": utc_now(),
        "runner_path": str(Path(__file__).resolve().relative_to(REPO_ROOT)),
        "runner_sha256": sha256_file(__file__),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "coverage_amendment_sha256": sha256_file(COVERAGE_AMENDMENT),
        "capture_seal_sha256": sha256_file(CAPTURE_SEAL),
        "cboe_manifest_sha256": CBOE_MANIFEST_SHA256,
        "cboe_file_sha256": CBOE_FILES,
        "underlying_inventory_rows": int(len(underlying_inventory)),
        "underlying_inventory_sha256": parent._source_inventory_digest(underlying_inventory),
        "vix_inventory_rows": int(len(vix_inventory)),
        "vix_inventory_sha256": _inventory_digest(
            vix_inventory, ["trade_date", "path", "size_bytes", "sha256"]
        ),
        "parent_metrics_sha256": sha256_file(parent_dir / "metrics.json"),
        "parent_provenance_sha256": sha256_file(parent_dir / "provenance.json"),
        "parent_model_sha256": sha256_file(parent_dir / "semantic_jepa.pt"),
        "holdout_2026_used_for_selection": False,
        "same_day_cboe_close_used": False,
        "missing_vix_imputed": False,
        "production_modified": False,
    }


def run_development(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable development output exists: {output}")
    parent_dir = Path(args.parent_development_dir)
    device = torch.device(args.device)
    (
        daily,
        technical,
        semantic,
        vix_features,
        term_features,
        underlying_inventory,
        vix_inventory,
        _,
        _,
    ) = _build_inputs(
        data_root=Path(args.data_root),
        vix_root=Path(args.vix_root),
        cboe_root=Path(args.cboe_root),
        parent_dir=parent_dir,
        end_date=parent.DEVELOPMENT_END,
        device=device,
    )
    months = [f"2025{month:02d}" for month in range(1, 13)]
    trades = run_walkforward(
        daily,
        months,
        technical,
        semantic,
        vix_features,
        term_features,
        include_parent_control=True,
    )
    selections, ranking = select_profiles(trades)
    monthly = parent.monthly_metrics(trades)
    exact_2025 = daily.loc[daily["month"].str.startswith("2025"), "vol_source_available"]
    if not exact_2025.astype(bool).all():
        raise AssertionError("2025 development unexpectedly used VIX fallback")
    metrics = {
        "schema": "directional_vol_complex_v1_development_metrics",
        "status": "PASS_DEVELOPMENT_FREEZE",
        "created_at_utc": utc_now(),
        "scope": {"start_date": parent.START_DATE, "end_date": parent.DEVELOPMENT_END, "months": months},
        "selected_profiles": selections,
        "daily_rows": int(len(daily)),
        "vix_available_daily_rows": int(daily["vol_source_available"].sum()),
        "vix_missing_daily_rows": int((~daily["vol_source_available"].astype(bool)).sum()),
        "feature_counts": {
            "technical": len(technical),
            "semantic": len(semantic),
            "vix_intraday": len(vix_features),
            "cboe_term": len(term_features),
        },
        "development_fallback_trades": int(trades["fallback_parent"].sum()),
        "holdout_2026_used": False,
        "production_modified": False,
    }
    provenance = _common_provenance(underlying_inventory, vix_inventory, parent_dir)
    output.mkdir(parents=True, exist_ok=False)
    underlying_inventory.to_csv(output / "underlying_source_inventory.csv", index=False, lineterminator="\n")
    vix_inventory.to_csv(output / "vix_source_inventory.csv", index=False, lineterminator="\n")
    trades.to_parquet(output / "development_trade_ledger.parquet", index=False)
    monthly.to_csv(output / "development_monthly_metrics.csv", index=False)
    ranking.to_csv(output / "profile_ranking.csv", index=False)
    for name, features in (
        ("technical_features.json", technical),
        ("semantic_features.json", semantic),
        ("vix_features.json", vix_features),
        ("term_features.json", term_features),
    ):
        (output / name).write_text(json.dumps(features, indent=2), encoding="utf-8")
    provenance.update(
        {
            "development_trade_ledger_sha256": sha256_file(output / "development_trade_ledger.parquet"),
            "development_monthly_metrics_sha256": sha256_file(output / "development_monthly_metrics.csv"),
            "profile_ranking_sha256": sha256_file(output / "profile_ranking.csv"),
        }
    )
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    metrics["provenance_sha256"] = sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def _load_frozen_development(development_dir: Path) -> tuple[dict, dict, list[str], list[str], list[str], list[str]]:
    metrics = json.loads((development_dir / "metrics.json").read_text(encoding="utf-8"))
    provenance = json.loads((development_dir / "provenance.json").read_text(encoding="utf-8"))
    if (
        metrics.get("schema") != "directional_vol_complex_v1_development_metrics"
        or metrics.get("status") != "PASS_DEVELOPMENT_FREEZE"
        or bool(metrics.get("holdout_2026_used", True))
    ):
        raise AssertionError("invalid volatility development freeze")
    expected = {
        "runner_sha256": sha256_file(__file__),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "coverage_amendment_sha256": sha256_file(COVERAGE_AMENDMENT),
        "capture_seal_sha256": sha256_file(CAPTURE_SEAL),
        "cboe_manifest_sha256": CBOE_MANIFEST_SHA256,
    }
    for key, value in expected.items():
        if provenance.get(key) != value:
            raise AssertionError(f"development freeze {key} mismatch")
    if metrics.get("provenance_sha256") != sha256_file(development_dir / "provenance.json"):
        raise AssertionError("development provenance hash mismatch")
    artifacts = {
        "development_trade_ledger_sha256": "development_trade_ledger.parquet",
        "development_monthly_metrics_sha256": "development_monthly_metrics.csv",
        "profile_ranking_sha256": "profile_ranking.csv",
    }
    for key, filename in artifacts.items():
        if provenance.get(key) != sha256_file(development_dir / filename):
            raise AssertionError(f"development artifact {filename} hash mismatch")
    feature_lists = tuple(
        json.loads((development_dir / name).read_text(encoding="utf-8"))
        for name in (
            "technical_features.json",
            "semantic_features.json",
            "vix_features.json",
            "term_features.json",
        )
    )
    return metrics, provenance, *feature_lists


def _verify_frozen_inventories(
    development_dir: Path,
    underlying_inventory: pd.DataFrame,
    vix_inventory: pd.DataFrame,
    provenance: dict,
) -> None:
    frozen_underlying = pd.read_csv(
        development_dir / "underlying_source_inventory.csv", dtype={"trade_date": str}
    )
    current_underlying = underlying_inventory.loc[
        underlying_inventory["trade_date"] <= parent.DEVELOPMENT_END
    ].reset_index(drop=True)
    underlying_columns = ["ticker", "trade_date", "path", "size_bytes", "sha256"]
    if not frozen_underlying[underlying_columns].astype(str).equals(
        current_underlying[underlying_columns].astype(str)
    ):
        raise AssertionError("pre-2026 underlying inventory changed")
    frozen_vix = pd.read_csv(development_dir / "vix_source_inventory.csv", dtype={"trade_date": str})
    current_vix = vix_inventory.loc[vix_inventory["trade_date"] <= parent.DEVELOPMENT_END].reset_index(drop=True)
    vix_columns = ["trade_date", "path", "size_bytes", "sha256"]
    if not frozen_vix[vix_columns].astype(str).equals(current_vix[vix_columns].astype(str)):
        raise AssertionError("pre-2026 local VIX inventory changed")
    if provenance.get("underlying_inventory_sha256") != parent._source_inventory_digest(current_underlying):
        raise AssertionError("frozen underlying digest mismatch")
    if provenance.get("vix_inventory_sha256") != _inventory_digest(current_vix, vix_columns):
        raise AssertionError("frozen VIX digest mismatch")


def run_evaluation(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable evaluation output exists: {output}")
    development_dir = Path(args.development_dir)
    parent_dir = Path(args.parent_development_dir)
    frozen_metrics, frozen_provenance, technical, semantic, vix_features, term_features = (
        _load_frozen_development(development_dir)
    )
    device = torch.device(args.device)
    (
        daily,
        observed_technical,
        observed_semantic,
        observed_vix,
        observed_term,
        underlying_inventory,
        vix_inventory,
        _,
        _,
    ) = _build_inputs(
        data_root=Path(args.data_root),
        vix_root=Path(args.vix_root),
        cboe_root=Path(args.cboe_root),
        parent_dir=parent_dir,
        end_date=parent.EVALUATION_END,
        device=device,
    )
    if (observed_technical, observed_semantic, observed_vix, observed_term) != (
        technical,
        semantic,
        vix_features,
        term_features,
    ):
        raise AssertionError("evaluation feature contract changed")
    _verify_frozen_inventories(
        development_dir, underlying_inventory, vix_inventory, frozen_provenance
    )
    months = [f"2026{month:02d}" for month in range(1, 8)]
    selected = {str(key): str(value) for key, value in frozen_metrics["selected_profiles"].items()}
    if set(selected.values()).difference(SELECTABLE_PROFILES):
        raise AssertionError("frozen development selected an unknown profile")
    trades = run_walkforward(
        daily,
        months,
        technical,
        semantic,
        vix_features,
        term_features,
        profiles_by_ticker=selected,
    )
    complete_months = months[:6]
    gate = parent.evaluate_complete_month_gate(trades, complete_months)
    monthly = parent.monthly_metrics(trades)
    july = monthly.loc[monthly["month"].eq("202607")].copy()
    july["month"] = "202607_MTD"
    fallback = trades.loc[trades["fallback_parent"]]
    metrics = {
        "schema": "directional_vol_complex_v1_evaluation_metrics",
        "status": "PASS_2026_GATE" if gate["joint_gate_pass"] else "CLOSED_2026_GATE",
        "created_at_utc": utc_now(),
        "scope": {
            "start_date": "20260101",
            "end_date": parent.EVALUATION_END,
            "complete_months": complete_months,
            "july_status": "MTD",
        },
        "selected_profiles": selected,
        "execution": {
            "decision_time": parent.DECISION_TIME,
            "entry_time": parent.ENTRY_TIME,
            "exit_time": parent.EXIT_TIME,
            "hold_minutes": parent.HOLD_MINUTES,
            "cost_bps": parent.COST_BPS,
            "overlap_count": 0,
            "fill_kind": "underlying_open_spot_proxy_not_futures_fill",
        },
        "fallback_parent_trades": int(len(fallback)),
        "fallback_dates": sorted(fallback["trade_date"].unique().tolist()),
        **gate,
        "july_mtd": july.to_dict("records"),
        "production_modified": False,
    }
    provenance = _common_provenance(underlying_inventory, vix_inventory, parent_dir)
    provenance.update(
        {
            "development_metrics_sha256": sha256_file(development_dir / "metrics.json"),
            "development_provenance_sha256": sha256_file(development_dir / "provenance.json"),
            "holdout_2026_used_for_selection": False,
            "futures_fills_validated": False,
        }
    )
    output.mkdir(parents=True, exist_ok=False)
    underlying_inventory.to_csv(output / "underlying_source_inventory.csv", index=False, lineterminator="\n")
    vix_inventory.to_csv(output / "vix_source_inventory.csv", index=False, lineterminator="\n")
    trades.to_parquet(output / "trade_ledger.parquet", index=False)
    monthly.to_csv(output / "monthly_metrics.csv", index=False)
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    metrics["provenance_sha256"] = sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("development", "evaluation"), required=True)
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--vix-root", default=str(DEFAULT_VIX_ROOT))
    parser.add_argument("--cboe-root", default=str(DEFAULT_CBOE_ROOT))
    parser.add_argument("--parent-development-dir", default=str(DEFAULT_PARENT_DEVELOPMENT))
    parser.add_argument("--development-dir", default=str(DEFAULT_DEVELOPMENT_OUTPUT))
    parser.add_argument("--output", default="")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()
    if not args.output:
        args.output = str(
            DEFAULT_DEVELOPMENT_OUTPUT if args.phase == "development" else DEFAULT_EVALUATION_OUTPUT
        )
    return args


def main() -> int:
    args = parse_args()
    if args.phase == "development":
        run_development(args)
    else:
        run_evaluation(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
