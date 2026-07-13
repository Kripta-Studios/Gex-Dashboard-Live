"""Outcome-free exact-join inventory for EXISTING_DATA_EXECUTABLE_UTILITY_V1.

This audit reads only Parquet schemas, identity/current-time columns, and
date/key coverage.  It never reads executable returns, wins, labels, future
prices, physical outcomes, or 2024/2025 economic metrics.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "tmp/event_option_dataset_execquote_causal1030_202201_202512_pairwise_v1/event_option_dataset.parquet"
E0_MANIFEST = ROOT / "research_papers/JEPA/results/_diagnostics/pairwise_opportunity_side_v1r1_hold_fix/feature_manifest.json"
LEGACY = ROOT / "training_data/training_data_spx_qqq_spy.parquet"
WALL_STATE = ROOT / "tmp/wall_state_gex_dex_202201_202512_v1/wall_state.parquet"
HFLOW = ROOT / "tmp/wall_surface_flow_at_touch_202208_202512_v1r2r1/wall_surface_flow_at_touch.parquet"
IVSURF = ROOT / "tmp/wall_iv_surface_deformation_at_touch_202208_202512_v1r1/wall_iv_surface_deformation_at_touch.parquet"
QSIZE = ROOT / "tmp/wall_quote_size_pressure_at_touch_202208_202512_v1r1/wall_quote_size_pressure_at_touch.parquet"
IBQDYN = ROOT / "tmp/h_ibqdyn1_features_202208_202512_v1r2/h_ibqdyn1_features.parquet"
QDYN = ROOT / "tmp/wall_quote_tick_dynamics_at_touch_202208_202512_v1r1r1/wall_quote_tick_dynamics_at_touch.parquet"
IB_FREEZE = ROOT / "research_papers/JEPA/results/_diagnostics/h_ibqdyn1_physical_202208_202512_v1_frozen_runner/manifest.json"

KEY = ["ticker", "trade_date", "minute"]
FORBIDDEN_ALPHA_TOKENS = ("future", "label", "outcome", "target", "exit", "pnl", "opt_win")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_ordered(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parquet_meta(path: Path) -> dict[str, Any]:
    parquet = pq.ParquetFile(path)
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "rows": parquet.metadata.num_rows,
        "columns": len(parquet.schema_arrow.names),
    }


def day(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("-", "", regex=False).str[:8]


def read_master_keys() -> pd.DataFrame:
    frame = pd.read_parquet(MASTER, columns=[*KEY, "timestamp", "spot"])
    frame["trade_date"] = day(frame["trade_date"])
    if frame.duplicated(KEY).any():
        raise AssertionError("master executable keys are not unique")
    return frame


def read_block_keys(path: Path, *, clock: str, extras: list[str]) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=[*KEY, "spot", clock, *extras])
    frame["trade_date"] = day(frame["trade_date"])
    return frame


def key_profile(block: pd.DataFrame, master: pd.DataFrame) -> dict[str, Any]:
    multiplicity = block.groupby(KEY, observed=True).size()
    unique = block[KEY].drop_duplicates()
    matched = unique.merge(master[KEY], on=KEY, how="inner", validate="one_to_one")
    compared = block.merge(master[[*KEY, "spot"]], on=KEY, how="inner", suffixes=("_block", "_master"))
    spot_diff = (compared["spot_block"] - compared["spot_master"]).abs()
    return {
        "rows": len(block),
        "unique_decision_keys": len(unique),
        "matched_master_keys": len(matched),
        "decision_keys_with_multiplicity_gt_1": int(multiplicity.gt(1).sum()),
        "maximum_decision_key_multiplicity": int(multiplicity.max()),
        "duplicate_source_rows_on_decision_key": int(block.duplicated(KEY, keep=False).sum()),
        "date_min": str(block["trade_date"].min()),
        "date_max": str(block["trade_date"].max()),
        "rows_by_ticker": {str(k): int(v) for k, v in block.groupby("ticker", observed=True).size().items()},
        "maximum_absolute_spot_difference": float(spot_diff.max()) if len(spot_diff) else None,
    }


def literal_assignment(path: Path, name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
            value = ast.literal_eval(node.value)
            return list(value)
    raise KeyError(f"{name} not found in {path}")


def build_inventory() -> dict[str, Any]:
    master = read_master_keys()
    master_ge635 = master[master["minute"].ge(635)].copy()
    e0_manifest = json.loads(E0_MANIFEST.read_text(encoding="utf-8"))
    e0 = list(e0_manifest["features"])

    master_columns = pq.ParquetFile(MASTER).schema_arrow.names
    excluded_pairphys = {
        "phys_event_seq_in_day", "phys_event_frac_in_day", "phys_minutes_since_first_event",
        "phys_spot_ret_from_first_event_bps", "phys_same_day_event_count",
    }
    pairphys = [
        column for column in master_columns
        if (column.startswith("phys_") and column not in excluded_pairphys)
        or (column.startswith("ctx_") and not column.endswith("_spot"))
    ]
    legacy = literal_assignment(ROOT / "neural/hybrid_model.py", "FEATURE_COLUMNS")
    wall_schema = pq.ParquetFile(WALL_STATE).schema_arrow.names
    wall_state_features = [
        column for column in wall_schema
        if column not in {"ticker", "trade_date", "dt", "spot", "minute"}
    ]
    ib_freeze = json.loads(IB_FREEZE.read_text(encoding="utf-8"))
    ib_f1 = list(ib_freeze["feature_names"]["F1"])

    hflow = read_block_keys(HFLOW, clock="decision_dt", extras=["episode_id", "wall_identity"])
    ivsurf = read_block_keys(IVSURF, clock="decision_dt", extras=["episode_id", "wall_identity"])
    qsize = read_block_keys(QSIZE, clock="decision_dt", extras=["episode_id", "wall_identity"])
    ibqdyn = read_block_keys(IBQDYN, clock="decision_dt", extras=["event_id", "wall_identity", "nearest_level_name"])
    wall = read_block_keys(WALL_STATE, clock="dt", extras=[])

    legacy_keys = pd.read_parquet(LEGACY, columns=["ticker", "date", "time", "spot_price"])
    legacy_keys = legacy_keys[day(legacy_keys["date"]).le("20251231")].copy()
    legacy_keys["ticker"] = legacy_keys["ticker"].replace({"SPX": "SPXW"})
    legacy_keys["trade_date"] = day(legacy_keys["date"])
    parts = legacy_keys["time"].astype(str).str.split(":")
    legacy_keys["minute"] = parts.str[0].astype(int) * 60 + parts.str[1].astype(int)
    if legacy_keys.duplicated(KEY).any():
        raise AssertionError("legacy live feature keys are not unique")
    legacy_join = master_ge635.merge(
        legacy_keys[[*KEY, "spot_price"]], on=KEY, how="left", validate="one_to_one", indicator=True
    )
    legacy_spot_bps = (
        (legacy_join["spot"] - legacy_join["spot_price"]).abs() / legacy_join["spot"] * 10_000.0
    )

    prefixed_pairphys = [f"pairphys__{column}" for column in pairphys]
    prefixed_legacy = [f"legacy__{column}" for column in legacy]
    prefixed_wall = [f"wallstate__{column}" for column in wall_state_features]
    prefixed_ib = [f"ibqdyn__{column}" for column in ib_f1]
    e1 = [
        *e0,
        *prefixed_pairphys,
        *prefixed_legacy,
        "wallstate__applicable",
        *prefixed_wall,
        "ibqdyn__applicable",
        *prefixed_ib,
    ]
    if len(e1) != len(set(e1)):
        raise AssertionError("recommended E1 feature names collide")
    forbidden = [name for name in e1 if any(token in name.lower() for token in FORBIDDEN_ALPHA_TOKENS)]
    if forbidden:
        raise AssertionError(f"forbidden alpha names in E1: {forbidden}")

    outcome_templates = [
        f"{right}_d{{bucket:02d}}_{suffix}"
        for right in ("call", "put")
        for suffix in ("opt_exit_ret", "opt_exit_minutes", "opt_win", "opt_status", "opt_max_ret", "opt_min_ret")
    ]
    block_profiles = {
        "base_pairwise_e0": {
            "classification": "EXACT_JOIN_AVAILABLE",
            "join": "self/master; one row per (ticker,trade_date,minute)",
            "feature_count": len(e0),
            "features": e0,
            "legacy_pairwise_sorted_csv_sha256": e0_manifest["feature_hash"],
            "ordered_json_sha256": hash_ordered(e0),
            "geometry": {"applicable_minute": ">=635", "not_applicable_master_rows_minute_630": int(master["minute"].eq(630).sum())},
        },
        "pairwise_current_time_physics_context": {
            "classification": "EXACT_JOIN_AVAILABLE",
            "join": "self/master",
            "feature_count": len(pairphys),
            "features": pairphys,
            "ordered_json_sha256": hash_ordered(pairphys),
            "excluded": sorted(excluded_pairphys),
        },
        "legacy_live_feature_surface": {
            "classification": "EXACT_JOIN_AVAILABLE",
            "join": "exact (ticker mapped SPX->SPXW,date,time->minute); no as-of/floor/nearest",
            "feature_count": len(legacy),
            "features": legacy,
            "ordered_json_sha256": hash_ordered(legacy),
            "matched_pairwise_modeling_rows": int(legacy_join["_merge"].eq("both").sum()),
            "source_missing_rows": int(legacy_join["_merge"].ne("both").sum()),
            "source_missing_range": ["20220103", "20220729"],
            "missing_policy": "retain master rows and null feature values; never zero-fill; train-only imputation only",
            "spot_difference_bps_max": float(legacy_spot_bps.max()),
        },
        "wall_state_gex_dex_dgex": {
            "classification": "EXACT_JOIN_AVAILABLE",
            "join": "exact one-to-one (ticker,trade_date,minute)",
            "profile": key_profile(wall, master),
            "timestamp_state_feature_count": len(wall_state_features),
            "timestamp_state_features": wall_state_features,
            "ordered_json_sha256": hash_ordered(wall_state_features),
            "not_applicable_master_rows": int(len(master) - len(master_ge635)),
            "not_applicable_reason": "frozen Pairwise/wall-state geometry begins 10:35; source is not missing",
            "candidate_physical_features": "UNSAFE_JOIN and excluded: candidate_* requires wall_identity and creates one-to-many rows",
        },
        "h_flow1": {
            "classification": "UNSAFE_JOIN",
            "profile": key_profile(hflow, master),
            "reason": "touch-event source has one-to-many decision keys and master has no wall_identity; aggregation was never frozen",
        },
        "h_ivsurf1": {
            "classification": "UNSAFE_JOIN",
            "profile": key_profile(ivsurf, master),
            "reason": "touch-event source has one-to-many decision keys and master has no wall_identity; aggregation was never frozen",
        },
        "h_qsize1r1": {
            "classification": "UNSAFE_JOIN",
            "profile": key_profile(qsize, master),
            "reason": "touch-event source has one-to-many decision keys and master has no wall_identity; aggregation was never frozen",
        },
        "h_ibqdyn1": {
            "classification": "NOT_APPLICABLE_BY_CAUSAL_GEOMETRY",
            "profile": key_profile(ibqdyn, master),
            "join_when_applicable": "exact one-to-one (ticker,trade_date,minute); event_id is unique but not required",
            "frozen_f1_feature_count": len(ib_f1),
            "frozen_f1_features": ib_f1,
            "frozen_f1_hash": ib_freeze["feature_hashes"]["F1"],
            "not_applicable_master_rows": int(len(master) - len(ibqdyn)),
            "missing_policy": "one causal applicability flag; retain nulls outside geometry; never zero-fill",
            "live_parity_caveat": ib_freeze["live_feature_parity_status"],
        },
        "h_qdyn1": {
            "classification": "UNSAFE_JOIN",
            "reason": "explicitly excluded and REJECTED_DATA_GATE; do not reuse any fields",
        },
        "h_greek2wall": {
            "classification": "SOURCE_MISSING",
            "reason": "BLOCKED_SOURCE_ENTITLEMENT; no direct all-Greeks data exist",
        },
        "executable_option_path_summaries": {
            "classification": "EXACT_JOIN_AVAILABLE",
            "role": "targets/execution diagnostics only; never alpha",
            "selected_bucket_by_ticker": {"SPXW": 25, "QQQ": 35, "SPY": 35},
            "column_templates": outcome_templates,
            "path_note": "master stores executable ask-to-bid path summaries; the intrapath quote sequence is not embedded",
        },
    }
    return {
        "schema": "existing_data_edge_join_inventory_v1",
        "outcomes_read": False,
        "economic_metrics_read": False,
        "date_counts_only_for_2024_2025": True,
        "hash_method_for_ordered_lists": "sha256(UTF-8 compact JSON array, order preserved)",
        "master": {
            **parquet_meta(MASTER),
            "join_key": KEY,
            "unique_keys": len(master),
            "rows_by_ticker": {str(k): int(v) for k, v in master.groupby("ticker", observed=True).size().items()},
            "date_min": str(master["trade_date"].min()),
            "date_max": str(master["trade_date"].max()),
            "pairwise_modeling_rows_minute_ge_635": len(master_ge635),
            "master_rows_preserved": True,
        },
        "sources": {
            name: parquet_meta(path)
            for name, path in {
                "legacy_live": LEGACY, "wall_state": WALL_STATE, "h_flow1": HFLOW,
                "h_ivsurf1": IVSURF, "h_qsize1r1": QSIZE, "h_ibqdyn1": IBQDYN,
                "h_qdyn1_rejected": QDYN,
            }.items()
        },
        "blocks": block_profiles,
        "recommended_arms": {
            "E0": {"feature_count": len(e0), "features": e0, "ordered_json_sha256": hash_ordered(e0)},
            "E1": {
                "feature_count": len(e1), "features": e1, "ordered_json_sha256": hash_ordered(e1),
                "prefixes": ["pairphys__", "legacy__", "wallstate__", "ibqdyn__"],
                "applicability_flags": ["wallstate__applicable", "ibqdyn__applicable"],
            },
        },
    }


def render_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Existing-data exact-join audit V1", "",
        "Outcome-free audit: no executable return, win, label, future price, physical outcome, or 2024/2025 economic metric was read.", "",
        f"Master: `{inventory['master']['path']}`; {inventory['master']['rows']:,} unique rows; SHA `{inventory['master']['sha256']}`.", "",
        "| Block | Classification | Exact evidence |", "| --- | --- | --- |",
    ]
    for name, block in inventory["blocks"].items():
        profile = block.get("profile", {})
        evidence = block.get("reason") or block.get("join") or block.get("join_when_applicable") or block.get("role", "")
        if profile:
            evidence += f"; rows={profile['rows']:,}, unique keys={profile['unique_decision_keys']:,}, multi-keys={profile['decision_keys_with_multiplicity_gt_1']:,}"
        lines.append(f"| `{name}` | `{block['classification']}` | {evidence} |")
    e0 = inventory["recommended_arms"]["E0"]
    e1 = inventory["recommended_arms"]["E1"]
    lines.extend([
        "", "## Freeze-ready arms", "",
        f"- E0: {e0['feature_count']} fields; ordered-list SHA `{e0['ordered_json_sha256']}`.",
        f"- E1: {e1['feature_count']} fields; ordered-list SHA `{e1['ordered_json_sha256']}`.",
        "- E1 preserves all master rows, prefixes joined fields, leaves source-missing/not-applicable values null, and uses only the two declared applicability flags.",
        "- H-FLOW1/H-IVSURF1/H-QSIZE1R1 are omitted rather than aggregated; H-QDYN1 and H-GREEK2 are omitted entirely.",
        "", "The full ordered lists and exact source hashes are in `join_feature_inventory_v1.json`.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="tmp/existing_data_edge_sprint_v1")
    args = parser.parse_args()
    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory()
    json_path = output / "join_feature_inventory_v1.json"
    md_path = output / "JOIN_FEATURE_INVENTORY_V1.md"
    json_path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(inventory), encoding="utf-8")
    print(json.dumps({
        "json": str(json_path.relative_to(ROOT)), "json_sha256": sha256_file(json_path),
        "markdown": str(md_path.relative_to(ROOT)), "markdown_sha256": sha256_file(md_path),
        "e0_sha256": inventory["recommended_arms"]["E0"]["ordered_json_sha256"],
        "e1_sha256": inventory["recommended_arms"]["E1"]["ordered_json_sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
