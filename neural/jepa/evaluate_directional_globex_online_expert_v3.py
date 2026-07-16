#!/usr/bin/env python3
"""Causal Hedge ensemble of paired momentum/reversion cash-Globex experts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from neural.jepa import evaluate_directional_breadth_transmission_v1 as panel
from neural.jepa import evaluate_directional_globex_cross_asset_v1 as v1
from neural.jepa import evaluate_directional_globex_online_linear_v2 as v2
from neural.jepa import evaluate_directional_semantic_jepa_v1 as base


PREDECLARATION = (
    base.REPO_ROOT
    / "research_papers/JEPA/DIRECTIONAL_GLOBEX_ONLINE_EXPERT_V3_PREDECLARATION.md"
)
DEFAULT_DEVELOPMENT_OUTPUT = (
    base.REPO_ROOT / "research_papers/JEPA/results/_diagnostics/"
    "directional_globex_online_expert_v3_development_202407_202512"
)
DEFAULT_EVALUATION_OUTPUT = (
    base.REPO_ROOT / "research_papers/JEPA/results/_diagnostics/"
    "directional_globex_online_expert_v3_evaluation_202601_20260715"
)
PROFILES = {
    "ONLINE_EXPERT_HEDGE21": 21,
    "ONLINE_EXPERT_HEDGE42": 42,
    "ONLINE_EXPERT_HEDGE63": 63,
}
CASH_SIGNALS = (
    "target_ret_1m",
    "target_ret_5m",
    "target_ret_15m",
    "target_ret_30m",
    "target_ret_since_open",
    "target_previous_return",
)
FUTURE_SIGNALS = (
    "ret_1h",
    "ret_3h",
    "ret_6h",
    "overnight_return",
    "asia_return",
    "europe_return",
    "premarket_return",
)
MATCHED_PREFIX = v2.MATCHED_PREFIX
EXPERT_COUNT = 28
COST_BPS = 1.0


def base_signal_names(ticker: str) -> list[str]:
    prefix = MATCHED_PREFIX[ticker]
    names = ["always_long", *CASH_SIGNALS]
    names.extend(f"{prefix}_{suffix}" for suffix in FUTURE_SIGNALS)
    if len(names) != 14 or len(names) != len(set(names)):
        raise AssertionError("V3 base expert contract changed")
    return names


def expert_signals(frame: pd.DataFrame, ticker: str) -> np.ndarray:
    columns = base_signal_names(ticker)
    raw = np.ones((len(frame), len(columns)), dtype=np.float64)
    raw[:, 1:] = frame[columns[1:]].to_numpy(dtype=np.float64)
    base_sign = np.where(raw >= 0.0, 1.0, -1.0)
    output = np.concatenate((base_sign, -base_sign), axis=1)
    if output.shape != (len(frame), EXPERT_COUNT):
        raise AssertionError("V3 expert matrix shape changed")
    return output


def hedge_probability(
    history: pd.DataFrame, current: pd.DataFrame, ticker: str
) -> float:
    memory = len(history)
    if memory not in set(PROFILES.values()):
        raise AssertionError("V3 history length is not a frozen memory")
    historical_signals = expert_signals(history, ticker)
    returns = history["future_return_bps"].to_numpy(dtype=np.float64)
    reward = np.clip(historical_signals * returns[:, None] / 50.0, -1.0, 1.0)
    scores = reward.sum(axis=0)
    eta = math.sqrt(2.0 * math.log(EXPERT_COUNT) / memory)
    logits = eta * scores
    weights = np.exp(logits - float(logits.max()))
    weights /= weights.sum()
    current_signals = expert_signals(current, ticker)[0]
    vote = float(np.dot(weights, current_signals))
    return float(np.clip((vote + 1.0) / 2.0, 0.0, 1.0))


def prediction_row(
    row: pd.Series, probability: float, profile_id: str, training_rows: int
) -> dict:
    long = probability >= 0.5
    gross = float(row["future_return_bps"] if long else -row["future_return_bps"])
    return {
        "ticker": str(row["ticker"]),
        "source_ticker": str(row["source_ticker"]),
        "trade_date": str(row["trade_date"]),
        "month": str(row["month"]),
        "window_id": str(row["window_id"]),
        "decision_time": str(row["decision_time"]),
        "entry_time": str(row["entry_time"]),
        "exit_time": str(row["exit_time"]),
        "hold_minutes": int(row["hold_minutes"]),
        "entry_spot": float(row["entry_spot"]),
        "exit_spot": float(row["exit_spot"]),
        "future_return_bps": float(row["future_return_bps"]),
        "profile_id": profile_id,
        "training_rows": training_rows,
        "probability_up": probability,
        "side": "LONG" if long else "SHORT",
        "gross_bps": gross,
        "net_bps": gross - COST_BPS,
    }


def run_online_walkforward(
    daily: pd.DataFrame, months: list[str], selected_profile: str | None = None
) -> pd.DataFrame:
    requested = [selected_profile] if selected_profile else list(PROFILES)
    rows = []
    for ticker in sorted(daily["ticker"].unique()):
        for window_id in sorted(daily["window_id"].unique()):
            group = daily.loc[
                daily["ticker"].eq(ticker) & daily["window_id"].eq(window_id)
            ].sort_values("trade_date", kind="stable")
            for test_row in group.loc[group["month"].isin(months)].itertuples(
                index=False
            ):
                current = group.loc[group["trade_date"].eq(str(test_row.trade_date))]
                if len(current) != 1:
                    raise AssertionError(
                        "V3 expected one decision per ticker-window-date"
                    )
                available = group.loc[group["trade_date"] < str(test_row.trade_date)]
                for profile_id in requested:
                    memory = PROFILES[str(profile_id)]
                    history = available.tail(memory)
                    if len(history) != memory:
                        raise AssertionError(
                            f"{ticker} {window_id} {test_row.trade_date}: insufficient V3 history"
                        )
                    probability = hedge_probability(history, current, ticker)
                    rows.append(
                        prediction_row(
                            current.iloc[0], probability, str(profile_id), memory
                        )
                    )
    if not rows:
        raise AssertionError("V3 online walk-forward produced no trades")
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
                raise AssertionError("incomplete V3 development coverage")
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
            raise AssertionError(f"{ticker}: incomplete V3 evaluation months")
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


def common_provenance(
    cash_inventory: pd.DataFrame, futures_inventory: pd.DataFrame
) -> dict:
    return {
        "schema": "directional_globex_online_expert_v3_provenance",
        "created_at_utc": base.utc_now(),
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_sha256": base.sha256_file(__file__),
        "v1_runner_sha256": base.sha256_file(Path(v1.__file__)),
        "v2_runner_sha256": base.sha256_file(Path(v2.__file__)),
        "panel_runner_sha256": base.sha256_file(Path(panel.__file__)),
        "capture_seal_sha256": base.sha256_file(v1.CAPTURE_SEAL),
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
        raise FileExistsError(f"immutable V3 development output exists: {output}")
    daily, cash_inventory, futures_inventory, coverage = v2.prepare_daily(
        Path(args.data_root), Path(args.futures_root), base.DEVELOPMENT_END
    )
    months = [f"2025{month:02d}" for month in range(1, 13)]
    trades = run_online_walkforward(daily, months)
    selected_profile, ranking = select_global_profile(trades)
    gate = development_gate(trades, selected_profile)
    monthly = monthly_metrics(trades)
    metrics = {
        "schema": "directional_globex_online_expert_v3_development_metrics",
        "status": "PASS_DEVELOPMENT_SELECTION"
        if gate["advance_to_2026"]
        else "CLOSED_DEVELOPMENT_GATE",
        "created_at_utc": base.utc_now(),
        "scope": {"start_date": "20240717", "end_date": base.DEVELOPMENT_END},
        "selected_profile": selected_profile,
        "expert_count": EXPERT_COUNT,
        "coverage": coverage,
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
        json.dumps(
            {ticker: base_signal_names(ticker) for ticker in MATCHED_PREFIX}, indent=2
        ),
        encoding="utf-8",
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


def load_development(development_dir: Path) -> tuple[dict, dict]:
    metrics = json.loads((development_dir / "metrics.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (development_dir / "provenance.json").read_text(encoding="utf-8")
    )
    if metrics.get("status") != "PASS_DEVELOPMENT_SELECTION" or not metrics.get(
        "advance_to_2026"
    ):
        raise AssertionError("V3 development did not authorize evaluation")
    checks = {
        "predeclaration_sha256": base.sha256_file(PREDECLARATION),
        "runner_sha256": base.sha256_file(__file__),
        "v1_runner_sha256": base.sha256_file(Path(v1.__file__)),
        "v2_runner_sha256": base.sha256_file(Path(v2.__file__)),
        "panel_runner_sha256": base.sha256_file(Path(panel.__file__)),
        "capture_seal_sha256": base.sha256_file(v1.CAPTURE_SEAL),
    }
    for key, expected in checks.items():
        if provenance.get(key) != expected:
            raise AssertionError(f"V3 frozen provenance changed: {key}")
    return metrics, provenance


def run_evaluation(args: argparse.Namespace) -> dict:
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable V3 evaluation output exists: {output}")
    development_dir = Path(args.development_dir)
    development, frozen_provenance = load_development(development_dir)
    daily, cash_inventory, futures_inventory, coverage = v2.prepare_daily(
        Path(args.data_root), Path(args.futures_root), base.EVALUATION_END
    )
    v2.verify_development_cash(cash_inventory, development_dir, frozen_provenance)
    months = [f"2026{month:02d}" for month in range(1, 8)]
    trades = run_online_walkforward(
        daily, months, selected_profile=str(development["selected_profile"])
    )
    gate = evaluation_gate(trades, months)
    monthly = monthly_metrics(trades)
    metrics = {
        "schema": "directional_globex_online_expert_v3_evaluation_metrics",
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
