#!/usr/bin/env python3
"""Reproduce the post-outcome 2025 development for cross-venue V4."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from neural.jepa import evaluate_cross_venue_calendar_rr_leader_v2 as v2  # noqa: E402
from neural.jepa.build_calendar_risk_reversal_pressure_v1 import (  # noqa: E402
    canonical_date,
    tracked_clean,
)


PROJECT_ROOT = SCRIPT_REPO_ROOT
TICKERS = v2.TICKERS
SENSOR_MAP = v2.SENSOR_MAP
FEATURE_COLUMNS = v2.FEATURE_COLUMNS
COSTS_BPS = v2.COSTS_BPS
MIN_MONTH_TRADES_EXCLUSIVE = 12
MIN_WIN_RATE = 0.45
INCREMENTAL_MIN_PF = 1.0
OBJECTIVE_MIN_PF = 1.20

PREDECLARATION = PROJECT_ROOT / (
    "research_papers/JEPA/"
    "CROSS_VENUE_CALENDAR_RR_LEADER_V4_FULL_HISTORY_LOGISTIC_PREDECLARATION.md"
)
V2_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v2_development_202301_202412_v1"
)
V3_OUTER_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v3_outer_2025_v1"
)
DATA_GATE_DIR = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v1_data_gate_202401_202512_v1r1"
)
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "research_papers/JEPA/results/_diagnostics/"
    "cross_venue_calendar_rr_leader_v4_development_2025_v1"
)
INPUT_HASHES = {
    V2_DIR / "development_dataset.parquet": (
        "459979c11ad5b7ba1ed44ef3add42142d0eab40982882bc52031982e22778f0b"
    ),
    V3_OUTER_DIR / "trades.csv": (
        "a45a6eb4af6010ece49f4dc0b42c0e21f3442765a13578f2874d8e2a8a6e73f5"
    ),
    V3_OUTER_DIR / "SUMMARY.json": (
        "99346b5b041b127b35d79a0ba1e0a176335ae5c4057d3518b29b03605ca21dd5"
    ),
    DATA_GATE_DIR / "cross_venue_calendar_rr_features.parquet": (
        "fd2953bd9bc918b95079d494663cf7ca2fc9dfe141604b8e8803cc2bf605d268"
    ),
    DATA_GATE_DIR / "source_inventory.csv": (
        "b63ca25185627528b1bc22ad937dcb834dbb4846d03b451aa395a62003d4c56c"
    ),
    Path(v2.__file__).resolve(): (
        "1bdc768ca4a72d99be1394d18107750abb228024fc56555ebe4d7b13c5c89d2a"
    ),
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify_inputs() -> None:
    tracked_clean(Path(__file__).resolve(), "V4 development evaluator")
    tracked_clean(PREDECLARATION, "V4 predeclaration")
    for path, expected in INPUT_HASHES.items():
        if not path.is_file() or sha256_file(path) != expected:
            raise AssertionError(f"V4 frozen input changed: {path}")


def load_training() -> pd.DataFrame:
    frame = pd.read_parquet(V2_DIR / "development_dataset.parquet").copy()
    required = {"ticker", "trade_date", "month", "base_gross_bps", "direct_win"}
    missing = sorted(required.union(FEATURE_COLUMNS).difference(frame.columns))
    if missing:
        raise KeyError(f"V4 training dataset lacks fields: {missing}")
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    frame["trade_date"] = frame["trade_date"].map(canonical_date)
    frame["month"] = frame["trade_date"].str[:6]
    if (
        len(frame) != 1_482
        or frame.duplicated(["ticker", "trade_date"]).any()
        or set(frame["ticker"]) != set(TICKERS)
        or not frame["trade_date"].between("20230101", "20241231").all()
        or not np.isfinite(frame[list(FEATURE_COLUMNS)].to_numpy(dtype=float)).all()
        or not frame["direct_win"].isin([0, 1]).all()
        or not frame["base_gross_bps"].gt(0.0).eq(frame["direct_win"].eq(1)).all()
    ):
        raise AssertionError("V4 training identity failed")
    return frame.sort_values(["trade_date", "ticker"], kind="stable").reset_index(
        drop=True
    )


def _option_features_2025() -> pd.DataFrame:
    raw = pd.read_parquet(
        DATA_GATE_DIR / "cross_venue_calendar_rr_features.parquet",
        filters=[("year", "==", "2025")],
    )
    frame = v2._canonical_feature_view(raw, "local_feature_valid")
    frame = frame.loc[frame["trade_date"].str.startswith("2025")].copy()
    frame["signal_pressure"] = frame["calendar_rr_pressure"]
    frame["abs_signal_pressure"] = frame["signal_pressure"].abs()
    frame["front_rr_change"] = frame["front_rr_t1"] - frame["front_rr_t0"]
    frame["back_rr_change"] = frame["back_rr_t1"] - frame["back_rr_t0"]
    frame["option_spot_return_5m_bps"] = (
        np.log(frame["spot_t1"] / frame["spot_t0"]) * 10_000.0
    )
    return frame[["ticker", "trade_date", *v2.OPTION_FEATURES]].copy()


def load_development_rows() -> pd.DataFrame:
    summary = json.loads((V3_OUTER_DIR / "SUMMARY.json").read_text(encoding="utf-8"))
    if (
        summary.get("status") != "FAILED_OUTER_2025_2026_CLOSED"
        or summary.get("outer_2025_opened") is not True
        or summary.get("holdout_2026_opened") is not False
        or summary.get("production_modified") is not False
    ):
        raise AssertionError("V4 sealed 2025 outcome contract changed")
    sealed = pd.read_csv(
        V3_OUTER_DIR / "trades.csv", dtype={"trade_date": str, "month": str}
    )
    needed = {
        "ticker",
        "trade_date",
        "month",
        "signal_pressure",
        "underlying_return_bps",
        "base_gross_bps",
    }
    missing = sorted(needed.difference(sealed.columns))
    if missing:
        raise KeyError(f"V4 sealed 2025 ledger lacks fields: {missing}")
    sealed["ticker"] = sealed["ticker"].astype(str).str.upper().str.strip()
    sealed["trade_date"] = sealed["trade_date"].map(canonical_date)
    sealed["month"] = sealed["trade_date"].str[:6]
    sealed["sensor_ticker"] = sealed["ticker"].map(SENSOR_MAP)
    features = _option_features_2025().rename(columns={"ticker": "sensor_ticker"})
    rows = sealed[
        [
            "ticker",
            "trade_date",
            "month",
            "sensor_ticker",
            "signal_pressure",
            "underlying_return_bps",
            "base_gross_bps",
        ]
    ].rename(columns={"signal_pressure": "sealed_signal_pressure"})
    rows = rows.merge(
        features,
        on=["sensor_ticker", "trade_date"],
        how="left",
        validate="many_to_one",
    )
    rows["base_side"] = np.sign(rows["signal_pressure"]).astype(np.int64)
    recomputed_gross = rows["base_side"] * rows["underlying_return_bps"]
    rows["direct_win"] = recomputed_gross.gt(0.0).astype(np.int64)
    if (
        len(rows) != 735
        or rows.duplicated(["ticker", "trade_date"]).any()
        or set(rows["ticker"]) != set(TICKERS)
        or not rows["trade_date"].between("20250101", "20251231").all()
        or rows[list(v2.OPTION_FEATURES)].isna().any().any()
        or not rows["sensor_ticker"].eq(rows["ticker"].map(SENSOR_MAP)).all()
        or not rows["base_side"].isin([-1, 1]).all()
        or not np.allclose(
            rows["signal_pressure"], rows["sealed_signal_pressure"], rtol=0.0, atol=1e-12
        )
        or not np.allclose(
            recomputed_gross, rows["base_gross_bps"], rtol=0.0, atol=1e-10
        )
    ):
        raise AssertionError("V4 development 2025 identity/parity failed")
    return rows.sort_values(["trade_date", "ticker"], kind="stable").reset_index(
        drop=True
    )


def load_underlying_inventory_2025() -> pd.DataFrame:
    inventory = pd.read_csv(
        DATA_GATE_DIR / "source_inventory.csv",
        dtype={"trade_date": str, "sha256": str},
    )
    inventory["ticker"] = inventory["ticker"].astype(str).str.upper().str.strip()
    inventory["trade_date"] = inventory["trade_date"].map(canonical_date)
    selected = inventory.loc[
        inventory["kind"].astype(str).eq("underlying")
        & inventory["trade_date"].str.startswith("2025")
    ].copy()
    selected["size_bytes"] = pd.to_numeric(
        selected["size_bytes"], errors="raise"
    ).astype(np.int64)
    if selected.duplicated(["ticker", "trade_date"]).any():
        raise AssertionError("V4 2025 underlying inventory is not unique")
    return selected


def required_cash_keys(rows: pd.DataFrame) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for record in rows.itertuples(index=False):
        day = str(record.trade_date)
        keys.update({("QQQ", day), ("SPY", day)})
        if str(record.ticker) == "SPXW":
            keys.add(("SPXW", day))
    return keys


def load_cash_cache(
    rows: pd.DataFrame, inventory: pd.DataFrame, workers: int
) -> tuple[dict[tuple[str, str], dict[str, float]], pd.DataFrame]:
    needed = required_cash_keys(rows)
    selected = inventory.loc[
        inventory.apply(
            lambda row: (str(row["ticker"]), str(row["trade_date"])) in needed,
            axis=1,
        )
    ].copy()
    actual = set(zip(selected["ticker"], selected["trade_date"], strict=True))
    if actual != needed:
        raise AssertionError(f"V4 early cash coverage failed: {sorted(needed - actual)[:5]}")
    cache: dict[tuple[str, str], dict[str, float]] = {}
    audits: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(v2.read_early_cash_source, record)
            for record in selected.itertuples(index=False)
        ]
        for future in as_completed(futures):
            key, features, audit = future.result()
            cache[key] = features
            audits.append(audit)
    audit_frame = pd.DataFrame(audits).sort_values(
        ["ticker", "trade_date"], kind="stable"
    ).reset_index(drop=True)
    if (
        len(cache) != 738
        or set(cache) != needed
        or int(audit_frame["original_invalid_open_rows"].sum()) != 0
        or not audit_frame["audit_rows_read"].eq(66).all()
        or not audit_frame["model_rows_used"].eq(36).all()
    ):
        raise AssertionError("V4 early cash audit contract failed")
    return cache, audit_frame


def make_ledger(rows: pd.DataFrame, probabilities: np.ndarray) -> pd.DataFrame:
    if probabilities.shape != (len(rows),) or not np.isfinite(probabilities).all():
        raise AssertionError("V4 probability vector changed")
    ledger = rows[
        [
            "ticker",
            "trade_date",
            "month",
            "sensor_ticker",
            "signal_pressure",
            "base_side",
            "underlying_return_bps",
            "base_gross_bps",
            "direct_win",
        ]
    ].copy()
    ledger["direct_probability"] = probabilities
    ledger["orientation"] = np.where(probabilities >= 0.5, 1, -1).astype(np.int64)
    ledger["side"] = ledger["orientation"] * ledger["base_side"]
    ledger["gross_bps"] = ledger["orientation"] * ledger["base_gross_bps"]
    for cost in COSTS_BPS:
        ledger[f"net_bps_{int(cost)}bp"] = ledger["gross_bps"] - cost
    ledger["net_bps"] = ledger["net_bps_1bp"]
    return ledger.sort_values(["ticker", "trade_date"], kind="stable").reset_index(
        drop=True
    )


def profit_factor(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    gains = float(array[array > 0.0].sum())
    losses = float(-array[array < 0.0].sum())
    if losses == 0.0:
        return 1.0e12 if gains > 0.0 else 0.0
    return gains / losses


def summarize_monthly(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    months = pd.period_range("2025-01", "2025-12", freq="M").strftime("%Y%m")
    for ticker in TICKERS:
        for month in months:
            selected = ledger.loc[
                ledger["ticker"].eq(ticker) & ledger["month"].eq(month)
            ]
            net = selected["net_bps"].to_numpy(dtype=float)
            rows.append(
                {
                    "ticker": ticker,
                    "month": month,
                    "trades": int(len(net)),
                    "win_rate": float(np.mean(net > 0.0)),
                    "profit_factor": profit_factor(net),
                    "net_bps": float(net.sum()),
                    "frequency_pass": int(len(net)) > MIN_MONTH_TRADES_EXCLUSIVE,
                    "pnl_positive": bool(net.sum() > 0.0),
                }
            )
    return pd.DataFrame(rows)


def summarize_tickers(ledger: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ticker in TICKERS:
        selected = ledger.loc[ledger["ticker"].eq(ticker)]
        cells = monthly.loc[monthly["ticker"].eq(ticker)]
        net = selected["net_bps"].to_numpy(dtype=float)
        pf = profit_factor(net)
        win_rate = float(np.mean(net > 0.0))
        pnl = float(net.sum())
        minimum = int(cells["trades"].min())
        positive = int(cells["pnl_positive"].sum())
        rows.append(
            {
                "ticker": ticker,
                "trades": int(len(net)),
                "win_rate": win_rate,
                "profit_factor": pf,
                "net_bps": pnl,
                "min_month_trades": minimum,
                "positive_months": positive,
                "incremental_gate_pass": bool(
                    pf > INCREMENTAL_MIN_PF
                    and win_rate > MIN_WIN_RATE
                    and pnl > 0.0
                    and minimum > MIN_MONTH_TRADES_EXCLUSIVE
                ),
                "objective_gate_pass": bool(
                    pf > OBJECTIVE_MIN_PF
                    and win_rate > MIN_WIN_RATE
                    and minimum > MIN_MONTH_TRADES_EXCLUSIVE
                    and positive == 12
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_sensitivity(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope in (*TICKERS, "POOLED"):
        selected = ledger if scope == "POOLED" else ledger.loc[
            ledger["ticker"].eq(scope)
        ]
        for cost in COSTS_BPS:
            net = selected[f"net_bps_{int(cost)}bp"].to_numpy(dtype=float)
            rows.append(
                {
                    "scope": scope,
                    "cost_bps": cost,
                    "trades": int(len(net)),
                    "win_rate": float(np.mean(net > 0.0)),
                    "profit_factor": profit_factor(net),
                    "net_bps": float(net.sum()),
                }
            )
    return pd.DataFrame(rows)


def serialize_model(model: Any, training: pd.DataFrame) -> dict[str, Any]:
    imputer = model.named_steps["imputer"]
    scaler = model.named_steps["scaler"]
    classifier = model.named_steps["classifier"]
    return {
        "schema": "cross_venue_calendar_rr_leader_v4_model_v1",
        "train_rows": int(len(training)),
        "train_start": str(training["trade_date"].min()),
        "train_end": str(training["trade_date"].max()),
        "feature_columns": list(FEATURE_COLUMNS),
        "C": 0.1,
        "threshold": 0.5,
        "imputer_statistics": imputer.statistics_.tolist(),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "classes": classifier.classes_.tolist(),
        "coef": classifier.coef_.tolist(),
        "intercept": classifier.intercept_.tolist(),
    }


def run(output_dir: Path, workers: int) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"immutable V4 development output exists: {output_dir}")
    verify_inputs()
    training = load_training()
    development = load_development_rows()
    inventory = load_underlying_inventory_2025()
    cache, source_audit = load_cash_cache(development, inventory, workers)
    development = v2.attach_cash_features(development, cache)
    model = v2.make_model()
    model.fit(training[list(FEATURE_COLUMNS)], training["direct_win"])
    probabilities = model.predict_proba(development[list(FEATURE_COLUMNS)])[:, 1]
    ledger = make_ledger(development, probabilities)
    monthly = summarize_monthly(ledger)
    tickers = summarize_tickers(ledger, monthly)
    sensitivity = summarize_sensitivity(ledger)
    incremental = bool(tickers["incremental_gate_pass"].all())
    objective = bool(tickers["objective_gate_pass"].all())
    status = (
        "PASS_INCREMENTAL_DEVELOPMENT_2026_DATA_NOT_OPENED"
        if incremental
        else "FAILED_DEVELOPMENT_2026_CLOSED"
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}")
    if staging.exists():
        raise FileExistsError(staging)
    staging.mkdir()
    try:
        dataset_columns = [
            "ticker",
            "trade_date",
            "month",
            "sensor_ticker",
            *FEATURE_COLUMNS,
            "base_side",
            "underlying_return_bps",
            "base_gross_bps",
            "direct_win",
        ]
        development[dataset_columns].to_parquet(
            staging / "development_dataset.parquet", index=False
        )
        source_audit.to_csv(staging / "source_audit.csv", index=False)
        ledger.to_csv(staging / "trades.csv", index=False)
        monthly.to_csv(staging / "monthly_metrics.csv", index=False)
        tickers.to_csv(staging / "ticker_summary.csv", index=False)
        sensitivity.to_csv(staging / "cost_sensitivity.csv", index=False)
        (staging / "model.json").write_text(
            json.dumps(serialize_model(model, training), indent=2, allow_nan=False)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        summary_lines = [
            "# CROSS_VENUE_CALENDAR_RR_LEADER_V4 development 2025",
            "",
            f"Status: `{status}`.",
            "",
            "| Ticker | Trades | WR | PF | Net bps | Min/month | Positive months |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in tickers.itertuples(index=False):
            summary_lines.append(
                f"| {row.ticker} | {row.trades} | {row.win_rate:.6%} | "
                f"{row.profit_factor:.6f} | {row.net_bps:.3f} | "
                f"{row.min_month_trades} | {row.positive_months} |"
            )
        summary_lines.extend(
            [
                "",
                "Post-outcome development only; 2025 is not OOS evidence.",
                "2026 outcomes/features and production/live/systemd remain unopened.",
            ]
        )
        (staging / "SUMMARY.md").write_text(
            "\n".join(summary_lines) + "\n", encoding="utf-8", newline="\n"
        )
        names = (
            "development_dataset.parquet",
            "source_audit.csv",
            "trades.csv",
            "monthly_metrics.csv",
            "ticker_summary.csv",
            "cost_sensitivity.csv",
            "model.json",
            "SUMMARY.md",
        )
        summary = {
            "schema": "cross_venue_calendar_rr_leader_v4_development_2025_v1",
            "status": status,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "execution_commit": current_git_commit(),
            "mapping": SENSOR_MAP,
            "training_rows": int(len(training)),
            "development_rows": int(len(development)),
            "early_cash_sources_rehashed": int(len(source_audit)),
            "source_mismatches": 0,
            "per_ticker": tickers.to_dict(orient="records"),
            "incremental_gate_pass": incremental,
            "objective_gate_pass": objective,
            "advance_to_2026_data_gate": incremental,
            "development_2025_post_outcome": True,
            "features_2026_opened": False,
            "outcomes_2026_opened": False,
            "production_modified": False,
            "live_or_systemd_modified": False,
            "input_sha256": {
                str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): expected
                for path, expected in INPUT_HASHES.items()
            },
            "output_sha256": {name: sha256_file(staging / name) for name in names},
            "dataset_recomputed_sha256": dataframe_digest(
                development[dataset_columns]
            ),
            "trades_recomputed_sha256": dataframe_digest(ledger),
            "monthly_recomputed_sha256": dataframe_digest(monthly),
            "ticker_summary_recomputed_sha256": dataframe_digest(tickers),
            "cost_sensitivity_recomputed_sha256": dataframe_digest(sensitivity),
        }
        (staging / "SUMMARY.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 1 <= args.workers <= 16:
        raise ValueError("workers must be in [1, 16]")
    summary = run(args.output_dir.resolve(), args.workers)
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
