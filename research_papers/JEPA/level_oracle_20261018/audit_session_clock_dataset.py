"""Independent audit of the incremental full/short SessionClock dataset.

The 2,595 complete full sessions are bound to the already-passed full oracle
audit and their reference hashes.  The 24 short sessions are reconstructed
from their sealed caches without importing any producer calculation module.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import exchange_calendars as xc
import numpy as np
import pandas as pd

STATUS = "PASS_INDEPENDENT_SESSION_CLOCK_DATASET_AUDIT"
FIRST, LAST, EOD, CLOSE = 60, 195, 205, 210
MISSING = {(t, d) for t in ("QQQ", "SPY") for d in ("20260401", "20260409", "20260415")}
LABEL_COLUMNS = ["action_id", "status", "trigger_i", "exit_i", "reason", "entry_ask",
                 "exit_bid", "missing_exit", "missing_spot_count", "net_base",
                 "net_adverse", "hold_minutes"]


def digest(path: Path | str) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(condition, message):
    if not bool(condition):
        raise AssertionError(message)


def same_frame(actual, expected, key, context):
    actual = actual.sort_values(key).reset_index(drop=True)
    expected = expected.sort_values(key).reset_index(drop=True)
    require(actual.columns.tolist() == expected.columns.tolist(), context + " columns")
    require(len(actual) == len(expected), context + " rows")
    for name in actual:
        if pd.api.types.is_numeric_dtype(actual[name]):
            require(np.allclose(actual[name].to_numpy(float), expected[name].to_numpy(float),
                                rtol=0, atol=1e-8, equal_nan=True), context + " " + name)
        else:
            require(actual[name].fillna("<NA>").equals(expected[name].fillna("<NA>")),
                    context + " " + name)


def load_cache(path):
    path = Path(path)
    meta = read(path.with_suffix(".json"))
    require(digest(path) == meta["sha256"], "short cache hash")
    with np.load(path, allow_pickle=False) as saved:
        raw = {name: saved[name] for name in saved.files}
    require(set(raw) == set(meta["array_schema"]), "short cache schema")
    for name, value in raw.items():
        spec = meta["array_schema"][name]
        require(list(value.shape) == spec["shape"] and str(value.dtype) == spec["dtype"],
                "short cache array " + name)
    require(raw["time_ns"].shape == (211,), "short minute count")
    require(np.all(np.diff(raw["time_ns"]) == 60_000_000_000), "short minute grid")
    return raw, meta


def valid_quote(raw, minute, contract):
    bid, ask = float(raw["bid"][minute, contract]), float(raw["ask"][minute, contract])
    return bool((int(raw["row_flags"][minute, contract]) & 3) == 3
                and np.isfinite(bid) and np.isfinite(ask)
                and bid >= 0 and ask > 0 and bid <= ask)


def net(entry, exit_, adverse=False):
    slip = Decimal(".02" if adverse else ".01")
    return float((max(Decimal(str(exit_)) - slip, Decimal(0))
                  - Decimal(str(entry)) - slip) * 100 - Decimal("2.60"))


def exit_geometry(raw, row):
    start = int(row.state_i) + 1
    spot = np.asarray(raw["spot"], float)[start:EOD]
    valid = np.asarray(raw["spot_valid"], bool)[start:EOD] & np.isfinite(spot) & (spot > 0)
    if int(row.right) == 0:
        target = spot >= float(row.target_center) - float(row.band)
        stop = spot <= float(row.stop_center) + float(row.band)
    else:
        target = spot <= float(row.target_center) + float(row.band)
        stop = spot >= float(row.stop_center) - float(row.band)
    hits = np.flatnonzero(valid & (target | stop))
    if not len(hits):
        return -1, EOD, "EOD", int((~valid).sum())
    offset = int(hits[0])
    trigger = start + offset
    return trigger, trigger + 1, "STOP" if stop[offset] else "TARGET", int((~valid[:offset + 1]).sum())


def reconstruct_labels(raw, actions):
    rows, geometry = [], {}
    for row in actions.itertuples(index=False):
        entry, contract = int(row.entry_i), int(row.contract_i)
        if not valid_quote(raw, entry, contract):
            rows.append(dict(action_id=row.action_id, status="NO_FILL", trigger_i=-1,
                             exit_i=entry, reason="NO_FILL", entry_ask=np.nan,
                             exit_bid=np.nan, missing_exit=False, missing_spot_count=0,
                             net_base=0.0, net_adverse=0.0, hold_minutes=0))
            continue
        key = (int(row.state_i), int(row.right), float(row.target_center),
               float(row.stop_center), float(row.band))
        geometry.setdefault(key, exit_geometry(raw, row))
        trigger, exit_i, reason, missing = geometry[key]
        ask = float(raw["ask"][entry, contract])
        missing_exit = not valid_quote(raw, exit_i, contract)
        bid = 0.0 if missing_exit else float(raw["bid"][exit_i, contract])
        rows.append(dict(action_id=row.action_id, status="FILLED", trigger_i=trigger,
                         exit_i=exit_i, reason=reason, entry_ask=ask, exit_bid=bid,
                         missing_exit=missing_exit, missing_spot_count=missing,
                         net_base=net(ask, bid), net_adverse=net(ask, bid, True),
                         hold_minutes=exit_i - entry))
    return pd.DataFrame(rows, columns=LABEL_COLUMNS)


def oracle_totals(actions, labels):
    joined = actions.merge(labels, on="action_id", validate="one_to_one").sort_values("action_id")
    value = np.zeros(EOD + 2)
    choice = np.full(EOD + 2, -1, dtype=np.int64)
    groups = {int(i): g for i, g in joined.groupby("state_i", sort=True)}
    for minute in range(LAST, FIRST - 1, -1):
        best = value[minute + 1]
        for row in groups.get(minute, joined.iloc[:0]).itertuples(index=False):
            if row.status != "FILLED":
                continue
            candidate = float(row.net_base) + value[int(row.exit_i) + 1]
            if candidate > best:
                best, choice[minute] = candidate, int(row.action_id)
        value[minute] = best
    indexed, ledger, minute = joined.set_index("action_id", drop=False), [], FIRST
    while minute <= LAST:
        action_id = int(choice[minute])
        if action_id < 0:
            minute += 1
        else:
            row = indexed.loc[action_id]
            ledger.append(row)
            minute = int(row.exit_i) + 1
    base = float(sum(float(row.net_base) for row in ledger))
    adverse = float(sum(float(row.net_adverse) for row in ledger))
    require(np.isclose(base, value[FIRST], rtol=0, atol=1e-8), "short DP value")
    return len(ledger), base, adverse


def safe(values):
    return np.nan_to_num(np.asarray(values), nan=0, posinf=0, neginf=0).astype(np.float32)


def action_features(raw, actions, width):
    output = []
    for row in actions.itertuples(index=False):
        minute, contract = int(row.state_i), int(row.contract_i)
        spot = float(raw["spot"][minute])
        bid, ask, iv, delta, vega, theta = [float(raw[k][minute, contract])
                                           for k in ("bid", "ask", "iv", "delta", "vega", "theta")]
        target, stop = float(row.target_center), float(row.stop_center)
        td, sd = abs(target - spot), abs(stop - spot)
        quote = np.isfinite(bid) and np.isfinite(ask) and bid >= 0 and ask > 0 and bid <= ask
        iv_ok, d_ok = np.isfinite(iv) and 0 < iv <= 5, np.isfinite(delta) and abs(delta) <= 1
        v_ok, t_ok = np.isfinite(vega) and vega >= 0, np.isfinite(theta)
        bits = [float(int(getattr(row, which + "_source_mask")) & bit != 0)
                for which in ("target", "stop") for bit in (1, 2, 4, 8, 16)]
        output.append(safe([int(row.right) == 1, (row.strike - spot) / width,
                            row.selected_delta, row.delta_bucket, (target - spot) / width,
                            (stop - spot) / width, td / width, sd / width, row.band / width,
                            td / sd if sd > 0 else 0, bid / spot, ask / spot,
                            (ask - bid) / spot, iv if iv_ok else np.nan,
                            delta if d_ok else np.nan, vega / spot if v_ok else np.nan,
                            theta / spot if t_ok else np.nan, quote, iv_ok,
                            int(raw["row_flags"][minute, contract]) & 1 != 0,
                            d_ok, v_ok, t_ok, *bits]))
    return np.asarray(output, np.float32).reshape(-1, 33)


def audit_short(row):
    root = Path(row.day_root)
    raw, meta = load_cache(row.cache_path)
    require(digest(Path(row.cache_meta_path)) == row.cache_meta_sha256, "short metadata index hash")
    states = pd.read_parquet(root / "states.parquet")
    levels = pd.read_parquet(root / "levels.parquet")
    actions = pd.read_parquet(root / "actions.parquet")
    labels = pd.read_parquet(root / "labels.parquet")
    for name, frame in (("states", states), ("levels", levels), ("actions", actions), ("labels", labels)):
        require(digest(root / (name + ".parquet")) == getattr(row, name + "_sha256"), name + " hash")
    require(states.state_i.tolist() == list(range(FIRST, LAST + 1)), "short state universe")
    spot = np.asarray(raw["spot"], float)
    valid = np.asarray(raw["spot_valid"], bool) & np.isfinite(spot) & (spot > 0)
    initial = spot[:60][valid[:60]]
    ib_valid = len(initial) >= 57 and (float(initial.max()) > float(initial.min()) if len(initial) else False)
    low, high = (float(initial.min()), float(initial.max())) if ib_valid else (np.nan, np.nan)
    require(np.array_equal(states.state_valid.to_numpy(bool), valid[FIRST:LAST + 1] & ib_valid), "short state validity")
    require(np.allclose(states.ib_low, low, rtol=0, atol=0, equal_nan=True), "short IB low")
    require(np.allclose(states.ib_high, high, rtol=0, atol=0, equal_nan=True), "short IB high")
    require(actions.empty or (actions.state_i.between(FIRST, LAST).all()
                              and np.array_equal(actions.entry_i, actions.state_i + 1)), "short action time")
    reconstructed = reconstruct_labels(raw, actions)
    same_frame(labels, reconstructed, ["action_id"], "short labels")
    trades, base, adverse = oracle_totals(actions, reconstructed)

    feature_path = Path(row.features_path)
    feature_meta = read(row.features_meta_path)
    require(digest(row.features_meta_path) == row.features_meta_sha256, "short feature metadata hash")
    require(digest(feature_path) == row.features_sha256 == feature_meta["sha256"], "short feature hash")
    with np.load(feature_path, allow_pickle=False) as saved:
        packed = {name: saved[name] for name in saved.files}
    require(np.array_equal(packed["state_i"].reshape(-1), np.arange(FIRST, LAST + 1)), "feature state ids")
    require(packed["base"].shape == (136, 81) and packed["tokens"].shape == (136, 20, 45)
            and packed["maps"].shape == (136, 20, 5, 64), "short feature shapes")
    require(np.array_equal(packed["base"][:, 0], (np.arange(FIRST, LAST + 1) / 390).astype(np.float32)), "minute feature")
    require(np.array_equal(packed["base"][:, 1], ((CLOSE - np.arange(FIRST, LAST + 1)) / 390).astype(np.float32)), "remaining feature")
    require(np.all(packed["bar_end_i"] < packed["state_i"].reshape(-1, 1)), "future bar boundary")
    action_path = Path(row.action_features_path)
    require(digest(action_path) == row.action_features_sha256, "short action feature hash")
    require(digest(row.action_features_meta_path) == row.action_features_meta_sha256,
            "short action feature metadata hash")
    with np.load(action_path, allow_pickle=False) as saved:
        require(np.array_equal(saved["action_id"], actions.action_id.to_numpy(np.int32)), "action feature ids")
        expected = action_features(raw, actions, high - low if ib_valid else 1.0)
        require(np.array_equal(saved["action_features"], expected), "short action features")
    freeze = read(root / "features_causal_freeze.json")
    require("labels.parquet" not in freeze, "labels entered causal freeze")
    for name, expected in freeze.items():
        require(digest(root / name) == expected, "short causal freeze " + name)
    return dict(actions=len(actions), oracle_trades=trades, oracle_net_base=base,
                oracle_net_adverse_same_path=adverse,
                missing_entries=int((labels.status == "NO_FILL").sum()),
                missing_exits=int(labels.missing_exit.sum()), clock_basis=meta["clock_basis"],
                oi_clock_basis=meta["oi_clock_basis"])


def verify_day_marker(root, row, contract_sha):
    section = "references" if int(row.close_i) == 390 else "short"
    marker = read(root / section / row.ticker / row.date / "complete.json")
    require(marker["contract_sha256"] == contract_sha, "day marker contract")
    for field in ("ticker", "date", "status", "close_i", "cache_npz_sha256",
                  "cache_meta_sha256", "actions_sha256", "labels_sha256",
                  "features_sha256", "features_meta_sha256",
                  "action_features_sha256", "action_features_meta_sha256"):
        require(marker["row"][field] == getattr(row, field), "day marker row " + field)
    paths = (row.cache_path, row.cache_meta_path, row.features_path, row.features_meta_path,
             row.action_features_path, row.action_features_meta_path)
    for path in paths:
        resolved = str(Path(path).resolve())
        require(resolved in marker["files"], "day marker membership")
        # Full feature bytes and every short byte are verified elsewhere; the
        # marker still must state the index digest for all referenced members.
        name = Path(path).name
        expected = (row.cache_npz_sha256 if name.endswith(".npz") and "action" not in name
                    and "feature" not in name else None)
        if expected is not None:
            require(marker["files"][resolved] == expected, "day marker cache digest")
    return marker


def expected_calendar():
    schedule = xc.get_calendar("XNYS").schedule.loc["2023-01-03":"2026-06-30"]
    rows = []
    for day, item in schedule.iterrows():
        minutes = int((item.close - item.open).total_seconds() / 60)
        require(minutes in (210, 390), "calendar schedule")
        for ticker in ("QQQ", "SPXW", "SPY"):
            rows.append((ticker, day.strftime("%Y%m%d"), minutes))
    require(len(rows) == 2625 and sum(x[2] == 210 for x in rows) == 24, "calendar coverage")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--original-root", type=Path, required=True)
    parser.add_argument("--original-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, original = args.dataset_root.resolve(), args.original_root.resolve()
    completion, contract = read(root / "completion.json"), read(root / "dataset_contract.json")
    require(completion["status"] == "COMPLETE", "session dataset incomplete")
    require(digest(root / "index.parquet") == completion["index_sha256"], "session index seal")
    full_audit = read(args.original_audit)
    require(full_audit["status"] == "PASS_INDEPENDENT_FULL_LEVEL_ORACLE_AUDIT", "full audit authority")
    require(Path(full_audit["binding"]["engine_root"]).resolve() == original, "full audit root")
    require(digest(original / "index.parquet") == full_audit["binding"]["index_sha256"], "full audited index")
    require(contract["original_index_sha256"] == digest(original / "index.parquet")
            and contract["original_audit_sha256"] == digest(args.original_audit), "incremental authority")
    index = pd.read_parquet(root / "index.parquet")
    index["date"] = index.date.astype(str)
    require(not index.duplicated(["ticker", "date"]).any(), "session index duplicates")
    require(index.status.value_counts().to_dict() == {"COMPLETE": 2619, "MISSING_SOURCE": 6},
            "session status counts")
    require(completion["available_days"] == 2619 and completion["missing_days"] == 6
            and completion["short_days"] == 24 and completion["full_days_reused"] == 2595,
            "completion coverage")
    expected = expected_calendar()
    require(set(zip(index.ticker, index.date, index.close_i, strict=True)) == set(expected), "session membership")
    require(set(zip(index.loc[index.status == "MISSING_SOURCE", "ticker"],
                    index.loc[index.status == "MISSING_SOURCE", "date"], strict=True)) == MISSING, "missing identities")
    old = pd.read_parquet(original / "index.parquet")
    old["date"] = old.date.astype(str)
    old = old.set_index(["ticker", "date"])
    short_results, full_references = [], 0
    for row in index.itertuples(index=False):
        if row.status == "MISSING_SOURCE":
            require(row.evaluation_status == "NO_EVALUABLE", "missing evaluation status")
            continue
        verify_day_marker(root, row, completion["dataset_contract_sha256"])
        if int(row.close_i) == 210:
            short_results.append({"ticker": row.ticker, "date": row.date, **audit_short(row)})
            continue
        source = old.loc[(row.ticker, row.date)]
        require(bool(row.reused_full_session), "full reference flag")
        for name in ("cache_npz_sha256", "cache_meta_sha256", "states_sha256",
                     "levels_sha256", "actions_sha256", "labels_sha256", "causal_freeze_sha256"):
            require(getattr(row, name) == source[name], "full reference " + name)
        require(digest(row.features_path) == row.features_sha256
                and digest(row.action_features_path) == row.action_features_sha256
                and digest(row.features_meta_path) == row.features_meta_sha256
                and digest(row.action_features_meta_path) == row.action_features_meta_sha256,
                "full feature reference")
        full_references += 1
    require(full_references == 2595 and len(short_results) == 24, "audited coverage")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(short_results).to_csv(out / "short_day_audit.csv", index=False)
    binding = dict(engine_root=str(root), index_sha256=digest(root / "index.parquet"),
                   dataset_contract_sha256=digest(root / "dataset_contract.json"),
                   completion_sha256=digest(root / "completion.json"), feature_root=str(root),
                   feature_contract_sha256=digest(root / "feature_contract.json"),
                   available_days=2619, missing_days=6)
    result = dict(status=STATUS, binding=binding, **binding, audited_short_days=24,
                  verified_full_references=2595, missing_source_days=6,
                  short_actions=sum(x["actions"] for x in short_results),
                  short_oracle_trades=sum(x["oracle_trades"] for x in short_results),
                  short_oracle_net_base=float(sum(x["oracle_net_base"] for x in short_results)),
                  short_oracle_net_adverse_same_path=float(sum(x["oracle_net_adverse_same_path"] for x in short_results)),
                  full_economics_recomputed=False, full_economics_authority=str(args.original_audit.resolve()),
                  oracle_is_hindsight_upper_bound=True, promotion_approved=False,
                  audit_script_sha256=digest(__file__))
    (out / "audit.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
