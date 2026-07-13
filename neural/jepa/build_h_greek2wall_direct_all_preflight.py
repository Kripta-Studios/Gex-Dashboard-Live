"""Capture the frozen 12-session H-GREEK2WALL direct-all feasibility preflight.

This builder is outcome-free.  It is deliberately incapable of expanding the
predeclared session universe and writes immutable raw/provider artifacts only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.build_wall_native_quote_sidecar import (  # noqa: E402
    canonical_json_bytes,
    current_git_commit,
    local_terminal_process_evidence,
    sha256_bytes,
    sha256_file,
    unwrap_response,
)
from neural.jepa.wall_surface_flow_environment import assert_runtime_lock  # noqa: E402
from training_data.stats import (  # noqa: E402
    calc_charm_ex,
    calc_dp_cdf_pdf,
    calc_gamma_ex,
    calc_vanna_ex,
    calc_vega_ex,
    calc_vomma_ex,
    calc_zomma_ex,
)

ENDPOINT = "/option/history/greeks/all"
OI_ENDPOINT = "/option/history/open_interest"
START_TIME = "10:19:00.000"
END_TIME = "14:30:00.000"
PREDECLARATION = (
    PROJECT_ROOT
    / "research_papers/JEPA/H_GREEK2WALL_DIRECT_ALL_V1_FEASIBILITY_PREDECLARATION.md"
)
SOURCE_CLARIFICATION = (
    PROJECT_ROOT
    / "research_papers/JEPA/H_GREEK2WALL_DIRECT_ALL_V1_SOURCE_CLARIFICATION.md"
)
DIRECT_OI_AMENDMENT = (
    PROJECT_ROOT
    / "research_papers/JEPA/H_GREEK2WALL_DIRECT_OI_V1_PREFLIGHT_AMENDMENT.md"
)
REMOTE_PROVENANCE_AMENDMENT = (
    PROJECT_ROOT
    / "research_papers/JEPA/H_GREEK2WALL_REMOTE_TERMINAL_PROVENANCE_AMENDMENT.md"
)
ENVIRONMENT_LOCK = (
    PROJECT_ROOT / "research_papers/JEPA/requirements-wall-surface-flow-v1r1.txt"
)
PROVENANCE = "CONDITIONAL_CURRENT_PROVIDER_RECONSTRUCTION"
REMOTE_BASE_URL = "http://91.99.90.39:25503/v3"
REMOTE_EVIDENCE_KIND = "USER_SUPPLIED_REMOTE_THETA_TERMINAL"
REMOTE_PROVENANCE = "CONDITIONAL_REMOTE_TERMINAL_RECONSTRUCTION"
REMOTE_STATUS_ENDPOINT = "/terminal/mdds/status"
FROZEN_SESSIONS = tuple(
    (ticker, day)
    for ticker in ("SPXW", "QQQ", "SPY")
    for day in ("20220801", "20230103", "20240102", "20250102")
)
KEYS = ("symbol", "expiration", "trade_date", "timestamp", "strike", "right")
ALPHA_GREEKS = ("vanna", "charm", "vomma", "zomma")
PROFILE_GREEKS = ("gamma", *ALPHA_GREEKS)
R_RATE = 0.0325
Q_DIV = 0.0150
REQUIRED = (
    "symbol",
    "expiration",
    "strike",
    "right",
    "timestamp",
    "underlying_timestamp",
    "underlying_price",
    "bid",
    "ask",
    "implied_vol",
    *PROFILE_GREEKS,
)
AUDIT_ONLY_GREEKS = ("veta", "speed", "color", "ultima")


def _day(value: Any) -> str:
    return "".join(c for c in str(value) if c.isdigit())[:8]


def _right(value: Any) -> str:
    value = str(value).strip().upper()
    if value in {"C", "CALL"}:
        return "CALL"
    if value in {"P", "PUT"}:
        return "PUT"
    raise ValueError(f"invalid option right: {value!r}")


def request_params(ticker: str, day: str) -> dict[str, str]:
    key = (str(ticker).upper(), _day(day))
    if key not in FROZEN_SESSIONS:
        raise AssertionError(f"session outside frozen 12-session preflight: {key}")
    return {
        "symbol": key[0],
        "expiration": key[1],
        "date": key[1],
        "strike": "*",
        "right": "both",
        "interval": "1m",
        "start_time": START_TIME,
        "end_time": END_TIME,
        "version": "latest",
        "format": "json",
    }


def oi_request_params(ticker: str, day: str) -> dict[str, str]:
    key = (str(ticker).upper(), _day(day))
    if key not in FROZEN_SESSIONS:
        raise AssertionError(f"session outside frozen 12-session preflight: {key}")
    return {
        "symbol": key[0],
        "expiration": key[1],
        "date": key[1],
        "strike": "*",
        "right": "both",
        "format": "json",
    }


def terminal_status_value(raw: bytes) -> str:
    """Normalize the documented MDDS status without accepting arbitrary 200s."""
    try:
        value: Any = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        value = raw.decode("utf-8", errors="strict")
    if isinstance(value, dict):
        for key in ("status", "response", "value"):
            if key in value:
                value = value[key]
                break
    return str(value).strip().strip('"').upper()


def commit_is_ancestor(commit: str) -> bool:
    if len(str(commit)) != 40:
        return False
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", str(commit), "HEAD"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def normalize_direct_oi(raw: Any, *, ticker: str, trade_date: str) -> pd.DataFrame:
    ticker, day = str(ticker).upper(), _day(trade_date)
    oi_request_params(ticker, day)
    frame = _flatten(raw)
    required = {"symbol", "expiration", "strike", "right", "timestamp", "open_interest"}
    if missing := sorted(required.difference(frame.columns)):
        raise KeyError(f"direct OI response missing fields: {missing}")
    out = frame.loc[:, sorted(required)].copy()
    out.insert(2, "trade_date", day)
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["expiration"] = out["expiration"].map(_day)
    out["right"] = out["right"].map(_right)
    out["strike"] = pd.to_numeric(out["strike"], errors="coerce")
    out["open_interest"] = pd.to_numeric(out["open_interest"], errors="coerce")
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    if (
        out.empty
        or out[
            ["symbol", "expiration", "right", "strike", "timestamp", "open_interest"]
        ]
        .isna()
        .any()
        .any()
    ):
        raise AssertionError("direct OI has empty/invalid rows")
    if not out["symbol"].eq(ticker).all() or not out["expiration"].eq(day).all():
        raise AssertionError("direct OI identity substitution")
    if not out["timestamp"].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError("direct OI timestamp outside native date")
    values = out["open_interest"].to_numpy(float)
    if (
        not np.isfinite(values).all()
        or (values < 0).any()
        or not np.equal(values, np.floor(values)).all()
    ):
        raise AssertionError("direct OI must be nonnegative integer")
    keys = ["symbol", "expiration", "trade_date", "strike", "right"]
    if out.duplicated(keys, keep=False).any():
        raise AssertionError("duplicate direct OI contract key")
    return out.sort_values(keys, kind="stable").reset_index(drop=True)


def _flatten(raw: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in unwrap_response(raw):
        if not isinstance(item, dict):
            raise ValueError("all-Greeks response item is not an object")
        if "contract" in item and "data" in item:
            if not isinstance(item["contract"], dict) or not isinstance(
                item["data"], list
            ):
                raise ValueError("invalid contract/data all-Greeks response")
            if any(not isinstance(point, dict) for point in item["data"]):
                raise ValueError("all-Greeks contract data contains a non-object point")
            rows.extend({**item["contract"], **point} for point in item["data"])
        else:
            rows.append(item)
    return pd.DataFrame(rows)


def normalize_response(raw: Any, *, ticker: str, trade_date: str) -> pd.DataFrame:
    ticker, day = str(ticker).upper(), _day(trade_date)
    request_params(ticker, day)  # frozen-scope assertion
    frame = _flatten(raw)
    missing = sorted(set(REQUIRED).difference(frame.columns))
    if missing:
        raise KeyError(f"direct all-Greeks response missing required fields: {missing}")
    columns = list(REQUIRED) + [c for c in AUDIT_ONLY_GREEKS if c in frame.columns]
    out = frame.loc[:, columns].copy()
    out.insert(2, "trade_date", day)
    out["symbol"] = out["symbol"].astype(str).str.upper()
    out["expiration"] = out["expiration"].map(_day)
    out["right"] = out["right"].map(_right)
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out["underlying_timestamp"] = pd.to_datetime(
        out["underlying_timestamp"], errors="coerce"
    )
    numeric = [
        "strike",
        "underlying_price",
        "bid",
        "ask",
        "implied_vol",
        *PROFILE_GREEKS,
    ]
    numeric += [c for c in AUDIT_ONLY_GREEKS if c in out]
    for column in numeric:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    identities = [
        "symbol",
        "expiration",
        "right",
        "timestamp",
        "underlying_timestamp",
        "strike",
    ]
    if out.empty or out[identities].isna().any().any():
        raise AssertionError("empty response or invalid identity/native timestamp")
    if not out["symbol"].eq(ticker).all() or not out["expiration"].eq(day).all():
        raise AssertionError(
            "contract substitution: symbol/expiration differs from request"
        )
    if set(out["right"]) != {"CALL", "PUT"}:
        raise AssertionError("wildcard response does not contain exactly both rights")
    if not out["timestamp"].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError("native option timestamp outside requested session")
    clock_mismatch = ~out["timestamp"].eq(out["underlying_timestamp"])
    if clock_mismatch.any():
        raise AssertionError(
            f"option/underlying timestamp mismatch rows={int(clock_mismatch.sum())}"
        )
    start = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {START_TIME}")
    end = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {END_TIME}")
    if not out["timestamp"].between(start, end, inclusive="both").all():
        raise AssertionError("native timestamp outside frozen request clock")
    if (
        not out["timestamp"].dt.second.eq(0).all()
        or not out["timestamp"].dt.microsecond.eq(0).all()
    ):
        raise AssertionError("direct all-Greeks interval is not an exact minute grid")
    if out.duplicated(list(KEYS)).any():
        raise AssertionError("duplicate direct all-Greeks native keys")
    if not np.isfinite(out[numeric].to_numpy(float)).all():
        raise AssertionError("required direct fields contain non-finite values")
    if not out["strike"].gt(0).all() or not out["underlying_price"].gt(0).all():
        raise AssertionError("non-positive strike or underlying")
    if out[["bid", "ask", "implied_vol"]].lt(0).any().any():
        raise AssertionError("negative quote or implied volatility")
    return out.sort_values(list(KEYS), kind="stable").reset_index(drop=True)


def field_profiles(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    for field in PROFILE_GREEKS:
        values = frame[field].to_numpy(float)
        records.append(
            {
                "field": field,
                "rows": int(len(values)),
                "finite_fraction": float(np.isfinite(values).mean()),
                "zero_fraction": float((values == 0).mean()),
                "positive_fraction": float((values > 0).mean()),
                "negative_fraction": float((values < 0).mean()),
                "distinct_values": int(pd.Series(values).nunique()),
                "minimum": float(values.min()),
                "maximum": float(values.max()),
            }
        )
    return records


def audit_sources(
    frame: pd.DataFrame,
    *,
    greeks_path: str | Path,
    oi_path: str | Path,
    direct_oi: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Audit provider revisions and positive-OI coverage; never replace values."""
    greek_path, oi_path = Path(greeks_path), Path(oi_path)
    hashes = {"greeks": sha256_file(greek_path), "oi": sha256_file(oi_path)}
    available = set(pq.ParquetFile(greek_path).schema_arrow.names)
    clock = "timestamp" if "timestamp" in available else "underlying_timestamp"
    needed = {
        "symbol",
        "expiration",
        "strike",
        "right",
        clock,
        "bid",
        "ask",
        "implied_vol",
        "underlying_price",
    }
    if missing := sorted(needed.difference(available)):
        raise KeyError(f"sealed vintage Greeks missing parity fields: {missing}")
    old = pd.read_parquet(greek_path, columns=sorted(needed))
    old["symbol"] = old["symbol"].astype(str).str.upper()
    old["expiration"] = old["expiration"].map(_day)
    old["right"] = old["right"].map(_right)
    old["timestamp"] = pd.to_datetime(old[clock], errors="coerce")
    for c in ("strike", "bid", "ask", "implied_vol", "underlying_price"):
        old[c] = pd.to_numeric(old[c], errors="coerce")
    parity_keys = ["symbol", "expiration", "timestamp", "strike", "right"]
    vintage_duplicate_rows = int(old.duplicated(parity_keys, keep=False).sum())
    if vintage_duplicate_rows:
        raise AssertionError(
            f"sealed vintage Greeks contain duplicate parity keys: rows={vintage_duplicate_rows}"
        )
    joined = frame.merge(
        old,
        on=parity_keys,
        how="left",
        suffixes=("_direct", "_vintage"),
        indicator=True,
        validate="one_to_one",
    )
    matched = joined["_merge"].eq("both")
    parity: dict[str, Any] = {
        "stored_clock": clock,
        "vintage_duplicate_parity_key_rows": vintage_duplicate_rows,
        "direct_rows": int(len(frame)),
        "vintage_key_matches": int(matched.sum()),
        "vintage_key_coverage": float(matched.mean()),
    }
    for c in ("bid", "ask", "implied_vol", "underlying_price"):
        delta = (
            joined.loc[matched, f"{c}_direct"] - joined.loc[matched, f"{c}_vintage"]
        ).abs()
        parity[f"{c}_revision_rows"] = int(delta.gt(1e-9).sum())
        parity[f"{c}_max_abs_difference"] = float(delta.max()) if len(delta) else None
    oi_available = set(pq.ParquetFile(oi_path).schema_arrow.names)
    oi_needed = {
        "symbol",
        "expiration",
        "strike",
        "right",
        "open_interest",
    }
    if "trade_date" in oi_available:
        oi_needed.add("trade_date")
    if missing := sorted(oi_needed.difference(oi_available)):
        raise KeyError(f"OI source missing fields: {missing}")
    oi = pd.read_parquet(oi_path, columns=sorted(oi_needed))
    oi["symbol"] = oi["symbol"].astype(str).str.upper()
    oi["expiration"] = oi["expiration"].map(_day)
    oi["right"] = oi["right"].map(_right)
    oi["strike"] = pd.to_numeric(oi["strike"], errors="coerce")
    oi["open_interest"] = pd.to_numeric(oi["open_interest"], errors="coerce")
    if "timestamp" in oi_available:
        oi["timestamp"] = pd.to_datetime(
            pd.read_parquet(oi_path, columns=["timestamp"])["timestamp"],
            errors="coerce",
        )
    else:
        oi["timestamp"] = pd.Series(pd.NaT, index=oi.index, dtype="datetime64[ns]")
    expected_symbol = str(frame["symbol"].iloc[0])
    expected_day = str(frame["trade_date"].iloc[0])
    if "trade_date" in oi:
        oi["trade_date"] = oi["trade_date"].map(_day)
    if oi[["symbol", "expiration", "right", "strike"]].isna().any().any():
        raise AssertionError("OI contains invalid identity/value/timestamp")
    if (
        not oi["symbol"].eq(expected_symbol).all()
        or not oi["expiration"].eq(expected_day).all()
        or ("trade_date" in oi and not oi["trade_date"].eq(expected_day).all())
    ):
        raise AssertionError("OI symbol/expiration/trade-date identity mismatch")
    finite_oi = np.isfinite(oi["open_interest"])
    if (finite_oi & oi["open_interest"].lt(0)).any():
        raise AssertionError("OI contains negative values")
    valid_oi_clock = oi["timestamp"].notna()
    if (
        not oi.loc[valid_oi_clock, "timestamp"]
        .dt.strftime("%Y%m%d")
        .eq(expected_day)
        .all()
    ):
        raise AssertionError("OI timestamp is outside its native trading day")
    oi_keys = ["symbol", "expiration", "strike", "right"]
    duplicate_oi_rows = int(oi.duplicated(oi_keys, keep=False).sum())
    if duplicate_oi_rows:
        raise AssertionError(f"duplicate OI contract keys: rows={duplicate_oi_rows}")
    availability_oi = direct_oi.copy() if direct_oi is not None else oi
    parity["oi_availability_source"] = (
        "direct_oi_primary" if direct_oi is not None else "local_vintage_test_only"
    )
    oi_join = frame[["symbol", "expiration", "strike", "right", "timestamp"]].merge(
        availability_oi,
        on=["symbol", "expiration", "strike", "right"],
        how="left",
        validate="many_to_one",
        suffixes=("_direct", "_oi"),
        indicator=True,
    )
    missing_key = oi_join["_merge"].eq("left_only")
    null_value = ~missing_key & ~np.isfinite(oi_join["open_interest"])
    null_clock = ~missing_key & oi_join["timestamp_oi"].isna()
    late = (
        ~missing_key
        & ~null_clock
        & oi_join["timestamp_oi"].gt(oi_join["timestamp_direct"])
    )
    available = ~missing_key & ~null_value & ~null_clock & ~late
    zero = available & oi_join["open_interest"].eq(0)
    positive = available & oi_join["open_interest"].gt(0)
    parity["contracts"] = int(
        frame[["symbol", "expiration", "strike", "right"]].drop_duplicates().shape[0]
    )
    parity["direct_rows_for_oi"] = int(len(oi_join))
    parity["oi_future_rows"] = int(late.sum())
    parity["oi_duplicate_contract_key_rows"] = duplicate_oi_rows
    parity["missing_oi_rows"] = int(missing_key.sum())
    parity["null_value_oi_rows"] = int(null_value.sum())
    parity["null_timestamp_oi_rows"] = int(null_clock.sum())
    parity["late_unavailable_oi_rows"] = int(late.sum())
    parity["zero_oi_rows_available"] = int(zero.sum())
    parity["positive_oi_rows_available"] = int(positive.sum())
    parity["oi_available_coverage"] = float(available.mean())
    parity["positive_oi_coverage"] = float(positive.mean())
    parity["oi_missing_reasons"] = {
        "missing_contract_key": parity["missing_oi_rows"],
        "null_or_nonfinite_value": parity["null_value_oi_rows"],
        "null_availability_timestamp": parity["null_timestamp_oi_rows"],
        "late_unavailable_at_direct_row": parity["late_unavailable_oi_rows"],
        "available_zero": parity["zero_oi_rows_available"],
        "available_positive": parity["positive_oi_rows_available"],
    }
    formula = frame.loc[frame["implied_vol"].gt(0)].copy()
    parity["local_formula_rows"] = int(len(formula))
    if len(formula):
        spot = formula["underlying_price"].to_numpy(float)
        strike = formula["strike"].to_numpy(float)
        vol = formula["implied_vol"].to_numpy(float)
        unit_oi = np.ones(len(formula), dtype=float)
        diagnostics_by_clock: dict[str, Any] = {}
        for clock_name, close_offset in (
            ("close_1600", pd.Timedelta(hours=16)),
            ("close_1615", pd.Timedelta(hours=16, minutes=15)),
        ):
            close = formula["timestamp"].dt.normalize() + close_offset
            t = (close - formula["timestamp"]).dt.total_seconds().clip(
                lower=60
            ).to_numpy(float) / (365.25 * 24 * 3600)
            dp, cdf_dp, pdf_dp = calc_dp_cdf_pdf(spot, strike, vol, t, R_RATE, Q_DIV)
            gamma_ex = calc_gamma_ex(spot, vol, t, Q_DIV, unit_oi, pdf_dp)
            gamma = gamma_ex / np.square(spot)
            vanna = calc_vanna_ex(spot, vol, t, Q_DIV, unit_oi, dp, pdf_dp) / (
                spot * vol
            )
            vega = calc_vega_ex(spot, vol, t, Q_DIV, unit_oi, pdf_dp)
            charm_call = calc_charm_ex(
                spot, vol, t, R_RATE, Q_DIV, "call", unit_oi, dp, cdf_dp, pdf_dp
            ) / (spot * t)
            charm_put = calc_charm_ex(
                spot, vol, t, R_RATE, Q_DIV, "put", unit_oi, dp, cdf_dp, pdf_dp
            ) / (spot * t)
            local = {
                "gamma": gamma,
                "vanna": vanna,
                "charm": np.where(formula["right"].eq("PUT"), charm_put, charm_call),
                "vomma": calc_vomma_ex(vega, dp, vol, t),
                "zomma": calc_zomma_ex(gamma, dp, vol, t),
            }
            diagnostics: dict[str, Any] = {}
            for field, local_values in local.items():
                direct = formula[field].to_numpy(float)
                finite = np.isfinite(direct) & np.isfinite(local_values)
                nonzero = finite & (np.abs(local_values) > 1e-15)
                ratios = direct[nonzero] / local_values[nonzero]
                direct_series = pd.Series(direct[finite])
                local_series = pd.Series(local_values[finite])
                rank_is_defined = (
                    finite.sum() > 1
                    and direct_series.nunique() > 1
                    and local_series.nunique() > 1
                )
                diagnostics[field] = {
                    "rows": int(finite.sum()),
                    "spearman": (
                        float(direct_series.corr(local_series, method="spearman"))
                        if rank_is_defined
                        else None
                    ),
                    "sign_agreement": float(
                        (
                            np.sign(direct[finite]) == np.sign(local_values[finite])
                        ).mean()
                    ),
                    "median_direct_to_local_ratio": (
                        float(np.median(ratios)) if len(ratios) else None
                    ),
                }
            diagnostics_by_clock[clock_name] = diagnostics
        parity["direct_vs_local_formula_diagnostics"] = diagnostics_by_clock
        parity["local_formula_semantics"] = {
            "gamma": "calc_gamma_ex(OI=1)/(S^2)",
            "vanna": "calc_vanna_ex(OI=1)/(S*vol)",
            "charm": "calc_charm_ex(OI=1)/(S*T)",
            "vomma": "calc_vomma_ex(calc_vega_ex(OI=1))",
            "zomma": "calc_zomma_ex(unit_gamma)",
            "oi_independent": True,
            "expiration_clocks": ["16:00", "16:15"],
            "clock_policy": "both fixed legacy diagnostics; never selectable",
            "r_rate": R_RATE,
            "q_div": Q_DIV,
            "interpretation": "legacy formula parity diagnostic only",
        }
    if (
        sha256_file(greek_path) != hashes["greeks"]
        or sha256_file(oi_path) != hashes["oi"]
    ):
        raise AssertionError("sealed source changed during parity audit")
    return {**parity, **{f"source_{k}_sha256": v for k, v in hashes.items()}}


def session_directory(root: str | Path, ticker: str, day: str) -> Path:
    request_params(ticker, day)
    return Path(root) / str(ticker).upper() / _day(day)


def canonical_source_paths(
    options_root: str | Path, ticker: str, day: str
) -> dict[str, Path]:
    ticker, day = str(ticker).upper(), _day(day)
    request_params(ticker, day)
    root = Path(options_root).resolve()
    year, month = day[:4], day[4:6]
    return {
        kind: root
        / ticker
        / kind
        / year
        / month
        / f"{ticker}_{day}_{day}_{kind}.parquet"
        for kind in ("greeks", "oi")
    }


def _audit_canonical_source_pair(
    ticker: str, day: str, paths: dict[str, Path]
) -> dict[str, Any]:
    for kind, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"missing exact canonical {kind} source: {path}")
    before = {kind: sha256_file(path) for kind, path in paths.items()}
    greek_schema = set(pq.ParquetFile(paths["greeks"]).schema_arrow.names)
    greek_required = {
        "symbol",
        "expiration",
        "trade_date",
        "strike",
        "right",
        "underlying_timestamp",
        "implied_vol",
    }
    native_greek_timestamp = "timestamp" in greek_schema
    if native_greek_timestamp:
        greek_required.add("timestamp")
    if missing := sorted(greek_required.difference(greek_schema)):
        raise KeyError(f"canonical Greeks schema missing: {missing}")
    greeks = pd.read_parquet(paths["greeks"], columns=sorted(greek_required))
    greeks["symbol"] = greeks["symbol"].astype(str).str.upper()
    greeks["expiration"] = greeks["expiration"].map(_day)
    greeks["trade_date"] = greeks["trade_date"].map(_day)
    greeks["right"] = greeks["right"].map(_right)
    greeks["strike"] = pd.to_numeric(greeks["strike"], errors="coerce")
    if native_greek_timestamp:
        greeks["timestamp"] = pd.to_datetime(greeks["timestamp"], errors="coerce")
    greeks["underlying_timestamp"] = pd.to_datetime(
        greeks["underlying_timestamp"], errors="coerce"
    )
    identities = [
        "symbol",
        "expiration",
        "trade_date",
        "right",
        "strike",
        "underlying_timestamp",
    ]
    if native_greek_timestamp:
        identities.append("timestamp")
    if greeks.empty or greeks[identities].isna().any().any():
        raise AssertionError("canonical Greeks has empty/invalid identity clock")
    if (
        not greeks["symbol"].eq(ticker).all()
        or not greeks["expiration"].eq(day).all()
        or not greeks["trade_date"].eq(day).all()
    ):
        raise AssertionError("canonical Greeks identity substitution")
    if set(greeks["right"]) != {"CALL", "PUT"}:
        raise AssertionError("canonical Greeks does not contain exactly both rights")
    if not np.isfinite(greeks["strike"]).all() or not greeks["strike"].gt(0).all():
        raise AssertionError("canonical Greeks contains invalid strikes")
    if (
        native_greek_timestamp
        and not greeks["timestamp"].eq(greeks["underlying_timestamp"]).all()
    ):
        raise AssertionError("canonical native and underlying timestamps differ")
    greek_clock = "timestamp" if native_greek_timestamp else "underlying_timestamp"
    if not greeks[greek_clock].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError("canonical Greeks contains another trade date")
    greek_keys = ["symbol", "expiration", greek_clock, "strike", "right"]
    if greeks.duplicated(greek_keys, keep=False).any():
        raise AssertionError("canonical Greeks contains duplicate native keys")

    oi_schema = set(pq.ParquetFile(paths["oi"]).schema_arrow.names)
    oi_required = {
        "symbol",
        "expiration",
        "strike",
        "right",
        "open_interest",
    }
    if "trade_date" in oi_schema:
        oi_required.add("trade_date")
    if missing := sorted(oi_required.difference(oi_schema)):
        raise KeyError(f"canonical OI schema missing: {missing}")
    oi = pd.read_parquet(paths["oi"], columns=sorted(oi_required))
    oi["symbol"] = oi["symbol"].astype(str).str.upper()
    oi["expiration"] = oi["expiration"].map(_day)
    oi["right"] = oi["right"].map(_right)
    oi["strike"] = pd.to_numeric(oi["strike"], errors="coerce")
    oi["open_interest"] = pd.to_numeric(oi["open_interest"], errors="coerce")
    if "timestamp" in oi_schema:
        oi["timestamp"] = pd.to_datetime(
            pd.read_parquet(paths["oi"], columns=["timestamp"])["timestamp"],
            errors="coerce",
        )
    else:
        oi["timestamp"] = pd.Series(pd.NaT, index=oi.index, dtype="datetime64[ns]")
    if "trade_date" in oi:
        oi["trade_date"] = oi["trade_date"].map(_day)
    required_values = [
        "symbol",
        "expiration",
        "right",
        "strike",
    ]
    if oi.empty or oi[required_values].isna().any().any():
        raise AssertionError("canonical OI has empty/invalid rows")
    if (
        not oi["symbol"].eq(ticker).all()
        or not oi["expiration"].eq(day).all()
        or ("trade_date" in oi and not oi["trade_date"].eq(day).all())
    ):
        raise AssertionError("canonical OI identity substitution")
    finite_oi = np.isfinite(oi["open_interest"])
    if (finite_oi & oi["open_interest"].lt(0)).any():
        raise AssertionError("canonical OI contains negative values")
    valid_oi_clock = oi["timestamp"].notna()
    if not oi.loc[valid_oi_clock, "timestamp"].dt.strftime("%Y%m%d").eq(day).all():
        raise AssertionError("canonical OI timestamp outside native day")
    cutoff = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]} {START_TIME}")
    late_oi = oi["timestamp"].gt(cutoff)
    oi_keys = ["symbol", "expiration", "strike", "right"]
    duplicate_oi_rows = int(oi.duplicated(oi_keys, keep=False).sum())
    if duplicate_oi_rows:
        raise AssertionError("canonical OI contains duplicate contract keys")
    after = {kind: sha256_file(path) for kind, path in paths.items()}
    if before != after:
        raise AssertionError("canonical source changed during inventory audit")
    return {
        "ticker": ticker,
        "trade_date": day,
        "greeks_path": str(paths["greeks"]),
        "greeks_sha256": before["greeks"],
        "greeks_rows": int(len(greeks)),
        "greeks_clock": greek_clock,
        "greeks_native_timestamp": bool(native_greek_timestamp),
        "greeks_underlying_timestamp_proxy": bool(not native_greek_timestamp),
        "greeks_first_timestamp": greeks[greek_clock].min().isoformat(),
        "greeks_last_timestamp": greeks[greek_clock].max().isoformat(),
        "oi_path": str(paths["oi"]),
        "oi_sha256": before["oi"],
        "oi_rows": int(len(oi)),
        "oi_first_timestamp": oi["timestamp"].min().isoformat()
        if valid_oi_clock.any()
        else None,
        "oi_last_timestamp": oi["timestamp"].max().isoformat()
        if valid_oi_clock.any()
        else None,
        "oi_zero_rows": int(oi["open_interest"].eq(0).sum()),
        "oi_positive_rows": int((finite_oi & oi["open_interest"].gt(0)).sum()),
        "oi_null_or_nonfinite_value_rows": int((~finite_oi).sum()),
        "oi_null_timestamp_rows": int((~valid_oi_clock).sum()),
        "oi_late_after_1019_rows": int(late_oi.sum()),
        "oi_negative_rows": 0,
        "oi_duplicate_contract_key_rows": duplicate_oi_rows,
    }


def freeze_source_inventory(
    *, options_root: str | Path, inventory_dir: str | Path
) -> dict[str, Any]:
    final = Path(inventory_dir).resolve()
    staging = final.with_name(final.name + ".staging")
    if final.exists() or staging.exists():
        raise FileExistsError(f"immutable source inventory exists: {final}")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    rows = [
        _audit_canonical_source_pair(
            ticker, day, canonical_source_paths(options_root, ticker, day)
        )
        for ticker, day in FROZEN_SESSIONS
    ]
    frame = pd.DataFrame(rows).sort_values(["ticker", "trade_date"], kind="stable")
    if len(frame) != 12 or set(zip(frame.ticker, frame.trade_date)) != set(
        FROZEN_SESSIONS
    ):
        raise AssertionError("canonical inventory is not the frozen 12-session set")
    staging.mkdir(parents=True, exist_ok=False)
    csv_path = staging / "source_inventory.csv"
    json_path = staging / "source_inventory.json"
    frame.to_csv(csv_path, index=False)
    json_path.write_bytes(canonical_json_bytes(frame.to_dict("records")))
    manifest = {
        "schema": "h_greek2wall_direct_all_source_inventory_v1",
        "status": "PASS_FROZEN_SOURCE_INVENTORY",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "sessions": 12,
        "options_root": str(Path(options_root).resolve()),
        "git_commit": current_git_commit(),
        "builder_sha256": sha256_file(__file__),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "source_clarification_sha256": sha256_file(SOURCE_CLARIFICATION),
        "direct_oi_amendment_sha256": sha256_file(DIRECT_OI_AMENDMENT),
        "remote_provenance_amendment_sha256": sha256_file(REMOTE_PROVENANCE_AMENDMENT),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "inventory_csv_sha256": sha256_file(csv_path),
        "inventory_json_sha256": sha256_file(json_path),
    }
    (staging / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    staging.rename(final)
    return manifest


def validate_source_inventory(inventory_dir: str | Path) -> pd.DataFrame:
    root = Path(inventory_dir).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    csv_path, json_path = root / "source_inventory.csv", root / "source_inventory.json"
    if (
        manifest.get("outcome_free") is not True
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("production_modified") is not False
        or manifest.get("sessions") != 12
        or manifest.get("status") != "PASS_FROZEN_SOURCE_INVENTORY"
    ):
        raise AssertionError("invalid frozen source inventory scope")
    if (
        sha256_file(csv_path) != manifest["inventory_csv_sha256"]
        or sha256_file(json_path) != manifest["inventory_json_sha256"]
    ):
        raise AssertionError("frozen source inventory artifact hash mismatch")
    if (
        sha256_file(__file__) != manifest["builder_sha256"]
        or sha256_file(PREDECLARATION) != manifest["predeclaration_sha256"]
        or sha256_file(SOURCE_CLARIFICATION) != manifest["source_clarification_sha256"]
        or sha256_file(DIRECT_OI_AMENDMENT) != manifest["direct_oi_amendment_sha256"]
        or sha256_file(REMOTE_PROVENANCE_AMENDMENT)
        != manifest["remote_provenance_amendment_sha256"]
    ):
        raise AssertionError("source inventory code/predeclaration mismatch")
    if not commit_is_ancestor(str(manifest.get("git_commit", ""))):
        raise AssertionError("source inventory build commit is not an ancestor of HEAD")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if (
        runtime["lock_sha256"] != manifest["runtime_lock_sha256"]
        or runtime["environment_sha256"] != manifest["runtime_environment_sha256"]
    ):
        raise AssertionError("source inventory runtime mismatch")
    frame = pd.read_csv(csv_path, dtype={"trade_date": str})
    json_records = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(json_records, list) or canonical_json_bytes(
        json_records
    ) != canonical_json_bytes(frame.to_dict("records")):
        raise AssertionError("frozen source inventory CSV/JSON disagreement")
    if len(frame) != 12 or set(zip(frame.ticker, frame.trade_date)) != set(
        FROZEN_SESSIONS
    ):
        raise AssertionError("frozen source inventory session substitution")
    for row in frame.to_dict("records"):
        paths = canonical_source_paths(
            manifest["options_root"], row["ticker"], row["trade_date"]
        )
        for kind in ("greeks", "oi"):
            if str(paths[kind]) != str(Path(row[f"{kind}_path"])):
                raise AssertionError(f"frozen {kind} path substitution")
            if sha256_file(paths[kind]) != row[f"{kind}_sha256"]:
                raise AssertionError(f"frozen {kind} source tampering")
    return frame


def capture_session(
    *,
    ticker: str,
    trade_date: str,
    source_inventory: str | Path,
    output_root: str | Path,
    base_url: str,
    terminal_jar: str | Path | None = None,
    timeout: float = 600,
    requester: Callable[..., Any] = requests.get,
    process_evidence_provider: Callable[
        ..., dict[str, Any]
    ] = local_terminal_process_evidence,
) -> dict[str, Any]:
    ticker, day = str(ticker).upper(), _day(trade_date)
    params = request_params(ticker, day)
    inventory = validate_source_inventory(source_inventory)
    selected = inventory[
        inventory["ticker"].eq(ticker) & inventory["trade_date"].eq(day)
    ]
    if len(selected) != 1:
        raise AssertionError(
            "frozen inventory does not resolve exactly one source session"
        )
    greeks_path = Path(selected.iloc[0]["greeks_path"])
    oi_path = Path(selected.iloc[0]["oi_path"])
    normalized_base = base_url.rstrip("/")
    host = (urlparse(normalized_base).hostname or "").lower()
    is_local = host in {
        "127.0.0.1",
        "localhost",
        "::1",
    }
    is_remote = normalized_base == REMOTE_BASE_URL
    if not is_local and not is_remote:
        raise AssertionError(
            "base URL is neither localhost nor the exact frozen remote Terminal"
        )
    remote_status_response = None
    remote_status_raw = b""
    if is_local:
        if terminal_jar is None:
            raise AssertionError("local capture requires terminal-jar")
        jar = Path(terminal_jar).resolve()
        if not jar.is_file():
            raise FileNotFoundError(jar)
        evidence = process_evidence_provider(normalized_base, jar)
        jar_hash = sha256_file(jar)
        if evidence.get("terminal_jar_sha256") != jar_hash:
            raise AssertionError("active JAR mismatch")
        historical_provenance = PROVENANCE
        live_parity = "BLOCKED_PENDING_PROSPECTIVE_PARITY"
    else:
        jar = None
        jar_hash = None
        remote_status_response = requester(
            normalized_base + REMOTE_STATUS_ENDPOINT,
            params={},
            headers={"Accept-Encoding": "identity"},
            timeout=timeout,
        )
        remote_status_response.raise_for_status()
        remote_status_raw = bytes(remote_status_response.content)
        if not remote_status_raw:
            raise AssertionError("empty remote Terminal status response")
        status_value = terminal_status_value(remote_status_raw)
        if status_value != "CONNECTED":
            raise AssertionError(f"remote Terminal MDDS is not CONNECTED: {status_value}")
        evidence = {
            "kind": REMOTE_EVIDENCE_KIND,
            "base_url": normalized_base,
            "status_endpoint": REMOTE_STATUS_ENDPOINT,
            "status_raw_sha256": sha256_bytes(remote_status_raw),
            "http_status": int(getattr(remote_status_response, "status_code", 200)),
            "http_headers": dict(
                sorted(
                    (str(k), str(v))
                    for k, v in getattr(remote_status_response, "headers", {}).items()
                )
            ),
            "server_date": str(
                getattr(remote_status_response, "headers", {}).get("Date", "")
            ),
            "status_value": status_value,
        }
        historical_provenance = REMOTE_PROVENANCE
        live_parity = "BLOCKED"
    final = session_directory(output_root, ticker, day)
    staging = final.with_name(final.name + ".staging")
    if final.exists() or staging.exists():
        raise FileExistsError(f"immutable session exists: {final}")
    source_paths = {"greeks": Path(greeks_path), "oi": Path(oi_path)}
    source_hashes = {k: sha256_file(v) for k, v in source_paths.items()}
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    response = requester(
        normalized_base + ENDPOINT,
        params=params,
        headers={"Accept-Encoding": "identity"},
        timeout=timeout,
    )
    response.raise_for_status()
    raw = bytes(response.content)
    if not raw:
        raise AssertionError("empty provider response")
    normalized = normalize_response(json.loads(raw), ticker=ticker, trade_date=day)
    oi_params = oi_request_params(ticker, day)
    oi_response = requester(
        normalized_base + OI_ENDPOINT,
        params=oi_params,
        headers={"Accept-Encoding": "identity"},
        timeout=timeout,
    )
    oi_response.raise_for_status()
    oi_raw = bytes(oi_response.content)
    if not oi_raw:
        raise AssertionError("empty direct OI provider response")
    direct_oi = normalize_direct_oi(json.loads(oi_raw), ticker=ticker, trade_date=day)
    audit = audit_sources(
        normalized, greeks_path=greeks_path, oi_path=oi_path, direct_oi=direct_oi
    )
    if any(sha256_file(path) != source_hashes[k] for k, path in source_paths.items()):
        raise AssertionError("source changed during capture")
    staging.mkdir(parents=True)
    raw_path = staging / "response.json"
    parquet = staging / "direct_all_greeks.parquet"
    oi_raw_path = staging / "oi_response.json"
    oi_parquet = staging / "direct_oi.parquet"
    raw_path.write_bytes(raw)
    normalized.to_parquet(parquet, index=False)
    oi_raw_path.write_bytes(oi_raw)
    direct_oi.to_parquet(oi_parquet, index=False)
    remote_status_path = staging / "remote_terminal_status.json"
    if is_remote:
        remote_status_path.write_bytes(remote_status_raw)
    schema = [
        (field.name, str(field.type)) for field in pq.ParquetFile(parquet).schema_arrow
    ]
    oi_schema = [
        (field.name, str(field.type))
        for field in pq.ParquetFile(oi_parquet).schema_arrow
    ]
    manifest = {
        "schema": "h_greek2wall_direct_all_preflight_session_v1",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "provenance": historical_provenance,
        "live_parity": live_parity,
        "base_url": normalized_base,
        "evidence_kind": evidence.get("kind", "LOCAL_FROZEN_JAR_PROCESS"),
        "ticker": ticker,
        "trade_date": day,
        "expiration": day,
        "endpoint": ENDPOINT,
        "request_params": params,
        "oi_endpoint": OI_ENDPOINT,
        "oi_request_params": oi_params,
        "source_inventory_path": str(Path(source_inventory).resolve()),
        "source_inventory_manifest_sha256": sha256_file(
            Path(source_inventory) / "manifest.json"
        ),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": current_git_commit(),
        "builder_sha256": sha256_file(__file__),
        "predeclaration_sha256": sha256_file(PREDECLARATION),
        "source_clarification_sha256": sha256_file(SOURCE_CLARIFICATION),
        "direct_oi_amendment_sha256": sha256_file(DIRECT_OI_AMENDMENT),
        "remote_provenance_amendment_sha256": sha256_file(REMOTE_PROVENANCE_AMENDMENT),
        "runtime_lock_sha256": runtime["lock_sha256"],
        "runtime_environment_sha256": runtime["environment_sha256"],
        "terminal_jar_path": str(jar) if jar is not None else None,
        "terminal_jar_sha256": jar_hash,
        "terminal_process_evidence": evidence,
        "remote_status_raw_sha256": sha256_bytes(remote_status_raw)
        if is_remote
        else None,
        "greeks_http_status": int(getattr(response, "status_code", 200)),
        "greeks_http_headers": dict(
            sorted(
                (str(k), str(v)) for k, v in getattr(response, "headers", {}).items()
            )
        ),
        "greeks_server_date": str(getattr(response, "headers", {}).get("Date", "")),
        "oi_http_status": int(getattr(oi_response, "status_code", 200)),
        "oi_http_headers": dict(
            sorted(
                (str(k), str(v)) for k, v in getattr(oi_response, "headers", {}).items()
            )
        ),
        "oi_server_date": str(getattr(oi_response, "headers", {}).get("Date", "")),
        "raw_response_sha256": sha256_bytes(raw),
        "parquet_sha256": sha256_file(parquet),
        "oi_raw_response_sha256": sha256_bytes(oi_raw),
        "oi_parquet_sha256": sha256_file(oi_parquet),
        "oi_rows": int(len(direct_oi)),
        "raw_bytes": len(raw),
        "parquet_bytes": parquet.stat().st_size,
        "oi_raw_bytes": len(oi_raw),
        "oi_parquet_bytes": oi_parquet.stat().st_size,
        "rows": len(normalized),
        "first_timestamp": normalized.timestamp.min().isoformat(),
        "last_timestamp": normalized.timestamp.max().isoformat(),
        "response_schema": schema,
        "response_schema_sha256": sha256_bytes(canonical_json_bytes(schema)),
        "oi_response_schema": oi_schema,
        "oi_response_schema_sha256": sha256_bytes(canonical_json_bytes(oi_schema)),
        "field_profiles": field_profiles(normalized),
        **{
            f"source_{name}_path": str(path.resolve())
            for name, path in source_paths.items()
        },
        **audit,
    }
    (staging / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    staging.rename(final)
    return manifest


def validate_session(
    path: str | Path, *, source_inventory: str | Path
) -> dict[str, Any]:
    root = Path(path)
    manifest = json.loads((root / "manifest.json").read_text())
    if (
        manifest.get("outcome_free") is not True
        or manifest.get("holdout_2026_used") is not False
        or manifest.get("production_modified") is not False
        or manifest.get("provenance") not in {PROVENANCE, REMOTE_PROVENANCE}
    ):
        raise AssertionError("invalid scope/provenance")
    expected_request = request_params(manifest["ticker"], manifest["trade_date"])
    inventory_root = Path(source_inventory).resolve()
    inventory = validate_source_inventory(inventory_root)
    selected = inventory[
        inventory["ticker"].eq(manifest["ticker"])
        & inventory["trade_date"].eq(manifest["trade_date"])
    ]
    if len(selected) != 1:
        raise AssertionError("source inventory session resolution mismatch")
    greeks_path = Path(selected.iloc[0]["greeks_path"])
    oi_path = Path(selected.iloc[0]["oi_path"])
    if (
        manifest.get("endpoint") != ENDPOINT
        or manifest.get("request_params") != expected_request
        or manifest.get("oi_endpoint") != OI_ENDPOINT
        or manifest.get("oi_request_params")
        != oi_request_params(manifest["ticker"], manifest["trade_date"])
        or _day(manifest.get("expiration")) != _day(manifest["trade_date"])
    ):
        raise AssertionError("manifest request/endpoint differs from frozen contract")
    if str(Path(manifest.get("source_inventory_path", "")).resolve()) != str(
        inventory_root
    ) or manifest.get("source_inventory_manifest_sha256") != sha256_file(
        inventory_root / "manifest.json"
    ):
        raise AssertionError("session source inventory substitution")
    if len(str(manifest.get("git_commit", ""))) != 40:
        raise AssertionError("invalid build commit provenance")
    raw = (root / "response.json").read_bytes()
    parquet = root / "direct_all_greeks.parquet"
    oi_raw = (root / "oi_response.json").read_bytes()
    oi_parquet = root / "direct_oi.parquet"
    if (
        sha256_bytes(raw) != manifest["raw_response_sha256"]
        or sha256_file(parquet) != manifest["parquet_sha256"]
        or sha256_bytes(oi_raw) != manifest["oi_raw_response_sha256"]
        or sha256_file(oi_parquet) != manifest["oi_parquet_sha256"]
    ):
        raise AssertionError("artifact hash mismatch")
    rebuilt = normalize_response(
        json.loads(raw), ticker=manifest["ticker"], trade_date=manifest["trade_date"]
    )
    pd.testing.assert_frame_equal(pd.read_parquet(parquet), rebuilt)
    direct_oi = normalize_direct_oi(
        json.loads(oi_raw), ticker=manifest["ticker"], trade_date=manifest["trade_date"]
    )
    pd.testing.assert_frame_equal(pd.read_parquet(oi_parquet), direct_oi)
    audit = audit_sources(
        rebuilt, greeks_path=greeks_path, oi_path=oi_path, direct_oi=direct_oi
    )
    source_arguments = {"greeks": Path(greeks_path), "oi": Path(oi_path)}
    for name in ("greeks", "oi"):
        if str(Path(manifest[f"source_{name}_path"]).resolve()) != str(
            source_arguments[name].resolve()
        ):
            raise AssertionError(f"sealed {name} source path substitution")
        if audit[f"source_{name}_sha256"] != manifest[f"source_{name}_sha256"]:
            raise AssertionError(f"sealed {name} source hash mismatch")
    for key, value in audit.items():
        if manifest.get(key) != value:
            raise AssertionError(f"stored parity audit mismatch: {key}")
    if manifest.get("field_profiles") != field_profiles(rebuilt):
        raise AssertionError("stored field profiles mismatch")
    if sha256_file(PREDECLARATION) != manifest["predeclaration_sha256"]:
        raise AssertionError("predeclaration changed")
    if sha256_file(SOURCE_CLARIFICATION) != manifest["source_clarification_sha256"]:
        raise AssertionError("source clarification changed")
    if sha256_file(DIRECT_OI_AMENDMENT) != manifest["direct_oi_amendment_sha256"]:
        raise AssertionError("direct OI amendment changed")
    if (
        sha256_file(REMOTE_PROVENANCE_AMENDMENT)
        != manifest["remote_provenance_amendment_sha256"]
    ):
        raise AssertionError("remote provenance amendment changed")
    if sha256_file(__file__) != manifest["builder_sha256"]:
        raise AssertionError("builder changed")
    evidence = manifest.get("terminal_process_evidence")
    required_evidence = {
        "process_id",
        "command_line",
        "executable_path",
        "executable_sha256",
        "local_address",
        "local_port",
        "terminal_jar_path",
        "terminal_jar_sha256",
    }
    if manifest["provenance"] == REMOTE_PROVENANCE:
        status_path = root / "remote_terminal_status.json"
        if (
            manifest.get("base_url") != REMOTE_BASE_URL
            or manifest.get("evidence_kind") != REMOTE_EVIDENCE_KIND
            or manifest.get("live_parity") != "BLOCKED"
            or not isinstance(evidence, dict)
            or evidence.get("kind") != REMOTE_EVIDENCE_KIND
            or evidence.get("base_url") != REMOTE_BASE_URL
            or evidence.get("status_endpoint") != REMOTE_STATUS_ENDPOINT
            or int(evidence.get("http_status", 0)) != 200
            or not evidence.get("server_date")
            or evidence.get("status_value") != "CONNECTED"
            or terminal_status_value(status_path.read_bytes()) != "CONNECTED"
            or sha256_file(status_path) != manifest["remote_status_raw_sha256"]
            or evidence.get("status_raw_sha256") != manifest["remote_status_raw_sha256"]
            or manifest.get("terminal_jar_path") is not None
            or manifest.get("terminal_jar_sha256") is not None
        ):
            raise AssertionError("invalid remote Terminal provenance evidence")
    else:
        if (
            sha256_file(manifest["terminal_jar_path"])
            != manifest["terminal_jar_sha256"]
        ):
            raise AssertionError("JAR changed")
        if (
            not isinstance(evidence, dict)
            or not required_evidence.issubset(evidence)
            or evidence.get("terminal_jar_sha256") != manifest["terminal_jar_sha256"]
            or int(evidence.get("process_id", 0)) <= 0
            or int(evidence.get("local_port", 0)) <= 0
        ):
            raise AssertionError("invalid Terminal process evidence")
    runtime = assert_runtime_lock(ENVIRONMENT_LOCK)
    if (
        int(manifest.get("greeks_http_status", 0)) != 200
        or int(manifest.get("oi_http_status", 0)) != 200
        or not isinstance(manifest.get("greeks_http_headers"), dict)
        or not isinstance(manifest.get("oi_http_headers"), dict)
    ):
        raise AssertionError("invalid provider HTTP evidence")
    if (
        runtime["lock_sha256"] != manifest["runtime_lock_sha256"]
        or runtime["environment_sha256"] != manifest["runtime_environment_sha256"]
    ):
        raise AssertionError("runtime provenance mismatch")
    schema = [
        (field.name, str(field.type)) for field in pq.ParquetFile(parquet).schema_arrow
    ]
    if sha256_bytes(canonical_json_bytes(schema)) != manifest["response_schema_sha256"]:
        raise AssertionError("response schema hash mismatch")
    oi_schema = [
        (field.name, str(field.type))
        for field in pq.ParquetFile(oi_parquet).schema_arrow
    ]
    if (
        sha256_bytes(canonical_json_bytes(oi_schema))
        != manifest["oi_response_schema_sha256"]
    ):
        raise AssertionError("direct OI response schema hash mismatch")
    return manifest


def projected_cost(manifests: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(manifests)
    if len(rows) != 12 or {(r["ticker"], r["trade_date"]) for r in rows} != set(
        FROZEN_SESSIONS
    ):
        raise AssertionError("cost projection requires exactly the frozen 12 sessions")
    return {
        "preflight_sessions": 12,
        "projected_sessions": 2519,
        "preflight_raw_gib": sum(r["raw_bytes"] for r in rows) / 2**30,
        "preflight_parquet_gib": sum(r["parquet_bytes"] for r in rows) / 2**30,
        "preflight_oi_raw_gib": sum(r["oi_raw_bytes"] for r in rows) / 2**30,
        "preflight_oi_parquet_gib": sum(r["oi_parquet_bytes"] for r in rows) / 2**30,
        "projected_raw_gib": np.mean([r["raw_bytes"] for r in rows]) * 2519 / 2**30,
        "projected_parquet_gib": np.mean([r["parquet_bytes"] for r in rows])
        * 2519
        / 2**30,
        "projected_oi_raw_gib": np.mean([r["oi_raw_bytes"] for r in rows])
        * 2519
        / 2**30,
        "projected_oi_parquet_gib": np.mean([r["oi_parquet_bytes"] for r in rows])
        * 2519
        / 2**30,
        "projected_total_gib": np.mean(
            [
                r["raw_bytes"]
                + r["parquet_bytes"]
                + r["oi_raw_bytes"]
                + r["oi_parquet_bytes"]
                for r in rows
            ]
        )
        * 2519
        / 2**30,
    }


def seal_preflight(
    *, source_inventory: str | Path, output_root: str | Path
) -> dict[str, Any]:
    """Revalidate and seal exactly the twelve frozen feasibility sessions."""
    source_frame = validate_source_inventory(source_inventory)
    inventory = source_frame.to_dict("records")
    root = Path(output_root)
    final = root / "_seal"
    staging = root / "_seal.staging"
    if final.exists() or staging.exists():
        raise FileExistsError(f"immutable preflight seal exists: {final}")
    records: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    for row in sorted(
        inventory, key=lambda value: (value["ticker"], value["trade_date"])
    ):
        ticker, day = str(row["ticker"]).upper(), _day(row["trade_date"])
        directory = session_directory(root, ticker, day).resolve()
        greek_path = Path(row["greeks_path"]).resolve()
        oi_path = Path(row["oi_path"]).resolve()
        manifest = validate_session(directory, source_inventory=source_inventory)
        if (manifest["ticker"], manifest["trade_date"]) != (ticker, day):
            raise AssertionError(
                "session directory identity differs from seal inventory"
            )
        evidence = manifest["terminal_process_evidence"]
        if (
            manifest["provenance"] != REMOTE_PROVENANCE
            and int(evidence.get("process_id", 0)) <= 0
        ):
            raise AssertionError("invalid Terminal process id in session evidence")
        manifest_path = directory / "manifest.json"
        records.append(
            {
                "ticker": ticker,
                "trade_date": day,
                "session_dir": str(directory),
                "session_manifest_sha256": sha256_file(manifest_path),
                "raw_response_sha256": manifest["raw_response_sha256"],
                "parquet_sha256": manifest["parquet_sha256"],
                "oi_raw_response_sha256": manifest["oi_raw_response_sha256"],
                "oi_parquet_sha256": manifest["oi_parquet_sha256"],
                "rows": int(manifest["rows"]),
                "raw_bytes": int(manifest["raw_bytes"]),
                "parquet_bytes": int(manifest["parquet_bytes"]),
                "oi_raw_bytes": int(manifest["oi_raw_bytes"]),
                "oi_parquet_bytes": int(manifest["oi_parquet_bytes"]),
                "greeks_path": str(greek_path),
                "greeks_sha256": manifest["source_greeks_sha256"],
                "oi_path": str(oi_path),
                "oi_sha256": manifest["source_oi_sha256"],
                "git_commit": manifest["git_commit"],
                "builder_sha256": manifest["builder_sha256"],
                "predeclaration_sha256": manifest["predeclaration_sha256"],
                "source_clarification_sha256": manifest["source_clarification_sha256"],
                "direct_oi_amendment_sha256": manifest["direct_oi_amendment_sha256"],
                "remote_provenance_amendment_sha256": manifest[
                    "remote_provenance_amendment_sha256"
                ],
                "runtime_lock_sha256": manifest["runtime_lock_sha256"],
                "runtime_environment_sha256": manifest["runtime_environment_sha256"],
                "terminal_jar_sha256": manifest["terminal_jar_sha256"],
                "terminal_process_id": int(evidence["process_id"])
                if "process_id" in evidence
                else None,
                "provenance": manifest["provenance"],
                "base_url": manifest["base_url"],
                "evidence_kind": manifest["evidence_kind"],
                "remote_status_raw_sha256": manifest["remote_status_raw_sha256"],
            }
        )
        manifests.append(manifest)
    invariant_fields = (
        "git_commit",
        "builder_sha256",
        "predeclaration_sha256",
        "source_clarification_sha256",
        "direct_oi_amendment_sha256",
        "remote_provenance_amendment_sha256",
        "runtime_lock_sha256",
        "runtime_environment_sha256",
        "terminal_jar_sha256",
        "provenance",
        "base_url",
        "evidence_kind",
    )
    for field in invariant_fields:
        if len({str(record[field]) for record in records}) != 1:
            raise AssertionError(
                f"preflight sessions disagree on frozen provenance: {field}"
            )
    profiles = []
    for manifest in manifests:
        year = str(manifest["trade_date"])[:4]
        profiles.extend(
            {"ticker": manifest["ticker"], "year": year, **profile}
            for profile in manifest["field_profiles"]
        )
    costs = projected_cost(manifests)
    staging.mkdir(parents=True, exist_ok=False)
    index = pd.DataFrame(records).sort_values(["ticker", "trade_date"], kind="stable")
    index_path = staging / "session_index.csv"
    profile_path = staging / "ticker_year_field_profiles.csv"
    index.to_csv(index_path, index=False)
    pd.DataFrame(profiles).sort_values(
        ["ticker", "year", "field"], kind="stable"
    ).to_csv(profile_path, index=False)
    seal = {
        "schema": "h_greek2wall_direct_all_preflight_seal_v1",
        "status": "PASS_12_SESSION_CAPTURE",
        "outcome_free": True,
        "holdout_2026_used": False,
        "production_modified": False,
        "provenance": PROVENANCE,
        "sessions": 12,
        "sessions_by_ticker": {ticker: 4 for ticker in ("SPXW", "QQQ", "SPY")},
        "frozen_sessions": [list(key) for key in FROZEN_SESSIONS],
        "source_inventory_path": str(Path(source_inventory).resolve()),
        "source_inventory_manifest_sha256": sha256_file(
            Path(source_inventory) / "manifest.json"
        ),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        **{field: records[0][field] for field in invariant_fields},
        **costs,
        "rows": int(index["rows"].sum()),
        "session_index_sha256": sha256_file(index_path),
        "ticker_year_field_profiles_sha256": sha256_file(profile_path),
    }
    (staging / "manifest.json").write_bytes(canonical_json_bytes(seal))
    staging.rename(final)
    return seal


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch-session")
    fetch.add_argument("--ticker", required=True)
    fetch.add_argument("--date", required=True)
    fetch.add_argument("--source-inventory", required=True)
    fetch.add_argument("--output-root", required=True)
    fetch.add_argument("--terminal-jar")
    fetch.add_argument("--base-url", default="http://127.0.0.1:25503/v3")
    freeze = sub.add_parser("freeze-source-inventory")
    freeze.add_argument("--options-root", required=True)
    freeze.add_argument("--inventory-dir", required=True)
    seal = sub.add_parser("seal-preflight")
    seal.add_argument("--source-inventory", required=True)
    seal.add_argument("--output-root", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "fetch-session":
        result = capture_session(
            ticker=args.ticker,
            trade_date=args.date,
            source_inventory=args.source_inventory,
            output_root=args.output_root,
            base_url=args.base_url,
            terminal_jar=args.terminal_jar,
        )
    elif args.command == "freeze-source-inventory":
        result = freeze_source_inventory(
            options_root=args.options_root, inventory_dir=args.inventory_dir
        )
    else:
        result = seal_preflight(
            source_inventory=args.source_inventory, output_root=args.output_root
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
