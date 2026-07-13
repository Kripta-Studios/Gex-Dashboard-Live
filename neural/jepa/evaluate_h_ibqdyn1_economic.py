"""One-shot executable-quote economic translation for a passed H-IBQDYN1."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from neural.jepa import evaluate_wall_quote_size_pressure_at_touch_v1 as shared
from neural.jepa.build_h_ibqdyn1_feasibility import (
    EXPECTED_SOURCE_SHA256,
    load_opportunity_universe,
)
from neural.jepa.build_wall_quote_tick_dynamics_sidecar import sha256_file
from neural.jepa.evaluate_h_ibqdyn1_physical import (
    ALPHA_FIELDS,
    EXPECTED_EVENTS,
    PROJECT_ROOT,
    _shared_contract,
)

PREDECLARATION = (
    "research_papers/JEPA/H_IBQDYN1_ECONOMIC_TRANSLATION_PREDECLARATION.md"
)
BUCKETS = {"SPXW": 25, "QQQ": 35, "SPY": 35}
CAPS = {"SPXW": 4, "QQQ": 2, "SPY": 1}
COOLDOWNS = {"SPXW": 0, "QQQ": 30, "SPY": 0}
RISK_CAPITAL = 5_000.0
OUTER_YEARS = ("2024", "2025")
GATES = {
    "minimum_profit_factor": 1.30,
    "minimum_win_rate": 0.50,
    "minimum_month_trades": 18,
    "minimum_hold_minutes": 30,
    "positive_pnl_every_month": True,
}
CODE_CLOSURE = (
    "neural/jepa/evaluate_h_ibqdyn1_economic.py",
    "neural/jepa/freeze_h_ibqdyn1_economic_runner.py",
    "neural/jepa/evaluate_h_ibqdyn1_physical.py",
    "neural/jepa/freeze_h_ibqdyn1_physical_runner.py",
    "neural/jepa/build_h_ibqdyn1_dataset.py",
    "neural/jepa/h_ibqdyn1_features.py",
    "neural/jepa/build_h_ibqdyn1_feasibility.py",
    "neural/jepa/build_event_option_dataset.py",
    "neural/jepa/evaluate_wall_quote_size_pressure_at_touch_v1.py",
    PREDECLARATION,
)


def outcome_columns() -> list[str]:
    fields = ["ticker", "trade_date", "timestamp", "option_price_mode"]
    for bucket in sorted(set(BUCKETS.values())):
        for right in ("call", "put"):
            fields.extend(
                [
                    f"{right}_d{bucket:02d}_opt_exit_ret",
                    f"{right}_d{bucket:02d}_opt_exit_minutes",
                ]
            )
    return fields


def verify_build_summary(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    args = value.get("args", {})
    expected = {
        "start_minute": 630,
        "end_minute": 870,
        "near_level_only": True,
        "near_level_bps": 20.0,
        "horizon_minutes": 180,
        "option_tp_pct": 10.0,
        "option_sl_pct": 0.6,
        "option_price_mode": "executable_quote",
        "option_exit_mode": "trailing",
        "option_min_hold_minutes": 30,
        "option_trail_activation_pct": 0.5,
        "option_trail_drawdown_pct": 0.25,
        "require_open_interest": True,
    }
    invalid = [name for name, expected_value in expected.items() if args.get(name) != expected_value]
    if invalid:
        raise AssertionError(f"executable event build contract mismatch: {invalid}")
    return value


def load_outcomes(events_path: Path, features: pd.DataFrame) -> pd.DataFrame:
    if sha256_file(events_path) != EXPECTED_SOURCE_SHA256:
        raise AssertionError("H-IBQDYN1 executable outcome source hash mismatch")
    identity = load_opportunity_universe(events_path)[
        ["event_id", "ticker", "trade_date", "decision_dt"]
    ].copy()
    source = pd.read_parquet(events_path, columns=outcome_columns())
    source["ticker"] = source["ticker"].astype(str).str.upper()
    source["trade_date"] = source["trade_date"].astype(str).str.replace(r"\D", "", regex=True).str[:8]
    source["decision_dt"] = pd.to_datetime(source.pop("timestamp"), errors="coerce")
    keys = ["ticker", "trade_date", "decision_dt"]
    if source["decision_dt"].isna().any() or source.duplicated(keys).any():
        raise AssertionError("ambiguous executable outcome decision keys")
    source = identity.merge(source, on=keys, how="left", validate="one_to_one")
    joined = features.merge(source.drop(columns=keys), on="event_id", how="left", validate="one_to_one")
    if (
        len(joined) != len(features)
        or joined["event_id"].duplicated().any()
        or not joined["option_price_mode"].astype(str).eq("executable_quote").all()
        or joined["trade_date"].astype(str).str.startswith("2026").any()
    ):
        raise AssertionError("H-IBQDYN1 executable outcome join changed universe")
    return joined


def score_physical_models(
    features: pd.DataFrame, physical_dir: Path, model_hashes: pd.DataFrame
) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    for year in OUTER_YEARS:
        for ticker in BUCKETS:
            cell_id = f"lr_{year}_{ticker}_60m"
            match = model_hashes[
                model_hashes["cell_id"].astype(str).eq(cell_id)
                & model_hashes["family"].astype(str).eq("lr")
                & model_hashes["arm"].astype(str).eq("F1")
            ]
            if len(match) != 1:
                raise AssertionError(f"missing exact physical LR model: {cell_id}")
            row = match.iloc[0]
            model_path = physical_dir / str(row["path"])
            if sha256_file(model_path) != str(row["sha256"]):
                raise AssertionError(f"physical LR model hash mismatch: {cell_id}")
            part = features[
                features["ticker"].astype(str).eq(ticker)
                & features["trade_date"].astype(str).str.startswith(year)
                & features["ibqdyn_both_valid"].astype(bool)
            ].copy()
            with _shared_contract():
                matrix = shared.model_frame(part, "F1")
            model = joblib.load(model_path)
            part["rejection_probability"] = model.predict_proba(matrix)[:, 1]
            role = part["wall_role"].astype(str)
            rejection = part["rejection_probability"].ge(0.5)
            part["action"] = np.where(
                role.eq("resistance"),
                np.where(rejection, "PUT", "CALL"),
                np.where(rejection, "CALL", "PUT"),
            )
            outputs.append(part)
    scored = pd.concat(outputs, ignore_index=True).sort_values(
        ["ticker", "trade_date", "decision_dt"], kind="stable"
    ).reset_index(drop=True)
    if not bool(scored["trade_date"].astype(str).str[:4].isin(OUTER_YEARS).all()):
        raise AssertionError("economic scorer escaped frozen outer years")
    return scored


def attach_selected_payoff(scored: pd.DataFrame) -> pd.DataFrame:
    out = scored.copy()
    out["realized_return"] = np.nan
    out["exit_minutes"] = np.nan
    for ticker, bucket in BUCKETS.items():
        mask = out["ticker"].astype(str).eq(ticker)
        if not bool(mask.any()):
            continue
        call = mask & out["action"].eq("CALL")
        put = mask & out["action"].eq("PUT")
        out.loc[call, "realized_return"] = pd.to_numeric(
            out.loc[call, f"call_d{bucket:02d}_opt_exit_ret"], errors="coerce"
        )
        out.loc[put, "realized_return"] = pd.to_numeric(
            out.loc[put, f"put_d{bucket:02d}_opt_exit_ret"], errors="coerce"
        )
        out.loc[call, "exit_minutes"] = pd.to_numeric(
            out.loc[call, f"call_d{bucket:02d}_opt_exit_minutes"], errors="coerce"
        )
        out.loc[put, "exit_minutes"] = pd.to_numeric(
            out.loc[put, f"put_d{bucket:02d}_opt_exit_minutes"], errors="coerce"
        )
    if (
        not np.isfinite(out[["realized_return", "exit_minutes"]].to_numpy(dtype=float)).all()
        or not out["exit_minutes"].between(30, 180).all()
    ):
        raise AssertionError("selected executable payoff is missing or violates hold contract")
    return out


def causal_replay(scored: pd.DataFrame) -> pd.DataFrame:
    trades: list[pd.Series] = []
    ordered = scored.sort_values(["ticker", "trade_date", "decision_dt"], kind="stable")
    for (ticker, day), part in ordered.groupby(["ticker", "trade_date"], sort=True):
        open_until: pd.Timestamp | None = None
        last_entry: pd.Timestamp | None = None
        count = 0
        for _, row in part.iterrows():
            entry = pd.Timestamp(row["decision_dt"])
            if count >= CAPS[str(ticker)]:
                break
            if open_until is not None and entry < open_until:
                continue
            if last_entry is not None and entry < last_entry + pd.Timedelta(minutes=COOLDOWNS[str(ticker)]):
                continue
            trades.append(row)
            count += 1
            last_entry = entry
            open_until = entry + pd.Timedelta(minutes=int(row["exit_minutes"]))
    return pd.DataFrame(trades).reset_index(drop=True)


def _metrics(frame: pd.DataFrame) -> dict[str, Any]:
    values = pd.to_numeric(frame["realized_return"], errors="coerce")
    wins = values[values > 0.0].sum()
    losses = -values[values < 0.0].sum()
    return {
        "trades": int(len(frame)),
        "win_rate": float((values > 0.0).mean()) if len(values) else 0.0,
        "profit_factor": float(wins / losses) if losses > 0.0 else (float("inf") if wins > 0.0 else 0.0),
        "pnl_r": float(values.sum()),
        "pnl_dollars": float(values.sum() * RISK_CAPITAL),
        "minimum_hold_minutes": float(pd.to_numeric(frame["exit_minutes"], errors="coerce").min()) if len(frame) else None,
    }


def summarize(trades: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    months = [f"{year}{month:02d}" for year in (2024, 2025) for month in range(1, 13)]
    rows: list[dict[str, Any]] = []
    ticker_summary: dict[str, Any] = {}
    for ticker in BUCKETS:
        part = trades[trades["ticker"].astype(str).eq(ticker)].copy()
        part["month"] = part["trade_date"].astype(str).str[:6]
        aggregate = _metrics(part)
        ticker_pass = aggregate["profit_factor"] >= 1.30 and aggregate["win_rate"] >= 0.50
        for month in months:
            metrics = _metrics(part[part["month"].eq(month)])
            passed = bool(
                metrics["trades"] >= 18
                and metrics["pnl_r"] > 0.0
                and metrics["minimum_hold_minutes"] is not None
                and metrics["minimum_hold_minutes"] >= 30.0
            )
            ticker_pass &= passed
            rows.append({"ticker": ticker, "month": month, **metrics, "passed": passed})
        ticker_summary[ticker] = {**aggregate, "passed": bool(ticker_pass)}
    summary = {
        "gate_spec": GATES,
        "ticker_summary": ticker_summary,
        "all_tickers_passed": bool(all(value["passed"] for value in ticker_summary.values())),
        "production_live_ready": False,
        "holdout_2026_used": False,
    }
    return pd.DataFrame(rows), summary


def verify_freeze(path: Path, inputs: dict[str, Path]) -> dict[str, Any]:
    freeze = json.loads(path.read_text(encoding="utf-8"))
    if freeze.get("schema") != "h_ibqdyn1_frozen_economic_runner_v1" or freeze.get("status") != "PREEXECUTION_FROZEN":
        raise AssertionError("wrong H-IBQDYN1 economic freeze")
    for name, actual in inputs.items():
        if freeze.get("inputs", {}).get(name, {}).get("sha256") != sha256_file(actual):
            raise AssertionError(f"frozen economic input mismatch: {name}")
    code = {relative: sha256_file(PROJECT_ROOT / relative) for relative in CODE_CLOSURE}
    if freeze.get("code_hashes") != code or freeze.get("policy") != {"physical_family": "lr", "physical_arm": "F1", "horizon_minutes": 60, "decision_boundary": 0.5, "scheduler": "chronological_reject_while_open"} or freeze.get("gate_spec") != GATES:
        raise AssertionError("active economic code/policy differs from freeze")
    if freeze.get("holdout_2026_opened") is not False or freeze.get("production_modified") is not False:
        raise AssertionError("economic freeze does not protect 2026/production")
    return freeze


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--event-build-summary", required=True)
    parser.add_argument("--physical-dir", required=True)
    parser.add_argument("--physical-manifest", required=True)
    parser.add_argument("--physical-summary", required=True)
    parser.add_argument("--physical-model-hashes", required=True)
    parser.add_argument("--frozen-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.output_dir)
    staging = output.with_name(output.name + ".staging")
    if output.exists() or staging.exists():
        raise FileExistsError("immutable H-IBQDYN1 economic output exists")
    inputs = {name: Path(getattr(args, name)) for name in ("dataset", "events", "event_build_summary", "physical_manifest", "physical_summary", "physical_model_hashes")}
    verify_freeze(Path(args.frozen_manifest), inputs)
    verify_build_summary(inputs["event_build_summary"])
    physical = json.loads(inputs["physical_manifest"].read_text(encoding="utf-8"))
    physical_summary = json.loads(inputs["physical_summary"].read_text(encoding="utf-8"))
    if physical.get("summary", {}).get("physical_mechanism_pass") is not True or physical_summary.get("physical_mechanism_pass") is not True or physical_summary.get("research_payoff_authorized") is not True:
        raise AssertionError("H-IBQDYN1 physical gate did not authorize payoff")
    features = pd.read_parquet(inputs["dataset"])
    if len(features) != EXPECTED_EVENTS or features["trade_date"].astype(str).str.startswith("2026").any() or not np.isfinite(features.loc[features["ibqdyn_both_valid"].astype(bool), list(ALPHA_FIELDS)].to_numpy(dtype=float)).all():
        raise AssertionError("economic feature input changed")
    model_hashes = pd.read_csv(inputs["physical_model_hashes"])
    scored = score_physical_models(features, Path(args.physical_dir), model_hashes)
    # First option-payoff access occurs only after every frozen/physical check.
    joined = load_outcomes(inputs["events"], scored)
    selected = attach_selected_payoff(joined)
    trades = causal_replay(selected)
    monthly, summary = summarize(trades)
    staging.mkdir(parents=True, exist_ok=False)
    trade_path = staging / "trades.parquet"
    score_path = staging / "scores.parquet"
    monthly_path = staging / "monthly.csv"
    summary_path = staging / "summary.json"
    selected.to_parquet(score_path, index=False)
    trades.to_parquet(trade_path, index=False)
    monthly.to_csv(monthly_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    manifest = {"schema": "h_ibqdyn1_economic_evaluation_v1", "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True, capture_output=True, text=True).stdout.strip(), "frozen_manifest_sha256": sha256_file(args.frozen_manifest), "artifact_hashes": {"scores": sha256_file(score_path), "trades": sha256_file(trade_path), "monthly": sha256_file(monthly_path), "summary": sha256_file(summary_path)}, "summary": summary, "holdout_2026_used": False, "production_modified": False}
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    staging.rename(output)
    print(json.dumps(manifest, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
