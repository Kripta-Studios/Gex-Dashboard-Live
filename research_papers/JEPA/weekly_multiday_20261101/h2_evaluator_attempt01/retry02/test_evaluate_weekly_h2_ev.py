from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("weekly_h2_eval", HERE / "evaluate_weekly_h2_ev.py")
assert SPEC and SPEC.loader
ev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ev)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature_dict(ticker: str, right: str, ask: float = 1.0, optional_null: bool = False) -> dict[str, float | None]:
    spot, strike, bid = 500.0, 505.0, ask - 0.1
    values: dict[str, float | None] = {
        "ticker_SPY": float(ticker == "SPY"),
        "ticker_QQQ": float(ticker == "QQQ"),
        "ticker_SPXW": float(ticker == "SPXW"),
        "right_call": float(right == "CALL"),
        "dte": 7.0,
        "weekday": 1.0,
        "spot": spot,
        "strike": strike,
        "moneyness": strike / spot - 1,
        "bid": bid,
        "ask": ask,
        "spread_relative": (ask - bid) / ask,
        "delta": 0.5 if right == "CALL" else -0.5,
        "implied_vol": None if optional_null else 0.2,
        "gamma": None if optional_null else 0.01,
        "theta": None if optional_null else -0.05,
        "vega": None if optional_null else 0.1,
        "rho": None if optional_null else 0.01,
    }
    assert tuple(values) == ev.FEATURES
    return values


def candidate(
    entry: str,
    exit_date: str,
    expiration: str,
    ticker: str,
    right: str,
    scenario: int,
    *,
    missing: str | None = None,
    optional_null: bool = False,
) -> dict:
    decision_ask = 1.0
    base = {
        "candidate_id": f"{ticker}:{entry}:{expiration}:{right}",
        "ticker": ticker,
        "entry_date": entry,
        "exit_date": exit_date,
        "expiration": expiration,
        "strike": 505.0,
        "right": right,
        "features": feature_dict(ticker, right, decision_ask, optional_null),
        "decision_ask": decision_ask,
        "source_pins": {
            "calendar_sha256": ev.CALENDAR_SHA256,
            "entry_path": f"D:/synthetic/{entry}.parquet",
            "entry_sha256": "1" * 64,
            "exit_path": f"D:/synthetic/{exit_date}.parquet",
            "exit_sha256": None if missing == "MISSING_EXIT_SOURCE" else "2" * 64,
            "clock_basis_entry": "NATIVE_STORED_TIMESTAMP",
            "clock_basis_exit": None if missing else "NATIVE_STORED_TIMESTAMP",
        },
    }
    offset = "-05:00"
    if scenario == 0:
        return {
            **base,
            "entry_ask": None,
            "exit_bid": None,
            "status": "NO_FILL",
            "label_available_at": f"{entry[:4]}-{entry[4:6]}-{entry[6:]}T10:35:00{offset}",
            "scenario": 0,
            "net_base": 0.0,
            "net_adverse": 0.0,
            "entry_debit_base": 0.0,
            "entry_debit_adverse": 0.0,
            "payoff_is_lower_bound": False,
        }
    entry_ask = 1.0
    bids = {1: 0.5, 2: 0.8, 3: 1.1, 4: 1.4}
    exit_bid = None if missing else bids[scenario]
    accounting_bid = 0.0 if exit_bid is None else exit_bid
    return {
        **base,
        "entry_ask": entry_ask,
        "exit_bid": exit_bid,
        "status": missing or "OBSERVED_EXIT",
        "label_available_at": f"{exit_date[:4]}-{exit_date[4:6]}-{exit_date[6:]}T10:35:00{offset}",
        "scenario": 1 if missing else scenario,
        "net_base": ev.net_usd(entry_ask, accounting_bid, 0.01),
        "net_adverse": ev.net_usd(entry_ask, accounting_bid, 0.02),
        "entry_debit_base": ev.entry_debit(entry_ask, 0.01),
        "entry_debit_adverse": ev.entry_debit(entry_ask, 0.02),
        "payoff_is_lower_bound": bool(missing),
    }


def write_dataset(root: Path, rows: list[dict]) -> tuple[Path, Path, Path]:
    candidates_path = root / "candidates.jsonl"
    candidates_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    groups: dict[tuple[str, str], list[str]] = {}
    all_dates = set()
    for row in rows:
        groups.setdefault((row["ticker"], row["entry_date"]), []).append(row["candidate_id"])
        all_dates.update((row["entry_date"], row["exit_date"]))
    coverage_rows = []
    for day in sorted(all_dates):
        for ticker in ev.TICKERS:
            ids = groups.get((ticker, day), [])
            coverage_rows.append({
                "ticker": ticker,
                "entry_date": day,
                "exit_date": None,
                "expiration": None,
                "status": "OFFICIAL_SESSION",
                "reason": "OFFERS" if ids else "NO_SERIES",
                "candidate_ids": ids,
                "source_paths": [],
            })
    coverage_path = root / "coverage.json"
    coverage = {"schema": "weekly_h2_coverage_v1", "rows": coverage_rows}
    coverage_path.write_text(json.dumps(coverage), encoding="utf-8")
    manifest = {
        "schema": "weekly_h2_dataset_manifest_v1",
        "status": "COMPLETE_WEEKLY_H2_DATASET_NOT_EVALUATED",
        "calendar": {"path": "synthetic/index.parquet", "sha256": ev.CALENDAR_SHA256},
        "files": {
            "candidates.jsonl": {"bytes": candidates_path.stat().st_size, "sha256": sha(candidates_path), "rows": len(rows)},
            "coverage.json": {"bytes": coverage_path.stat().st_size, "sha256": sha(coverage_path), "rows": len(coverage_rows)},
        },
        "flags": {"fit_performed": False, "economic_evaluation_performed": False, "promotion_approved": False},
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return candidates_path, coverage_path, manifest_path


def synthetic_rows() -> list[dict]:
    specs = [
        ("20230103", "20230105", "20230110", 0),
        ("20230403", "20230405", "20230410", 1),
        ("20240103", "20240105", "20240110", 3),
        ("20240403", "20240405", "20240410", 4),
        ("20250103", "20250107", "20250110", 1),
        ("20250403", "20250407", "20250410", 3),
        ("20260105", "20260107", "20260112", 2),
        ("20260403", "20260407", "20260410", 4),
    ]
    rows = []
    for index, (entry, exit_date, expiration, scenario) in enumerate(specs):
        rows.append(candidate(entry, exit_date, expiration, "SPY", "CALL", scenario, optional_null=True))
        rows.append(candidate(entry, exit_date, expiration, "SPY", "PUT", (scenario + 1) % 5))
        if index == 1:
            rows[-1] = candidate(entry, exit_date, expiration, "SPY", "PUT", 1, missing="MISSING_EXIT_QUOTE", optional_null=True)
    return rows


def test_amended_missing_exit_is_class_one_lower_bound_and_train_eligible() -> None:
    raw = candidate("20230403", "20230405", "20230410", "SPY", "CALL", 1, missing="MISSING_EXIT_SOURCE")
    row = ev.validate_candidate(raw)
    split = ev.split_rows([row])
    assert row["scenario"] == 1 and row["payoff_is_lower_bound"] is True
    assert row["_model_label_eligible"] is True and split["TRAIN"] == [row]
    assert row["net_adverse"] < -100


def test_stable_train_transformer_keeps_all_missing_feature_dimensions() -> None:
    matrix = np.asarray([
        list(feature_dict("SPY", "CALL", optional_null=True).values()),
        list(feature_dict("QQQ", "PUT", optional_null=True).values()),
    ], dtype=float)
    transformer = ev.StableTrainTransformer().fit(matrix)
    transformed = transformer.transform(matrix)
    assert transformed.shape == (2, 36)
    assert transformer.as_dict()["medians"][-5:] == [0.0] * 5


def test_label_availability_purges_cross_cutoff() -> None:
    raw = candidate("20241230", "20250102", "20250106", "SPY", "CALL", 1)
    row = ev.validate_candidate(raw)
    ev.split_rows([row])
    assert row["_split"] == "TRAIN"
    assert row["_model_label_eligible"] is False


def test_top1_requires_strict_positive_and_exact_tie_wait() -> None:
    call = {"right": "CALL", "_ev_adverse": 2.0}
    put = {"right": "PUT", "_ev_adverse": 2.0}
    assert ev.select_candidate([call, put], "EV_TOP1_H2") == (None, "EV_TIE_WAIT")
    put["_ev_adverse"] = 1.0
    assert ev.select_candidate([call, put], "EV_TOP1_H2")[0] is call
    call["_ev_adverse"] = put["_ev_adverse"] = 0.0
    assert ev.select_candidate([call, put], "EV_TOP1_H2") == (None, "EV_NOT_POSITIVE")


def test_full_synthetic_run_outputs_pins_ledgers_and_conservative_metrics(tmp_path: Path) -> None:
    paths = write_dataset(tmp_path, synthetic_rows())
    output = tmp_path / "evaluation"
    summary = ev.run(*paths, output)
    assert summary["development_seen"] is True and summary["promotion_approved"] is False
    assert summary["label_support"]["TRAIN"]["lower_bound"] == 1
    assert summary["probability_metrics_conservative"]["TRAIN"]["n"] == 8
    assert summary["probability_metrics_observed_only"]["TRAIN"]["n"] == 7
    calibration = json.loads((output / "calibration_grid.json").read_text(encoding="utf-8"))
    assert len(calibration["scores"]) == 11
    model = json.loads((output / "model.json").read_text(encoding="utf-8"))
    assert model["C"] == 1.0 and model["max_iter"] == 2000 and model["random_state"] == 0
    assert model["sklearn_version"] == "1.8.0"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["implementation_pins"]) == {"evaluate_weekly_h2_ev.py", "ECONOMIC_H2_CONTRACT.md"}
    assert (output / "ledger_ev_top1_h2.jsonl").is_file()
    assert summary["economics"]["ALWAYS_CALL_H2"]["EVAL"]["pooled"]["trades"] >= 1
    with pytest.raises(ev.EvaluationError, match="output already exists"):
        ev.run(*paths, output)


def test_manifest_hash_mismatch_fails_before_output(tmp_path: Path) -> None:
    candidates_path, coverage_path, manifest_path = write_dataset(tmp_path, synthetic_rows())
    candidates_path.write_text(candidates_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    output = tmp_path / "never_created"
    with pytest.raises(ev.EvaluationError, match="manifest hash mismatch"):
        ev.run(candidates_path, coverage_path, manifest_path, output)
    assert not output.exists()


def test_replay_exits_before_same_day_reentry_and_cash_reconciles() -> None:
    first = ev.validate_candidate(candidate("20230103", "20230105", "20230110", "SPY", "CALL", 3))
    second = ev.validate_candidate(candidate("20230105", "20230109", "20230112", "SPY", "CALL", 4))
    for row in (first, second):
        row["_split"] = "TRAIN"
        row["_ev_adverse"] = 1.0
        row["_ev_base"] = 1.0
    coverage = {"rows": [{"entry_date": day} for day in ("20230103", "20230105", "20230109")]}
    ledger = ev.replay([first, second], coverage, "ALWAYS_CALL_H2")
    day = [row["event"] for row in ledger if row["date"] == "20230105" and row["ticker"] == "SPY"]
    assert day[:2] == ["EXIT", "ENTRY"]
    exits = [row for row in ledger if row["event"] == "EXIT"]
    assert exits[-1]["cash_adverse"] == pytest.approx(100_000 + sum(row["net_adverse"] for row in (first, second)))
