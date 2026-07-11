from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import torch

if __package__:
    from .dataset import RobustNormalizer
    from .walkforward_event_phys_td_jepa_oof import (
        EventPhysTDJEPA,
        EventPhysTDJEPAConfig,
        export_observed_transition_features,
    )
else:
    from neural.jepa.dataset import RobustNormalizer
    from neural.jepa.walkforward_event_phys_td_jepa_oof import (
        EventPhysTDJEPA,
        EventPhysTDJEPAConfig,
        export_observed_transition_features,
    )


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_frozen_encoder(
    model_path: str | Path,
    device: torch.device,
) -> tuple[EventPhysTDJEPA, RobustNormalizer, list[str], dict[str, Any]]:
    try:
        payload = torch.load(model_path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(model_path, map_location="cpu")
    if not isinstance(payload, dict) or payload.get("component") != "event_phys_td_jepa_encoder":
        raise ValueError("unexpected Phys-TD-JEPA encoder payload")
    required = ("model_state_dict", "config", "feature_cols", "normalizer", "metadata")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"encoder payload missing fields: {missing}")
    config = EventPhysTDJEPAConfig(**payload["config"])
    model = EventPhysTDJEPA(config)
    model.load_state_dict(payload["model_state_dict"])
    model.to(device).eval()
    normalizer = RobustNormalizer.from_dict(payload["normalizer"])
    feature_cols = [str(value) for value in payload["feature_cols"]]
    if feature_cols != list(normalizer.feature_names):
        raise ValueError("encoder feature columns and normalizer contract differ")
    return model, normalizer, feature_cols, dict(payload["metadata"])


def prepare_frame(frame: pd.DataFrame, feature_cols: list[str], start_month: str, end_month: str) -> pd.DataFrame:
    if str(end_month) > "202605":
        raise ValueError("June 2026 is sealed; end_month must be <= 202605")
    work = frame.copy()
    if "date" not in work.columns:
        work["date"] = work["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    work["month"] = work["date"].str[:6]
    work = work[work["month"].between(str(start_month), str(end_month))].copy()
    if work.empty:
        raise ValueError("no rows in requested transition export window")
    if int(work["date"].astype(int).max()) >= 20260601:
        raise ValueError("June 2026 seal violated by source rows")
    if "time" not in work.columns and "timestamp" in work.columns:
        work["time"] = pd.to_datetime(work["timestamp"], format="mixed", errors="raise").dt.strftime("%H:%M")
    if "timestamp" not in work.columns:
        work["timestamp"] = pd.to_datetime(
            work["date"].astype(str) + " " + work["time"].astype(str), errors="raise"
        )
    required_keys = ["ticker", "trade_date", "expiration", "expiry_mode", "timestamp", "time", "minute"]
    missing = [column for column in [*required_keys, *feature_cols] if column not in work.columns]
    if missing:
        raise ValueError(f"source data missing frozen encoder columns: {missing[:20]}")
    if "option_price_mode" in work.columns and set(work["option_price_mode"].astype(str)) != {"executable_quote"}:
        raise ValueError("source is not exclusively executable_quote")
    minute = pd.to_numeric(work["minute"], errors="raise").astype(int)
    if minute.min() < 630 or minute.max() > 870 or not ((minute - 600) % 5 == 0).all():
        raise ValueError("source violates 10:30-14:30 ET five-minute grid")
    return work.reset_index(drop=True)


def export_from_checkpoint(
    model_path: str | Path,
    frame: pd.DataFrame,
    *,
    start_month: str,
    end_month: str,
    device: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    target_device = torch.device(device)
    model, normalizer, feature_cols, metadata = load_frozen_encoder(model_path, target_device)
    work = prepare_frame(frame, feature_cols, start_month, end_month)
    training_months = [str(value) for value in metadata.get("train_months", [])]
    deploy_month = str(metadata.get("deploy_month", ""))
    if not training_months or not deploy_month or max(training_months) >= deploy_month:
        raise ValueError("encoder metadata does not prove a causal training cutoff")
    args_payload = dict(metadata.get("args") or {})
    export_args = SimpleNamespace(
        expected_step_minutes=int(args_payload.get("expected_step_minutes", 5)),
        infer_batch_size=int(args_payload.get("infer_batch_size", 4096)),
        group_expiry_mode=bool(args_payload.get("group_expiry_mode", True)),
    )
    transitions = export_observed_transition_features(
        model,
        normalizer,
        work,
        feature_cols,
        export_args,
        target_device,
        horizon_steps=1,
    )
    if transitions.empty:
        raise RuntimeError("frozen encoder produced no contiguous transition rows")
    current = pd.to_datetime(transitions["timestamp"], format="mixed", errors="raise")
    target = pd.to_datetime(transitions["target_timestamp"], format="mixed", errors="raise")
    if not ((target - current).dt.total_seconds() == 300).all():
        raise RuntimeError("export contains a non-five-minute target transition")
    contract = {
        "schema_version": 1,
        "component": "event_phys_td_shadow_transitions",
        "model_path": str(model_path),
        "model_sha256": sha256_file(model_path),
        "encoder_deploy_month": deploy_month,
        "encoder_training_months": training_months,
        "start_month": str(start_month),
        "end_month": str(end_month),
        "rows": int(len(transitions)),
        "tickers": sorted(transitions["ticker"].astype(str).unique().tolist()),
        "date_min": str(transitions["trade_date"].min()),
        "date_max": str(transitions["trade_date"].max()),
        "horizon_minutes": 5,
        "target_z_live_feature": False,
        "target_available_only_at_target_timestamp": True,
        "june_2026_sealed": True,
    }
    return transitions, contract


def main() -> int:
    parser = argparse.ArgumentParser(description="Export causal z/pred_z/target_z pairs from one frozen Phys-TD encoder.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", required=True)
    parser.add_argument("--end-month", required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    source = Path(args.data)
    frame = pd.read_parquet(source)
    transitions, metadata = export_from_checkpoint(
        args.model,
        frame,
        start_month=args.start_month,
        end_month=args.end_month,
        device=args.device,
    )
    output_path = output_dir / "shadow_transitions.parquet"
    transitions.to_parquet(output_path, index=False)
    metadata.update(
        {
            "source_path": str(source),
            "source_sha256": sha256_file(source),
            "output_path": str(output_path),
            "output_sha256": sha256_file(output_path),
        }
    )
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
