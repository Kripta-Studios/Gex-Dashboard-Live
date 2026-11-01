from __future__ import annotations

from datetime import datetime, timedelta
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
    features = feature_dict(ticker, right, decision_ask, optional_null)
    features["dte"] = float((datetime.strptime(expiration, "%Y%m%d") - datetime.strptime(entry, "%Y%m%d")).days)
    features["weekday"] = float(datetime.strptime(entry, "%Y%m%d").weekday())
    base = {
        "candidate_id": f"{ticker}:{entry}:{expiration}:{right}",
        "ticker": ticker,
        "entry_date": entry,
        "exit_date": exit_date,
        "expiration": expiration,
        "strike": 505.0,
        "right": right,
        "features": features,
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
    def label_time(day: str) -> str:
        parsed = datetime.strptime(day, "%Y%m%d").replace(hour=10, minute=35, tzinfo=ev.NY)
        return parsed.isoformat()
    if scenario == 0:
        return {
            **base,
            "entry_ask": None,
            "exit_bid": None,
            "status": "NO_FILL",
            "label_available_at": label_time(entry),
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
        "label_available_at": label_time(exit_date),
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
        start = datetime.strptime(row["entry_date"], "%Y%m%d")
        end = datetime.strptime(row["exit_date"], "%Y%m%d")
        business_days = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                business_days.append(current.strftime("%Y%m%d"))
            current += timedelta(days=1)
        assert business_days[0] == row["entry_date"] and business_days[2] == row["exit_date"]
        all_dates.update(business_days[:3])
    calendar = [
        {"ticker": ticker, "date": day, "close_i": 390, "status": "COMPLETE"}
        for ticker in ev.TICKERS for day in sorted(all_dates)
    ]
    coverage_rows = []
    dates = sorted(all_dates)
    for ticker in ev.TICKERS:
        for index, day in enumerate(dates):
            ids = groups.get((ticker, day), [])
            matching = [row for row in rows if row["candidate_id"] in ids]
            expected_exit = dates[index + 2] if index + 2 < len(dates) else None
            coverage_rows.append({
                "ticker": ticker,
                "entry_date": day,
                "exit_date": expected_exit,
                "expiration": matching[0]["expiration"] if matching else None,
                "status": "PLANNED" if ids else ("NO_SERIES" if expected_exit else "HORIZON_OUTSIDE_CALENDAR"),
                "reason": "OFFERS" if ids else ("NO_SERIES" if expected_exit else "NO_OFFICIAL_H2"),
                "candidate_ids": ids,
                "entry_path": None,
                "exit_path": None,
            })
    coverage_path = root / "coverage.json"
    coverage = {"schema": "weekly_h2_coverage_v1", "calendar": calendar, "rows": coverage_rows}
    coverage_path.write_text(json.dumps(coverage), encoding="utf-8")
    inventory_path = root / "inventory.json"
    inventory_path.write_text(json.dumps({"schema": "synthetic_inventory", "sources": []}), encoding="utf-8")
    inventory_sha = sha(inventory_path)
    manifest = {
        "schema": "weekly_h2_dataset_manifest_v1",
        "status": "COMPLETE_WEEKLY_H2_DATASET_NOT_EVALUATED",
        "calendar": {"path": "synthetic/index.parquet", "sha256": ev.CALENDAR_SHA256},
        "files": {
            "candidates.jsonl": {"bytes": candidates_path.stat().st_size, "sha256": sha(candidates_path), "rows": len(rows)},
            "coverage.json": {"bytes": coverage_path.stat().st_size, "sha256": sha(coverage_path), "rows": len(coverage_rows)},
            "inventory.json": {"bytes": inventory_path.stat().st_size, "sha256": inventory_sha, "rows": 0},
        },
        "implementation_pins": {
            "build_weekly_h2_dataset.py": ev.BUILDER_SHA256,
            "weekly_multiday_source_pilot.py": ev.SOURCE_PILOT_SHA256,
            "ECONOMIC_H2_CONTRACT.md": ev.CONTRACT_SHA256,
        },
        "inventory_bound_sha256": inventory_sha,
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
    assert transformed.shape == (2, 23)
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
    summary = ev.run(*paths, sha(paths[2]), output)
    assert summary["development_seen"] is True and summary["promotion_approved"] is False
    assert summary["label_support"]["TRAIN"]["lower_bound"] == 1
    assert summary["label_support"]["TRAIN"]["lower_bound_by_scenario"]["1"] == 1
    assert summary["label_support"]["TRAIN"]["lower_bound_proportion"] == pytest.approx(1 / 8)
    assert summary["unseen_classes_with_zero_train_support"]["CAL"] == [2]
    assert summary["probability_metrics_conservative"]["TRAIN"]["n"] == 8
    assert summary["probability_metrics_observed_only"]["TRAIN"]["n"] == 7
    calibration = json.loads((output / "calibration_grid.json").read_text(encoding="utf-8"))
    assert len(calibration["scores"]) == 11
    model = json.loads((output / "model.json").read_text(encoding="utf-8"))
    assert model["C"] == 1.0 and model["max_iter"] == 2000 and model["random_state"] == 0
    assert model["sklearn_version"] == "1.8.0"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["implementation_pins"]) == {"evaluate_weekly_h2_ev.py", "ECONOMIC_H2_CONTRACT.md"}
    assert (output / "ledger_ev_top1_h2_eval_adverse.jsonl").is_file()
    assert summary["economics"]["ALWAYS_CALL_H2"]["EVAL"]["base"]["pooled"]["trades"] >= 1
    train_put = summary["economics"]["ALWAYS_PUT_H2"]["TRAIN"]["base"]["pooled"]
    assert train_put["missing_exit_quote"] == 1 and train_put["missing_exit_source"] == 0
    assert train_put["duration_calendar_days_max"] is not None
    assert "SPY" in summary["coverage_by_split_ticker_reason"]["TRAIN"]
    assert set(summary["book_divergences"]["ALWAYS_CALL_H2"]["EVAL"]) == {"base_entries", "adverse_entries", "base_only", "adverse_only"}
    assert set(summary["economics"]["ALWAYS_CALL_H2"]) == {"TRAIN", "CAL", "EVAL"}
    eval_control = [json.loads(line) for line in (output / "ledger_always_call_h2_eval_base.jsonl").read_text(encoding="utf-8").splitlines()]
    first_entry = next(row for row in eval_control if row["event"] == "ENTRY")
    assert first_entry["cash"] == pytest.approx(100_000 - ev.entry_debit(1.0, 0.01))
    with pytest.raises(ev.EvaluationError, match="output already exists"):
        ev.run(*paths, sha(paths[2]), output)


def test_manifest_hash_mismatch_fails_before_output(tmp_path: Path) -> None:
    candidates_path, coverage_path, manifest_path = write_dataset(tmp_path, synthetic_rows())
    candidates_path.write_text(candidates_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    output = tmp_path / "never_created"
    with pytest.raises(ev.EvaluationError, match="manifest hash mismatch"):
        ev.run(candidates_path, coverage_path, manifest_path, sha(manifest_path), output)
    assert not output.exists()


def test_coverage_h2_must_be_second_official_session(tmp_path: Path) -> None:
    candidates_path, coverage_path, manifest_path = write_dataset(tmp_path, synthetic_rows())
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    row = next(item for item in coverage["rows"] if item["candidate_ids"])
    row["exit_date"] = "20230106"
    coverage_path.write_text(json.dumps(coverage), encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["coverage.json"].update(bytes=coverage_path.stat().st_size, sha256=sha(coverage_path))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ev.EvaluationError, match="second official session"):
        ev.run(candidates_path, coverage_path, manifest_path, sha(manifest_path), tmp_path / "out")


def test_label_clock_must_be_exact_new_york_1035() -> None:
    raw = candidate("20230403", "20230405", "20230410", "SPY", "CALL", 3)
    raw["label_available_at"] = "2023-04-05T10:36:00-04:00"
    with pytest.raises(ev.EvaluationError, match="exact 10:35"):
        ev.validate_candidate(raw)


def test_replay_exits_before_same_day_reentry_and_cash_reconciles() -> None:
    first = ev.validate_candidate(candidate("20230103", "20230105", "20230110", "SPY", "CALL", 3))
    second = ev.validate_candidate(candidate("20230105", "20230109", "20230112", "SPY", "CALL", 4))
    for row in (first, second):
        row["_split"] = "TRAIN"
        row["_ev_adverse"] = 1.0
        row["_ev_base"] = 1.0
    coverage = {"rows": [{"entry_date": day} for day in ("20230103", "20230105", "20230109")]}
    ledger = ev.replay([first, second], coverage, "ALWAYS_CALL_H2", "TRAIN", "adverse")
    day = [row["event"] for row in ledger if row["date"] == "20230105" and row["ticker"] == "SPY"]
    assert day[:2] == ["EXIT", "ENTRY"]
    exits = [row for row in ledger if row["event"] == "EXIT"]
    assert exits[-1]["cash"] == pytest.approx(100_000 + sum(row["net_adverse"] for row in (first, second)))


def test_capital_blocked_is_replay_event_not_model_no_fill() -> None:
    row = ev.validate_candidate(candidate("20230103", "20230105", "20230110", "SPY", "CALL", 3))
    row["_split"] = "TRAIN"
    row["_ev_base"] = row["_ev_adverse"] = 1.0
    coverage = {"rows": [{"entry_date": day} for day in ("20230103", "20230105")]}
    base = ev.replay([row], coverage, "ALWAYS_CALL_H2", "TRAIN", "base", starting_cash=102.5)
    adverse = ev.replay([row], coverage, "ALWAYS_CALL_H2", "TRAIN", "adverse", starting_cash=102.5)
    assert any(item["event"] == "ENTRY" for item in base)
    assert any(item["event"] == "CAPITAL_BLOCKED" for item in adverse)
    assert not any(item["event"] == "NO_FILL" for item in adverse)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("dte", 6.0, "DTE mismatch"), ("weekday", 2.0, "weekday mismatch"), ("delta", -0.5, "delta invalid")],
)
def test_feature_identity_guards_fail_closed(field: str, value: float, message: str) -> None:
    raw = candidate("20230403", "20230405", "20230410", "SPY", "CALL", 3)
    raw["features"][field] = value
    with pytest.raises(ev.EvaluationError, match=message):
        ev.validate_candidate(raw)
