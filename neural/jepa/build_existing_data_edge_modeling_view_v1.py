"""Build the one permitted temporary existing-data modeling view.

The view is outcome-free.  It is a reproducible exact-key assembly of the
already-built blocks frozen by ``audit_existing_data_edge_join_inventory_v1``.
It never performs an as-of, nearest-strike, or floor-time join and never writes
outside ``tmp/existing_data_edge_sprint_v1``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from neural.jepa.audit_existing_data_edge_join_inventory_v1 import (
    IBQDYN,
    LEGACY,
    MASTER,
    ROOT,
    WALL_STATE,
    day,
    hash_ordered,
    sha256_file,
)
from neural.jepa.walkforward_pairwise_opportunity_side import build_diff_features


KEY = ["ticker", "trade_date", "minute"]
OUTPUT_ROOT = ROOT / "tmp/existing_data_edge_sprint_v1"
DEFAULT_INVENTORY = OUTPUT_ROOT / "join_feature_inventory_v1.json"
DEFAULT_VIEW = OUTPUT_ROOT / "modeling_view_features.parquet"
DEFAULT_MANIFEST = OUTPUT_ROOT / "modeling_view_manifest.json"


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _assert_under_output(path: Path) -> None:
    resolved = path.resolve()
    root = OUTPUT_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise AssertionError(f"temporary output must remain under {_relative(OUTPUT_ROOT)}")


def _load_inventory(path: Path) -> dict[str, Any]:
    inventory = json.loads(path.read_text(encoding="utf-8"))
    if inventory.get("outcomes_read") is not False:
        raise AssertionError("join inventory is not outcome-free")
    for source_name, source_path in {
        "legacy_live": LEGACY,
        "wall_state": WALL_STATE,
        "h_ibqdyn1": IBQDYN,
    }.items():
        expected = inventory["sources"][source_name]["sha256"]
        actual = sha256_file(source_path)
        if actual != expected:
            raise AssertionError(f"source hash changed for {source_name}: {actual} != {expected}")
    master_sha = sha256_file(MASTER)
    if master_sha != inventory["master"]["sha256"]:
        raise AssertionError("master executable-label parquet changed after inventory")
    return inventory


def _build_base_and_pairphys(master: pd.DataFrame, inventory: dict[str, Any]) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    pairphys = inventory["blocks"]["pairwise_current_time_physics_context"]["features"]
    for ticker, bucket in (("SPXW", 25), ("QQQ", 35), ("SPY", 35)):
        part = master.loc[master["ticker"].eq(ticker)].copy()
        part, features = build_diff_features(part, ticker=ticker, bucket=bucket)
        expected = inventory["recommended_arms"]["E0"]["features"]
        if features != expected:
            raise AssertionError(f"E0 allowlist construction changed for {ticker}")
        renamed = {column: f"pairphys__{column}" for column in pairphys}
        part = part.rename(columns=renamed)
        columns = list(dict.fromkeys([*KEY, *expected, *renamed.values()]))
        outputs.append(part[columns])
    out = pd.concat(outputs, ignore_index=True)
    if out.duplicated(KEY).any():
        raise AssertionError("base modeling keys are not unique")
    return out


def _join_legacy(view: pd.DataFrame, inventory: dict[str, Any]) -> pd.DataFrame:
    features = inventory["blocks"]["legacy_live_feature_surface"]["features"]
    source = pd.read_parquet(LEGACY, columns=["ticker", "date", "time", *features])
    source = source[day(source["date"]).le("20251231")].copy()
    source["ticker"] = source["ticker"].replace({"SPX": "SPXW"}).astype(str)
    source["trade_date"] = day(source["date"])
    pieces = source["time"].astype(str).str.split(":")
    source["minute"] = pieces.str[0].astype(int) * 60 + pieces.str[1].astype(int)
    source = source[[*KEY, *features]]
    if source.duplicated(KEY).any():
        raise AssertionError("legacy exact keys are not unique")
    source = source.rename(columns={column: f"legacy__{column}" for column in features})
    return view.merge(source, on=KEY, how="left", validate="one_to_one")


def _join_wall_state(view: pd.DataFrame, inventory: dict[str, Any]) -> pd.DataFrame:
    features = inventory["blocks"]["wall_state_gex_dex_dgex"]["timestamp_state_features"]
    source = pd.read_parquet(WALL_STATE, columns=[*KEY, *features])
    source["trade_date"] = day(source["trade_date"])
    if source.duplicated(KEY).any():
        raise AssertionError("wall-state exact keys are not unique")
    source["wallstate__applicable"] = 1.0
    source = source.rename(columns={column: f"wallstate__{column}" for column in features})
    joined = view.merge(source, on=KEY, how="left", validate="one_to_one", indicator="_wall_join")
    expected_applicable = joined["minute"].ge(635)
    if not joined.loc[expected_applicable, "_wall_join"].eq("both").all():
        raise AssertionError("wall-state exact coverage is missing at minute >= 635")
    if joined.loc[~expected_applicable, "_wall_join"].eq("both").any():
        raise AssertionError("wall-state unexpectedly applies to frozen 10:30 geometry")
    joined["wallstate__applicable"] = joined["wallstate__applicable"].fillna(0.0)
    return joined.drop(columns="_wall_join")


def _join_ibqdyn(view: pd.DataFrame, inventory: dict[str, Any]) -> pd.DataFrame:
    features = inventory["blocks"]["h_ibqdyn1"]["frozen_f1_features"]
    identity_features = [column for column in features if column.startswith("identity_")]
    raw_features = [column for column in features if column not in identity_features]
    source_columns = list(dict.fromkeys([*KEY, "wall_identity", *raw_features]))
    source = pd.read_parquet(IBQDYN, columns=source_columns)
    source["trade_date"] = day(source["trade_date"])
    if source.duplicated(KEY).any():
        raise AssertionError("H-IBQDYN exact keys are not unique")
    identity = source["wall_identity"].astype(str)
    for column in identity_features:
        source[column] = identity.eq(column.removeprefix("identity_")).astype(float)
    if not source[identity_features].sum(axis=1).eq(1.0).all():
        raise AssertionError("H-IBQDYN frozen wall identity is outside the eight-level allowlist")
    source = source.drop(columns="wall_identity")
    source["ibqdyn__applicable"] = 1.0
    source = source.rename(columns={column: f"ibqdyn__{column}" for column in features})
    joined = view.merge(source, on=KEY, how="left", validate="one_to_one", indicator="_ib_join")
    matched = int(joined["_ib_join"].eq("both").sum())
    if matched != len(source):
        raise AssertionError(f"H-IBQDYN exact match count changed: {matched} != {len(source)}")
    joined["ibqdyn__applicable"] = joined["ibqdyn__applicable"].fillna(0.0)
    return joined.drop(columns="_ib_join")


def build_view(inventory_path: Path, output_path: Path, manifest_path: Path) -> dict[str, Any]:
    _assert_under_output(output_path)
    _assert_under_output(manifest_path)
    inventory = _load_inventory(inventory_path)
    e0 = list(inventory["recommended_arms"]["E0"]["features"])
    e1 = list(inventory["recommended_arms"]["E1"]["features"])

    pairphys = inventory["blocks"]["pairwise_current_time_physics_context"]["features"]
    raw_e0_sources = [
        "ticker", "trade_date", "minute", *e0[:9],
        *[f"{right}_d{bucket:02d}_{metric}" for right in ("call", "put")
          for bucket in (25, 35) for metric in ("iv", "spread_pct", "volume", "oi", "abs_delta", "vega")],
        *pairphys,
    ]
    master_columns = pq.ParquetFile(MASTER).schema_arrow.names
    read_columns = list(dict.fromkeys(column for column in raw_e0_sources if column in master_columns))
    required = {"ticker", "trade_date", "minute", *e0[:9], *pairphys}
    if not required.issubset(read_columns):
        raise KeyError(f"master is missing modeling fields: {sorted(required - set(read_columns))[:10]}")
    master = pd.read_parquet(MASTER, columns=read_columns)
    master["ticker"] = master["ticker"].astype(str).str.upper()
    master["trade_date"] = day(master["trade_date"])
    if len(master) != int(inventory["master"]["rows"]) or master.duplicated(KEY).any():
        raise AssertionError("master universe changed during modeling-view build")

    view = _build_base_and_pairphys(master, inventory)
    view = _join_legacy(view, inventory)
    view = _join_wall_state(view, inventory)
    view = _join_ibqdyn(view, inventory)
    missing = [column for column in e1 if column not in view]
    extras = [column for column in view if column not in {*KEY, *e1}]
    if missing or extras:
        raise AssertionError(f"modeling-view schema mismatch; missing={missing[:5]}, extras={extras[:5]}")
    ordered_columns = list(dict.fromkeys([*KEY, *e1]))
    view = view[ordered_columns].sort_values(KEY, kind="stable").reset_index(drop=True)
    for column in e1:
        view[column] = pd.to_numeric(view[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    if view.duplicated(KEY).any() or len(view) != int(inventory["master"]["rows"]):
        raise AssertionError("modeling view failed full-universe preservation")
    if hash_ordered(e0) != inventory["recommended_arms"]["E0"]["ordered_json_sha256"]:
        raise AssertionError("E0 ordered hash mismatch")
    if hash_ordered(e1) != inventory["recommended_arms"]["E1"]["ordered_json_sha256"]:
        raise AssertionError("E1 ordered hash mismatch")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    view.to_parquet(output_path, index=False, compression="zstd")
    reloaded = pd.read_parquet(output_path, columns=KEY)
    if len(reloaded) != len(view) or reloaded.duplicated(KEY).any():
        raise AssertionError("persisted temporary view failed key revalidation")
    missing_counts = view[e1].isna().sum()
    manifest = {
        "schema": "existing_data_edge_modeling_view_v1",
        "status": "PASS_EXACT_EXISTING_DATA_VIEW",
        "outcomes_in_view": False,
        "new_data_source": False,
        "join_types": ["exact equality on ticker/trade_date/minute", "self/master"],
        "forbidden_joins_used": [],
        "master_rows_preserved": len(view),
        "date_min": str(view["trade_date"].min()),
        "date_max": str(view["trade_date"].max()),
        "rows_by_ticker": {str(k): int(v) for k, v in view.groupby("ticker", observed=True).size().items()},
        "source_inventory_sha256": sha256_file(inventory_path),
        "source_hashes": {name: value["sha256"] for name, value in inventory["sources"].items()},
        "master_sha256": inventory["master"]["sha256"],
        "view_path": _relative(output_path),
        "view_sha256": sha256_file(output_path),
        "view_bytes": output_path.stat().st_size,
        "E0": {"features": e0, "feature_count": len(e0), "ordered_json_sha256": hash_ordered(e0)},
        "E1": {"features": e1, "feature_count": len(e1), "ordered_json_sha256": hash_ordered(e1)},
        "null_counts": {str(k): int(v) for k, v in missing_counts.items() if int(v) > 0},
        "geometry": {
            "master_includes_1030": True,
            "e0_backward_changes_use_only_same-day earlier master rows": True,
            "wallstate_applicable_from_minute": 635,
            "ibqdyn_applicable_only_on_exact_frozen_event_keys": True,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest["manifest_path"] = _relative(manifest_path)
    manifest["manifest_sha256"] = sha256_file(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY.relative_to(ROOT)))
    parser.add_argument("--output", default=str(DEFAULT_VIEW.relative_to(ROOT)))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST.relative_to(ROOT)))
    args = parser.parse_args()
    manifest = build_view(ROOT / args.inventory, ROOT / args.output, ROOT / args.manifest)
    print(json.dumps({key: manifest[key] for key in (
        "status", "master_rows_preserved", "view_path", "view_sha256", "view_bytes",
        "manifest_path", "manifest_sha256",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
