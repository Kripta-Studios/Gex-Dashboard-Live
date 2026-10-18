"""Fixed, descriptive quote diagnostics for the sealed level oracle."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

TICKER = "SPY"
DATE = "20250102"
CONTROL = "gbt_net__0"
ATOL = 1e-12


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def valid_quote(cache: dict, minute: int, contract: int) -> bool:
    bid = float(cache["bid"][minute, contract])
    ask = float(cache["ask"][minute, contract])
    flags = int(cache["row_flags"][minute, contract])
    return bool((flags & 3) == 3 and np.isfinite(bid) and np.isfinite(ask)
                and bid >= 0 and ask > 0 and bid <= ask)


def repeated_observed_run(cache: dict, minute: int, contract: int) -> int:
    if not valid_quote(cache, minute, contract):
        return 0
    bid = float(cache["bid"][minute, contract])
    ask = float(cache["ask"][minute, contract])
    length = 1
    for prior in range(minute - 1, -1, -1):
        if (not valid_quote(cache, prior, contract)
                or float(cache["bid"][prior, contract]) != bid
                or float(cache["ask"][prior, contract]) != ask):
            break
        length += 1
    return length


def contract_lookup(cache: dict) -> dict[tuple[float, int], int]:
    return {(float(strike), int(right)): idx for idx, (strike, right)
            in enumerate(zip(cache["strike"], cache["right"], strict=True))}


def observation(cache: dict, lookup: dict, population: str, leg: str,
                action_id: int, minute: int, contract: int) -> dict:
    strike = float(cache["strike"][contract])
    right = int(cache["right"][contract])
    quote_ok = valid_quote(cache, minute, contract)
    spot_ok = bool(cache["spot_valid"][minute]) and np.isfinite(cache["spot"][minute])
    bid = float(cache["bid"][minute, contract]) if quote_ok else np.nan
    ask = float(cache["ask"][minute, contract]) if quote_ok else np.nan
    spot = float(cache["spot"][minute]) if spot_ok else np.nan
    intrinsic = (max(spot - strike, 0.0) if right == 0 else max(strike - spot, 0.0)) if spot_ok else np.nan
    spread = ask - bid if quote_ok else np.nan
    spread_ratio = spread / ask if quote_ok else np.nan
    opposite = lookup.get((strike, 1 - right))
    pair_ok = spot_ok and opposite is not None and valid_quote(cache, minute, opposite)
    parity = np.nan
    if pair_ok:
        own_mid = (bid + ask) / 2
        other_mid = (float(cache["bid"][minute, opposite])
                     + float(cache["ask"][minute, opposite])) / 2
        call_mid, put_mid = (own_mid, other_mid) if right == 0 else (other_mid, own_mid)
        parity = call_mid - put_mid - (spot - strike)
    run = repeated_observed_run(cache, minute, contract)
    return {
        "population": population, "leg": leg, "action_id": int(action_id),
        "minute": int(minute), "contract_i": int(contract), "right": right,
        "strike": strike, "quote_valid": quote_ok, "spot_valid": spot_ok,
        "bid": bid, "ask": ask, "spot": spot, "approx_intrinsic": intrinsic,
        "ask_minus_intrinsic": ask - intrinsic if quote_ok and spot_ok else np.nan,
        "bid_minus_intrinsic": bid - intrinsic if quote_ok and spot_ok else np.nan,
        "ask_below_intrinsic": bool(quote_ok and spot_ok and ask + ATOL < intrinsic),
        "spread": spread, "spread_over_ask": spread_ratio,
        "zero_bid": bool(quote_ok and bid == 0),
        "spread_over_ask_ge_025": bool(quote_ok and spread_ratio >= 0.25),
        "spread_over_ask_ge_050": bool(quote_ok and spread_ratio >= 0.50),
        "repeated_observed_run": run,
        "repeated_observed_ge_3": run >= 3, "repeated_observed_ge_5": run >= 5,
        "parity_pair_available": bool(pair_ok), "approx_parity_residual": parity,
        "approx_parity_abs": abs(parity) if pair_ok else np.nan,
        "approx_parity_abs_ge_010": bool(pair_ok and abs(parity) >= 0.10),
        "approx_parity_abs_ge_025": bool(pair_ok and abs(parity) >= 0.25),
        "approx_parity_abs_ge_050": bool(pair_ok and abs(parity) >= 0.50),
    }


def describe(values: pd.Series) -> dict:
    numeric = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if not len(numeric):
        return {"n": 0, "min": None, "p10": None, "median": None,
                "mean": None, "p90": None, "max": None}
    return {"n": len(numeric), "min": float(np.min(numeric)),
            "p10": float(np.quantile(numeric, 0.10)), "median": float(np.median(numeric)),
            "mean": float(np.mean(numeric)), "p90": float(np.quantile(numeric, 0.90)),
            "max": float(np.max(numeric))}


def summarize(frame: pd.DataFrame) -> dict:
    boolean = ("quote_valid", "spot_valid", "ask_below_intrinsic", "zero_bid",
               "spread_over_ask_ge_025", "spread_over_ask_ge_050",
               "repeated_observed_ge_3", "repeated_observed_ge_5",
               "parity_pair_available", "approx_parity_abs_ge_010",
               "approx_parity_abs_ge_025", "approx_parity_abs_ge_050")
    continuous = ("ask_minus_intrinsic", "bid_minus_intrinsic", "spread",
                  "spread_over_ask", "repeated_observed_run",
                  "approx_parity_residual", "approx_parity_abs")
    result = {"observations": len(frame), "rates": {}, "continuous": {}}
    for name in boolean:
        count = int(frame[name].sum())
        result["rates"][name] = {"count": count, "rate": count / len(frame) if len(frame) else None}
    for name in continuous:
        result["continuous"][name] = describe(frame[name])
    return result


def relative_comparison(summary: dict, selected: str, reference: str) -> dict:
    result = {}
    for metric in ("ask_below_intrinsic", "zero_bid", "spread_over_ask_ge_025",
                   "spread_over_ask_ge_050", "repeated_observed_ge_3",
                   "repeated_observed_ge_5", "approx_parity_abs_ge_025",
                   "approx_parity_abs_ge_050"):
        left = summary[selected]["rates"][metric]["rate"]
        right = summary[reference]["rates"][metric]["rate"]
        result[metric] = {"selected_rate": left, "reference_rate": right,
                          "rate_difference": left - right,
                          "rate_ratio": None if right == 0 else left / right}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--oracle-audit", type=Path, required=True)
    parser.add_argument("--learner-root", type=Path, required=True)
    parser.add_argument("--learner-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    oracle_audit = json.loads(args.oracle_audit.read_text(encoding="utf-8"))
    learner_audit = json.loads(args.learner_audit.read_text(encoding="utf-8"))
    require(oracle_audit["status"] == "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT", "Oracle audit")
    require(
        learner_audit["status"] == "PASS_INDEPENDENT_LEARNER_ECONOMIC_EXECUTION_AUDIT",
        "Learner audit",
    )
    index_path = args.engine_root / "index.parquet"
    require(sha256(index_path) == oracle_audit["binding"]["index_sha256"], "Engine index hash")
    index = pd.read_parquet(index_path)
    match = index.loc[(index.ticker == TICKER) & (index.date.astype(str) == DATE)]
    require(len(match) == 1 and match.iloc[0].status == "COMPLETE", "Fixed pilot day")
    day = match.iloc[0]
    day_root = Path(day.day_root)
    paths = {name: day_root / name for name in
             ("actions.parquet", "labels.parquet", "oracle_ledger.parquet")}
    for name in paths:
        require(sha256(paths[name]) == day[name.removesuffix(".parquet") + "_sha256"], name + " hash")
    cache_path = Path(day.cache_path)
    require(sha256(cache_path) == day.cache_npz_sha256, "Cache hash")
    control_path = args.learner_root / "validation" / f"{CONTROL}_ledger.parquet"
    expected_control = learner_audit["verified_economic_outputs"][f"validation\\{CONTROL}_ledger.parquet"]
    require(sha256(control_path) == expected_control, "Control ledger hash")

    with np.load(cache_path, allow_pickle=False) as stored:
        cache = {name: stored[name] for name in stored.files}
    lookup = contract_lookup(cache)
    actions = pd.read_parquet(paths["actions.parquet"])
    oracle = pd.read_parquet(paths["oracle_ledger.parquet"])
    control_all = pd.read_parquet(control_path)
    control = control_all.loc[(control_all.ticker == TICKER)
                              & (control_all.date.astype(str) == DATE)].copy()
    rows = []
    offered = actions[["entry_i", "contract_i"]].drop_duplicates().sort_values(["entry_i", "contract_i"])
    for ordinal, row in enumerate(offered.itertuples(index=False)):
        rows.append(observation(cache, lookup, "OFFERED_ENTRY", "ENTRY", -1 - ordinal,
                                int(row.entry_i), int(row.contract_i)))
    for population, ledger in (("ORACLE", oracle), ("CONTROL", control)):
        for row in ledger.itertuples(index=False):
            rows.append(observation(cache, lookup, population + "_ENTRY", "ENTRY",
                                    row.action_id, int(row.entry_i), int(row.contract_i)))
            rows.append(observation(cache, lookup, population + "_EXIT", "EXIT",
                                    row.action_id, int(row.exit_i), int(row.contract_i)))
    observations = pd.DataFrame(rows)
    summaries = {name: summarize(part.reset_index(drop=True))
                 for name, part in observations.groupby("population", sort=True)}
    comparisons = {
        "oracle_entry_vs_offered_entry": relative_comparison(summaries, "ORACLE_ENTRY", "OFFERED_ENTRY"),
        "oracle_entry_vs_control_entry": relative_comparison(summaries, "ORACLE_ENTRY", "CONTROL_ENTRY"),
    }
    args.output.mkdir(parents=True, exist_ok=False)
    observations.to_parquet(args.output / "observations.parquet", index=False)
    source_paths = {"engine_index": index_path, "cache": cache_path, **paths,
                    "control_ledger": control_path, "oracle_audit": args.oracle_audit,
                    "learner_audit": args.learner_audit}
    sources = {name: {"path": str(path.resolve()), "sha256": sha256(path)}
               for name, path in source_paths.items()}
    (args.output / "sources.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    summary = {
        "status": "COMPLETE_FIXED_ORACLE_QUOTE_ANOMALY_DIAGNOSTIC",
        "ticker": TICKER, "date": DATE, "control": CONTROL,
        "populations": summaries, "comparisons": comparisons,
        "observations_sha256": sha256(args.output / "observations.parquet"),
        "sources_sha256": sha256(args.output / "sources.json"),
        "diagnostic_only_no_exclusions": True, "original_trades_and_pnl_unchanged": True,
        "option_quote_age_verified": False, "parity_is_approximate_not_arbitrage_proof": True,
        "new_raw_values_read": False, "technical_ready": False, "promotion_approved": False,
        "script_sha256": sha256(Path(__file__).resolve()),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary, allow_nan=False))


if __name__ == "__main__":
    main()

