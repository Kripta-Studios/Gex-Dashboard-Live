"""TRAIN-only missingness and causal common-contract gamma diagnostics; no outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import level_engine as engine

KEYS = (
    "time_ns",
    "spot",
    "spot_valid",
    "strike",
    "right",
    "iv",
    "row_flags",
    "oi_contract_idx",
    "oi_available_ns",
    "oi_value",
    "oi_valid",
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    if path.exists():
        raise FileExistsError(path)
    partial = path.with_name(path.name + ".partial")
    with partial.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
    partial.replace(path)


def density(spot, strike, iv, minutes_left, oi):
    """Same unsigned dollar-gamma formula, caller explicitly supplies valid cohort."""
    tau = minutes_left * 60 / (365 * 86400)
    d1 = (np.log(spot / strike) + 0.5 * iv * iv * tau) / (iv * np.sqrt(tau))
    return (
        np.exp(-0.5 * d1 * d1)
        / (np.sqrt(2 * np.pi) * spot * iv * np.sqrt(tau))
        * oi
        * spot
        * spot
    )


def ratio(numerator, denominator):
    return float(numerator / denominator) if denominator > 0 else np.nan


def diagnose_day(raw, observations):
    oi = engine.available_oi_matrix(raw)
    known = engine.known_contract_matrix(raw)
    present = (raw["row_flags"] & 1) != 0
    iv = raw["iv"]
    iv_valid = np.isfinite(iv) & (iv > 0) & (iv <= 5)
    spot, strike, right = raw["spot"], raw["strike"], raw["right"]
    spot_valid = raw["spot_valid"] & np.isfinite(spot) & (spot > 0)
    oi_seen = np.zeros_like(known)
    for contract, available in zip(raw["oi_contract_idx"], raw["oi_available_ns"]):
        if int(available) != np.iinfo(np.int64).min:
            start = np.searchsorted(raw["time_ns"], available, side="left")
            oi_seen[start:, contract] = True
    eligible = present & iv_valid & np.isfinite(oi) & spot_valid[:, None]
    mass = np.full(oi.shape, np.nan)
    for minute in range(390):
        good = eligible[minute]
        mass[minute, good] = density(
            spot[minute], strike[good], iv[minute, good], 390 - minute, oi[minute, good]
        )
    ib_values = spot[:60][spot_valid[:60]]
    ib_valid = len(ib_values) >= 57 and np.ptp(ib_values) > 0
    records = []
    for side in (0, 1):
        direction = right == side
        known_count = (known & direction).sum(axis=1)
        present_count = (present & direction).sum(axis=1)
        oi_count = (np.isfinite(oi) & direction).sum(axis=1)
        iv_count = (present & iv_valid & direction).sum(axis=1)
        full_oi = (known_count > 0) & (oi_count == known_count)
        full_present = (known_count > 0) & (present_count == known_count)
        full_iv = (present_count > 0) & (iv_count == present_count)
        for obs in observations.itertuples(index=False):
            t = int(obs.state_i)
            invalid_iv = direction & present[t] & ~iv_valid[t]
            with np.errstate(invalid="ignore", divide="ignore"):
                money = np.abs(np.log(strike / spot[t]))
            otm = strike > spot[t] if side == 0 else strike < spot[t]
            common_fields = dict(
                ticker=obs.ticker,
                date=obs.date,
                state_i=t,
                side="CALL" if side == 0 else "PUT",
                action_count=int(obs.action_count),
                ipw_weight=float(obs.ipw_weight),
                known_identities=int(known_count[t]),
                present_identities=int(present_count[t]),
                oi_unreported=int((direction & known[t] & ~oi_seen[t]).sum()),
                oi_latest_invalid=int(
                    (direction & known[t] & oi_seen[t] & ~np.isfinite(oi[t])).sum()
                ),
                greek_absent_known=int((direction & known[t] & ~present[t]).sum()),
                iv_invalid_present=int(invalid_iv.sum()),
                iv_nonfinite=int((invalid_iv & ~np.isfinite(iv[t])).sum()),
                iv_nonpositive=int(
                    (invalid_iv & np.isfinite(iv[t]) & (iv[t] <= 0)).sum()
                ),
                iv_above5=int((invalid_iv & (iv[t] > 5)).sum()),
                iv_invalid_otm=int((invalid_iv & otm & spot_valid[t]).sum()),
                iv_invalid_itm=int((invalid_iv & ~otm & spot_valid[t]).sum()),
                iv_invalid_oi_zero=int((invalid_iv & (oi[t] == 0)).sum()),
                iv_invalid_oi_positive=int((invalid_iv & (oi[t] > 0)).sum()),
                static_observed_positive=bool(
                    ib_valid and np.nansum(mass[t, direction]) > 0
                ),
            )
            for low, high, label in (
                (0, 0.005, "le005"),
                (0.005, 0.01, "005_01"),
                (0.01, 0.02, "01_02"),
                (0.02, np.inf, "gt02"),
            ):
                common_fields["iv_invalid_moneyness_" + label] = int(
                    (
                        invalid_iv
                        & (money >= low if low == 0 else money > low)
                        & (money <= high)
                    ).sum()
                )
            for lag in (5, 15):
                old = t - lag
                start, stop = (t // lag - 1) * lag, (t // lag) * lag
                bar = slice(start, stop)
                bar_ok = start >= 0 and spot_valid[bar].all()
                gates = dict(
                    bar_spot=bool(bar_ok),
                    oi=bool(full_oi[t] and full_oi[bar].all()),
                    iv=bool(full_iv[t] and full_iv[bar].all()),
                    present=bool(full_present[t] and full_present[bar].all()),
                )
                positive = np.nansum(mass[:, direction], axis=1) > 0
                gates["positive"] = bool(positive[t] and positive[bar].any())
                common = direction & eligible[t] & eligible[old]
                count = int(common.sum())
                now_valid = direction & eligible[t]
                old_valid = direction & eligible[old]
                current_total, past_total = (
                    np.nansum(mass[t, direction]),
                    np.nansum(mass[old, direction]),
                )
                current_common, past_common = (
                    np.nansum(mass[t, common]),
                    np.nansum(mass[old, common]),
                )
                row = dict(
                    common_fields,
                    lag=lag,
                    old_cue_available=bool(ib_valid and all(gates.values())),
                    **{"old_gate_" + k: v for k, v in gates.items()},
                    common_available=bool(count and spot_valid[t] and spot_valid[old]),
                    common_count=count,
                    common_known_now_fraction=ratio(count, known_count[t]),
                    common_known_old_fraction=ratio(count, known_count[old]),
                    common_valid_now_fraction=ratio(count, now_valid.sum()),
                    common_valid_old_fraction=ratio(count, old_valid.sum()),
                    common_gamma_now_fraction=ratio(current_common, current_total),
                    common_gamma_old_fraction=ratio(past_common, past_total),
                    common_oi_now_fraction=ratio(
                        oi[t, common].sum(), np.nansum(oi[t, direction])
                    ),
                    common_oi_old_fraction=ratio(
                        oi[old, common].sum(), np.nansum(oi[old, direction])
                    ),
                    valid_now_not_common=int((now_valid & ~common).sum()),
                    valid_old_not_common=int((old_valid & ~common).sum()),
                )
                if count:
                    # Ordered decomposition is arithmetic attribution, not causal identification.
                    spot_step = density(
                        spot[t],
                        strike[common],
                        iv[old, common],
                        390 - old,
                        oi[old, common],
                    ).sum()
                    iv_step = density(
                        spot[t],
                        strike[common],
                        iv[t, common],
                        390 - old,
                        oi[old, common],
                    ).sum()
                    time_step = density(
                        spot[t], strike[common], iv[t, common], 390 - t, oi[old, common]
                    ).sum()
                    row.update(
                        gamma_common_old=float(past_common),
                        gamma_common_now=float(current_common),
                        delta_common=float(current_common - past_common),
                        spot_component=float(spot_step - past_common),
                        iv_component=float(iv_step - spot_step),
                        time_component=float(time_step - iv_step),
                        reported_oi_component=float(current_common - time_step),
                        reported_oi_changed=bool(
                            np.any(oi[t, common] != oi[old, common])
                        ),
                        delta_composition=float(
                            (current_total - current_common)
                            - (past_total - past_common)
                        ),
                    )
                records.append(row)
    return pd.DataFrame(records)


def summarize(frame):
    excluded = {
        "ticker",
        "date",
        "state_i",
        "side",
        "lag",
        "action_count",
        "ipw_weight",
    }
    answer = {}
    for column in frame.columns:
        if column in excluded:
            continue
        values = frame[column].to_numpy(dtype=float)
        valid = np.isfinite(values)
        weights = frame.ipw_weight.to_numpy()
        action_weights = frame.action_count.to_numpy()
        answer[column] = {
            "finite_states": int(valid.sum()),
            "state_mean": float(values[valid].mean()) if valid.any() else None,
            "action_weighted_mean": float(
                np.average(values[valid], weights=action_weights[valid])
            )
            if valid.any()
            else None,
            "ipw_weighted_mean": float(
                np.average(values[valid], weights=weights[valid])
            )
            if valid.any()
            else None,
        }
    return {
        "unique_states": len(frame),
        "sample_actions": int(frame.action_count.sum()),
        "sum_action_ipw": float(frame.ipw_weight.sum()),
        "fields": answer,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source_paths = [
        Path(__file__),
        Path(engine.__file__),
        Path(__file__).with_name("GAMMA_COMMON_CONTRACT_TRAIN_DIAGNOSTIC_SPEC.md"),
        args.sample,
    ]
    sources = {str(p.resolve()): sha(p) for p in source_paths}
    write_json(
        args.output / "preexecution.json",
        {"sources": sources, "train_only": True, "new_fits": 0},
    )
    sample = pd.read_parquet(
        args.sample, columns=["ticker", "date", "state_i", "weight"]
    )
    sample["date"] = sample.date.astype(str)
    if (
        not sample.date.str.startswith(("2023", "2024")).all()
        or not sample.state_i.between(60, 375).all()
    ):
        raise ValueError("Only TRAIN2023-2024 decision states permitted")
    if not np.isfinite(sample.weight).all() or (sample.weight <= 0).any():
        raise ValueError("Invalid original IPW")
    observations = (
        sample.groupby(["ticker", "date", "state_i"], sort=True)
        .agg(action_count=("weight", "size"), ipw_weight=("weight", "sum"))
        .reset_index()
    )
    paths = []
    for number, ((ticker, date), states) in enumerate(
        observations.groupby(["ticker", "date"], sort=True), 1
    ):
        path = args.cache_root / ticker / (date + ".npz")
        metadata_path = path.with_suffix(".json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = sha(path)
        if (
            digest != metadata["sha256"]
            or metadata["ticker"] != ticker
            or metadata["date"] != date
        ):
            raise ValueError("Cache identity/hash mismatch")
        sources[str(path.resolve())] = digest
        sources[str(metadata_path.resolve())] = sha(metadata_path)
        with np.load(path, allow_pickle=False) as loaded:
            raw = {key: loaded[key] for key in KEYS}
        result = diagnose_day(raw, states)
        destination = args.output / (ticker + "_" + date + ".parquet")
        result.to_parquet(destination, index=False)
        paths.append(destination)
        write_json(
            destination.with_suffix(".json"),
            {"sha256": sha(destination), "cache_sha256": digest, "rows": len(result)},
        )
        if number % 100 == 0:
            print(json.dumps({"days_complete": number}), flush=True)
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    groups = {
        f"{side}_{lag}m": summarize(part)
        for (side, lag), part in frame.groupby(["side", "lag"])
    }
    by_ticker_year = {
        f"{ticker}_{year}_{side}_{lag}m": summarize(part)
        for (ticker, year, side, lag), part in frame.groupby(
            ["ticker", frame.date.str[:4], "side", "lag"]
        )
    }
    for path, digest in sources.items():
        if sha(path) != digest:
            raise ValueError("Changed source after diagnostic: " + path)
    write_json(
        args.output / "summary.json",
        {
            "status": "COMPLETE_TRAIN_ONLY_GAMMA_COVERAGE",
            "groups": groups,
            "ticker_year": by_ticker_year,
            "days": len(paths),
            "unique_states": len(observations),
            "sample_actions": len(sample),
            "sources": sources,
            "fits": 0,
            "val_test_read": False,
            "outcomes_read": False,
        },
    )
    write_json(
        args.output / "completion.json",
        {
            "summary_sha256": sha(args.output / "summary.json"),
            "daily_files": {path.name: sha(path) for path in paths},
        },
    )


if __name__ == "__main__":
    main()
