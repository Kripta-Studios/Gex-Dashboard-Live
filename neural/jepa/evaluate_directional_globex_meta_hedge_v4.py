#!/usr/bin/env python3
"""Online causal meta-Hedge over the frozen V1/V2/V3 directional policies."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_breadth_transmission_v1 as panel
from neural.jepa import evaluate_directional_globex_cross_asset_v1 as v1
from neural.jepa import evaluate_directional_globex_online_expert_v3 as v3
from neural.jepa import evaluate_directional_globex_online_linear_v2 as v2
from neural.jepa import evaluate_directional_semantic_jepa_v1 as base


PREDECLARATION = (
    base.REPO_ROOT
    / "research_papers/JEPA/DIRECTIONAL_GLOBEX_META_HEDGE_V4_PREDECLARATION.md"
)
V1_DEVELOPMENT = v1.DEFAULT_DEVELOPMENT_OUTPUT
V2_DEVELOPMENT = v2.DEFAULT_DEVELOPMENT_OUTPUT
V3_DEVELOPMENT = v3.DEFAULT_DEVELOPMENT_OUTPUT
DEFAULT_DEVELOPMENT_OUTPUT = (
    base.REPO_ROOT / "research_papers/JEPA/results/_diagnostics/"
    "directional_globex_meta_hedge_v4_development_202407_202512"
)
DEFAULT_EVALUATION_OUTPUT = (
    base.REPO_ROOT / "research_papers/JEPA/results/_diagnostics/"
    "directional_globex_meta_hedge_v4_evaluation_202601_20260715"
)
PROFILES = {
    "META_HEDGE21": 21,
    "META_HEDGE42": 42,
    "META_HEDGE63": 63,
}
COMPONENT_PROFILES = {
    "v1": v1.SELECTABLE_PROFILES,
    "v2": tuple(v2.PROFILES),
    "v3": tuple(v3.PROFILES),
}
KEYS = ("ticker", "trade_date", "window_id")
META_COLUMNS = (
    "ticker",
    "source_ticker",
    "trade_date",
    "month",
    "window_id",
    "decision_time",
    "entry_time",
    "exit_time",
    "hold_minutes",
    "entry_spot",
    "exit_spot",
    "future_return_bps",
)
COST_BPS = 1.0
EXPERT_COUNT = 18


def _component_pivot(trades: pd.DataFrame, source: str) -> pd.DataFrame:
    expected = set(COMPONENT_PROFILES[source])
    if set(trades["profile_id"].unique()) != expected:
        raise AssertionError(f"{source}: component profile contract changed")
    frame = trades.copy()
    frame["signal"] = np.where(frame["side"].eq("LONG"), 1.0, -1.0)
    pivot = frame.pivot(index=list(KEYS), columns="profile_id", values="signal")
    pivot = pivot.rename(columns={name: f"{source}::{name}" for name in pivot.columns})
    return pivot.reset_index()


def build_candidate_ledger(
    v1_trades: pd.DataFrame, v2_trades: pd.DataFrame, v3_trades: pd.DataFrame
) -> tuple[pd.DataFrame, list[str]]:
    components = {"v1": v1_trades, "v2": v2_trades, "v3": v3_trades}
    base_rows = v1_trades.drop_duplicates(list(KEYS)).loc[:, META_COLUMNS].copy()
    if len(base_rows) * len(COMPONENT_PROFILES["v1"]) != len(v1_trades):
        raise AssertionError("V1 component decisions are incomplete")
    output = base_rows
    expert_names = []
    for source, trades in components.items():
        pivot = _component_pivot(trades, source)
        output = output.merge(pivot, on=list(KEYS), how="inner", validate="one_to_one")
        expert_names.extend(
            f"{source}::{profile}" for profile in COMPONENT_PROFILES[source]
        )
    if len(output) != len(base_rows):
        raise AssertionError("component decisions do not share an exact intersection")
    for source, trades in components.items():
        outcomes = trades.drop_duplicates(list(KEYS)).loc[
            :, [*KEYS, "future_return_bps"]
        ]
        checked = output.merge(
            outcomes,
            on=list(KEYS),
            how="left",
            validate="one_to_one",
            suffixes=("", f"_{source}"),
        )
        if not np.allclose(
            checked["future_return_bps"],
            checked[f"future_return_bps_{source}"],
            atol=1e-12,
        ):
            raise AssertionError(f"{source}: component outcome mismatch")
    for name in tuple(expert_names):
        inverse = f"inverse::{name}"
        output[inverse] = -output[name]
        expert_names.append(inverse)
    output["constant::LONG"] = 1.0
    output["constant::SHORT"] = -1.0
    expert_names.extend(("constant::LONG", "constant::SHORT"))
    if len(expert_names) != EXPERT_COUNT or output[expert_names].isna().any().any():
        raise AssertionError("V4 18-expert contract changed")
    return output.sort_values(list(KEYS), kind="stable").reset_index(
        drop=True
    ), expert_names


def meta_probability(
    history: pd.DataFrame, current: pd.DataFrame, expert_names: list[str]
) -> float:
    memory = len(history)
    if memory not in set(PROFILES.values()) or len(expert_names) != EXPERT_COUNT:
        raise AssertionError("V4 meta memory or expert contract changed")
    historical_signals = history[expert_names].to_numpy(dtype=np.float64)
    returns = history["future_return_bps"].to_numpy(dtype=np.float64)
    rewards = np.clip(historical_signals * returns[:, None] / 50.0, -1.0, 1.0)
    scores = rewards.sum(axis=0)
    eta = math.sqrt(2.0 * math.log(EXPERT_COUNT) / memory)
    logits = eta * scores
    weights = np.exp(logits - float(logits.max()))
    weights /= weights.sum()
    vote = float(np.dot(weights, current[expert_names].to_numpy(dtype=np.float64)[0]))
    return float(np.clip((vote + 1.0) / 2.0, 0.0, 1.0))


def prediction_row(
    row: pd.Series, probability: float, profile_id: str, training_rows: int
) -> dict:
    long = probability >= 0.5
    gross = float(row["future_return_bps"] if long else -row["future_return_bps"])
    output = {column: row[column] for column in META_COLUMNS}
    output.update(
        {
            "profile_id": profile_id,
            "training_rows": training_rows,
            "probability_up": probability,
            "side": "LONG" if long else "SHORT",
            "gross_bps": gross,
            "net_bps": gross - COST_BPS,
        }
    )
    return output


def run_meta_walkforward(
    candidates: pd.DataFrame,
    expert_names: list[str],
    months: list[str],
    selected_profile: str | None = None,
) -> pd.DataFrame:
    requested = [selected_profile] if selected_profile else list(PROFILES)
    rows = []
    for ticker in sorted(candidates["ticker"].unique()):
        for window_id in sorted(candidates["window_id"].unique()):
            group = candidates.loc[
                candidates["ticker"].eq(ticker) & candidates["window_id"].eq(window_id)
            ].sort_values("trade_date", kind="stable")
            tests = group.loc[group["month"].isin(months)]
            for test_row in tests.itertuples(index=False):
                current = group.loc[group["trade_date"].eq(str(test_row.trade_date))]
                if len(current) != 1:
                    raise AssertionError(
                        "V4 expected one decision per ticker-window-date"
                    )
                available = group.loc[group["trade_date"] < str(test_row.trade_date)]
                for profile_id in requested:
                    memory = PROFILES[str(profile_id)]
                    history = available.tail(memory)
                    if len(history) != memory:
                        raise AssertionError(
                            f"{ticker} {window_id} {test_row.trade_date}: insufficient V4 history"
                        )
                    probability = meta_probability(history, current, expert_names)
                    rows.append(
                        prediction_row(
                            current.iloc[0], probability, str(profile_id), memory
                        )
                    )
    if not rows:
        raise AssertionError("V4 meta walk-forward produced no trades")
    return (
        pd.DataFrame(rows)
        .sort_values(["ticker", "trade_date", "window_id", "profile_id"], kind="stable")
        .reset_index(drop=True)
    )


def monthly_metrics(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ticker, profile_id, month), group in trades.groupby(
        ["ticker", "profile_id", "month"], sort=True
    ):
        rows.append(
            {
                "ticker": ticker,
                "profile_id": profile_id,
                "month": month,
                **base.summarize_trades(group),
            }
        )
    return pd.DataFrame(rows)


def select_global_profile(trades: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    monthly = monthly_metrics(trades)
    rows = []
    for profile_id in PROFILES:
        by_ticker = []
        for ticker in sorted(trades["ticker"].unique()):
            ticker_monthly = monthly.loc[
                monthly["ticker"].eq(ticker) & monthly["profile_id"].eq(profile_id)
            ]
            ticker_trades = trades.loc[
                trades["ticker"].eq(ticker) & trades["profile_id"].eq(profile_id)
            ]
            if len(ticker_monthly) != 12 or int(ticker_monthly["trades"].min()) <= 12:
                raise AssertionError("incomplete V4 development coverage")
            by_ticker.append(
                {
                    "positive_months": int((ticker_monthly["net_bps"] > 0.0).sum()),
                    "profit_factor": base.profit_factor(ticker_trades["net_bps"]),
                    "monthly_q25": float(ticker_monthly["net_bps"].quantile(0.25)),
                }
            )
        rows.append(
            {
                "profile_id": profile_id,
                "worst_positive_months": min(
                    item["positive_months"] for item in by_ticker
                ),
                "total_positive_months": sum(
                    item["positive_months"] for item in by_ticker
                ),
                "worst_profit_factor": min(item["profit_factor"] for item in by_ticker),
                "worst_monthly_q25": min(item["monthly_q25"] for item in by_ticker),
            }
        )
    ranking = (
        pd.DataFrame(rows)
        .sort_values(
            [
                "worst_positive_months",
                "total_positive_months",
                "worst_profit_factor",
                "worst_monthly_q25",
                "profile_id",
            ],
            ascending=[False, False, False, False, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )
    ranking["rank"] = np.arange(1, len(ranking) + 1)
    ranking["selected"] = ranking["rank"].eq(1)
    return str(ranking.iloc[0]["profile_id"]), ranking


def development_gate(trades: pd.DataFrame, selected_profile: str) -> dict:
    selected = trades.loc[trades["profile_id"].eq(selected_profile)]
    monthly = monthly_metrics(selected)
    ticker_metrics = {}
    for ticker in sorted(selected["ticker"].unique()):
        ticker_trades = selected.loc[selected["ticker"].eq(ticker)]
        ticker_monthly = monthly.loc[monthly["ticker"].eq(ticker)]
        summary = base.summarize_trades(ticker_trades)
        positive = int((ticker_monthly["net_bps"] > 0.0).sum())
        minimum = int(ticker_monthly["trades"].min())
        passed = (
            summary["profit_factor"] > 1.10
            and summary["win_rate"] > 0.45
            and positive >= 8
            and minimum > 12
        )
        ticker_metrics[ticker] = {
            **summary,
            "positive_months": positive,
            "min_month_trades": minimum,
            "gate_pass": passed,
        }
    return {
        "ticker_metrics": ticker_metrics,
        "advance_to_2026": all(item["gate_pass"] for item in ticker_metrics.values()),
    }


def evaluation_gate(trades: pd.DataFrame, months: list[str]) -> dict:
    monthly = monthly_metrics(trades)
    ticker_metrics = {}
    for ticker in sorted(trades["ticker"].unique()):
        ticker_trades = trades.loc[trades["ticker"].eq(ticker)]
        ticker_monthly = monthly.loc[monthly["ticker"].eq(ticker)]
        if sorted(ticker_monthly["month"].tolist()) != months:
            raise AssertionError(f"{ticker}: incomplete V4 evaluation months")
        summary = base.summarize_trades(ticker_trades)
        positive = int((ticker_monthly["net_bps"] > 0.0).sum())
        minimum = int(ticker_monthly["trades"].min())
        passed = (
            summary["profit_factor"] > 1.20
            and summary["win_rate"] > 0.45
            and positive == len(months)
            and minimum > 12
        )
        ticker_metrics[ticker] = {
            **summary,
            "positive_months": positive,
            "evaluated_months": len(months),
            "min_month_trades": minimum,
            "gate_pass": passed,
        }
    return {
        "ticker_metrics": ticker_metrics,
        "joint_gate_pass": all(item["gate_pass"] for item in ticker_metrics.values()),
    }


def load_component_development() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    paths = {
        "v1": V1_DEVELOPMENT / "development_trade_ledger.parquet",
        "v2": V2_DEVELOPMENT / "development_trade_ledger.parquet",
        "v3": V3_DEVELOPMENT / "development_trade_ledger.parquet",
    }
    if not all(path.exists() for path in paths.values()):
        raise FileNotFoundError("missing frozen component development ledger")
    return tuple(pd.read_parquet(paths[name]) for name in ("v1", "v2", "v3"))


def common_provenance(
    cash_inventory: pd.DataFrame, futures_inventory: pd.DataFrame
) -> dict:
    component_files = {
        "v1_ledger": V1_DEVELOPMENT / "development_trade_ledger.parquet",
        "v2_ledger": V2_DEVELOPMENT / "development_trade_ledger.parquet",
        "v3_ledger": V3_DEVELOPMENT / "development_trade_ledger.parquet",
        "v1_metrics": V1_DEVELOPMENT / "metrics.json",
        "v2_metrics": V2_DEVELOPMENT / "metrics.json",
        "v3_metrics": V3_DEVELOPMENT / "metrics.json",
    }
    return {
        "schema": "directional_globex_meta_hedge_v4_provenance",
        "created_at_utc": base.utc_now(),
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_sha256": base.sha256_file(__file__),
        "v1_runner_sha256": base.sha256_file(Path(v1.__file__)),
        "v2_runner_sha256": base.sha256_file(Path(v2.__file__)),
        "v3_runner_sha256": base.sha256_file(Path(v3.__file__)),
        "panel_runner_sha256": base.sha256_file(Path(panel.__file__)),
        "capture_seal_sha256": base.sha256_file(v1.CAPTURE_SEAL),
        "component_artifact_sha256": {
            name: base.sha256_file(path) for name, path in component_files.items()
        },
        "cash_inventory_rows": int(len(cash_inventory)),
        "cash_inventory_sha256": panel.inventory_digest(cash_inventory),
        "futures_inventory": futures_inventory.to_dict("records"),
        "new_dataset_created": False,
        "adaptive_after_v1_2026": True,
        "production_modified": False,
    }


def run_development(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable V4 development output exists: {output}")
    v1_trades, v2_trades, v3_trades = load_component_development()
    candidates, expert_names = build_candidate_ledger(v1_trades, v2_trades, v3_trades)
    months = [f"2025{month:02d}" for month in range(1, 13)]
    trades = run_meta_walkforward(candidates, expert_names, months)
    selected_profile, ranking = select_global_profile(trades)
    gate = development_gate(trades, selected_profile)
    monthly = monthly_metrics(trades)
    cash_inventory = pd.read_csv(
        V1_DEVELOPMENT / "cash_source_inventory.csv", dtype={"trade_date": str}
    )
    futures_inventory = pd.read_csv(V1_DEVELOPMENT / "futures_source_inventory.csv")
    metrics = {
        "schema": "directional_globex_meta_hedge_v4_development_metrics",
        "status": "PASS_DEVELOPMENT_SELECTION"
        if gate["advance_to_2026"]
        else "CLOSED_DEVELOPMENT_GATE",
        "created_at_utc": base.utc_now(),
        "scope": {"start_date": "20240717", "end_date": base.DEVELOPMENT_END},
        "selected_profile": selected_profile,
        "expert_count": len(expert_names),
        **gate,
        "holdout_2026_used_for_selection": False,
        "adaptive_after_v1_2026": True,
        "production_modified": False,
    }
    provenance = common_provenance(cash_inventory, futures_inventory)
    output.mkdir(parents=True, exist_ok=False)
    cash_inventory.to_csv(
        output / "cash_source_inventory.csv", index=False, lineterminator="\n"
    )
    futures_inventory.to_csv(
        output / "futures_source_inventory.csv", index=False, lineterminator="\n"
    )
    trades.to_parquet(output / "development_trade_ledger.parquet", index=False)
    monthly.to_csv(output / "development_monthly_metrics.csv", index=False)
    ranking.to_csv(output / "profile_ranking.csv", index=False)
    (output / "expert_contract.json").write_text(
        json.dumps(expert_names, indent=2), encoding="utf-8"
    )
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    metrics["provenance_sha256"] = base.sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def load_development(development_dir: Path) -> tuple[dict, dict, list[str]]:
    metrics = json.loads((development_dir / "metrics.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (development_dir / "provenance.json").read_text(encoding="utf-8")
    )
    experts = json.loads(
        (development_dir / "expert_contract.json").read_text(encoding="utf-8")
    )
    if metrics.get("status") != "PASS_DEVELOPMENT_SELECTION" or not metrics.get(
        "advance_to_2026"
    ):
        raise AssertionError("V4 development did not authorize evaluation")
    checks = {
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_sha256": base.sha256_file(__file__),
        "v1_runner_sha256": base.sha256_file(Path(v1.__file__)),
        "v2_runner_sha256": base.sha256_file(Path(v2.__file__)),
        "v3_runner_sha256": base.sha256_file(Path(v3.__file__)),
        "panel_runner_sha256": base.sha256_file(Path(panel.__file__)),
        "capture_seal_sha256": base.sha256_file(v1.CAPTURE_SEAL),
    }
    for key, expected in checks.items():
        if provenance.get(key) != expected:
            raise AssertionError(f"V4 frozen provenance changed: {key}")
    if len(experts) != EXPERT_COUNT:
        raise AssertionError("V4 frozen expert count changed")
    return metrics, provenance, experts


def evaluation_component_ledgers(
    daily: pd.DataFrame, months: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cash_features = json.loads(
        (V1_DEVELOPMENT / "cash_features.json").read_text(encoding="utf-8")
    )
    futures_features = json.loads(
        (V1_DEVELOPMENT / "futures_features.json").read_text(encoding="utf-8")
    )
    v1_trades = v1.run_walkforward(daily, months, cash_features, futures_features)
    v2_trades = v2.run_online_walkforward(daily, months)
    v3_trades = v3.run_online_walkforward(daily, months)
    return v1_trades, v2_trades, v3_trades


def run_evaluation(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable V4 evaluation output exists: {output}")
    development_dir = Path(args.development_dir)
    development, frozen_provenance, frozen_experts = load_development(development_dir)
    daily, cash_inventory, futures_inventory, coverage = v2.prepare_daily(
        Path(args.data_root), Path(args.futures_root), base.EVALUATION_END
    )
    v2.verify_development_cash(cash_inventory, development_dir, frozen_provenance)
    months = [f"2026{month:02d}" for month in range(1, 8)]
    current_components = evaluation_component_ledgers(daily, months)
    current_candidates, observed_experts = build_candidate_ledger(*current_components)
    if observed_experts != frozen_experts:
        raise AssertionError("V4 evaluation expert order changed")
    development_components = load_component_development()
    history_candidates, history_experts = build_candidate_ledger(
        *development_components
    )
    if history_experts != frozen_experts:
        raise AssertionError("V4 development expert order changed")
    candidates = pd.concat((history_candidates, current_candidates), ignore_index=True)
    if candidates.duplicated(list(KEYS)).any():
        raise AssertionError("V4 history/evaluation candidate overlap")
    trades = run_meta_walkforward(
        candidates,
        frozen_experts,
        months,
        selected_profile=str(development["selected_profile"]),
    )
    gate = evaluation_gate(trades, months)
    monthly = monthly_metrics(trades)
    metrics = {
        "schema": "directional_globex_meta_hedge_v4_evaluation_metrics",
        "status": "PASS_2026_JUL_GATE"
        if gate["joint_gate_pass"]
        else "CLOSED_2026_JUL_GATE",
        "created_at_utc": base.utc_now(),
        "scope": {
            "start_date": "20260101",
            "end_date": base.EVALUATION_END,
            "months": months,
            "july_status": "MTD_THROUGH_20260715",
        },
        "selected_profile": development["selected_profile"],
        "coverage": coverage,
        **gate,
        "adaptive_after_v1_2026": True,
        "production_modified": False,
    }
    provenance = common_provenance(cash_inventory, futures_inventory)
    provenance.update(
        {
            "development_metrics_sha256": base.sha256_file(
                development_dir / "metrics.json"
            ),
            "development_provenance_sha256": base.sha256_file(
                development_dir / "provenance.json"
            ),
        }
    )
    output.mkdir(parents=True, exist_ok=False)
    trades.to_parquet(output / "trade_ledger.parquet", index=False)
    monthly.to_csv(output / "monthly_metrics.csv", index=False)
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    metrics["provenance_sha256"] = base.sha256_file(output / "provenance.json")
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2, sort_keys=True), flush=True)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("development", "evaluation"), required=True)
    parser.add_argument("--data-root", default=str(base.DEFAULT_DATA_ROOT))
    parser.add_argument("--futures-root", default=str(v1.DEFAULT_FUTURES_ROOT))
    parser.add_argument("--development-dir", default=str(DEFAULT_DEVELOPMENT_OUTPUT))
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    if not args.output:
        args.output = str(
            DEFAULT_DEVELOPMENT_OUTPUT
            if args.phase == "development"
            else DEFAULT_EVALUATION_OUTPUT
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
