from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

import numpy as np
import pandas as pd
import torch

if __package__:
    from .export_event_phys_td_shadow_transitions import (
        load_frozen_encoder,
        prepare_frame,
        sha256_file,
    )
    from .walkforward_event_phys_td_jepa_oof import build_contexts
else:
    from export_event_phys_td_shadow_transitions import load_frozen_encoder, prepare_frame, sha256_file
    from walkforward_event_phys_td_jepa_oof import build_contexts


def export_current_horizon_features(
    model: torch.nn.Module,
    normalizer: Any,
    frame: pd.DataFrame,
    args: SimpleNamespace,
    device: torch.device,
    *,
    horizons: Sequence[int],
) -> pd.DataFrame:
    requested = [int(value) for value in horizons]
    if not requested or len(set(requested)) != len(requested):
        raise ValueError("horizons must be non-empty and unique")
    configured = [int(value) for value in model.config.horizons]
    missing = [value for value in requested if value not in configured]
    if missing:
        raise ValueError(f"requested horizons not in checkpoint: {missing}")
    work = frame.copy().reset_index(drop=True)
    sort_col = "timestamp" if "timestamp" in work.columns else "time"
    work = work.sort_values(["ticker", "date", "expiry_mode", sort_col], kind="stable").reset_index(drop=True)
    group_cols = ["ticker", "date", "expiry_mode"] if bool(args.group_expiry_mode) else ["ticker", "date"]
    horizon_indices = [configured.index(value) for value in requested]
    z_dim = int(model.config.z_dim)
    rows: list[dict[str, Any]] = []
    model.eval()
    with torch.no_grad():
        for _, group in work.groupby(group_cols, sort=False):
            group = group.reset_index(drop=True)
            minutes = pd.to_numeric(group["minute"], errors="raise").to_numpy(dtype=np.int64)
            normalized = normalizer.transform_frame(group)
            contexts, delta_contexts, positions = build_contexts(
                normalized,
                int(model.config.context_len),
                minutes=minutes,
                expected_step_minutes=int(args.expected_step_minutes),
            )
            if not positions:
                continue
            z_parts: list[np.ndarray] = []
            pred_parts: list[np.ndarray] = []
            for start in range(0, len(contexts), int(args.infer_batch_size)):
                context = torch.from_numpy(contexts[start : start + int(args.infer_batch_size)]).to(device).float()
                delta = torch.from_numpy(delta_contexts[start : start + int(args.infer_batch_size)]).to(device).float()
                z, _, prediction = model(context, delta)
                z_parts.append(z.cpu().numpy())
                pred_parts.append(prediction[:, horizon_indices].cpu().numpy())
            encoded = np.concatenate(z_parts).astype(np.float32, copy=False)
            predicted = np.concatenate(pred_parts).astype(np.float32, copy=False)
            for row_index, position in enumerate(positions):
                current = group.iloc[int(position)]
                row: dict[str, Any] = {
                    "ticker": str(current["ticker"]),
                    "trade_date": str(current["trade_date"]),
                    "expiration": str(current["expiration"]),
                    "expiry_mode": str(current["expiry_mode"]),
                    "timestamp": current[sort_col],
                    "time": current["time"],
                    "minute": int(minutes[position]),
                }
                for dimension in range(z_dim):
                    row[f"horizon_z_{dimension:02d}"] = float(encoded[row_index, dimension])
                for requested_index, horizon in enumerate(requested):
                    for dimension in range(z_dim):
                        row[f"horizon_pred_h{horizon}_{dimension:02d}"] = float(
                            predicted[row_index, requested_index, dimension]
                        )
                rows.append(row)
    columns = [
        "ticker",
        "trade_date",
        "expiration",
        "expiry_mode",
        "timestamp",
        "time",
        "minute",
        *[f"horizon_z_{dimension:02d}" for dimension in range(z_dim)],
        *[
            f"horizon_pred_h{horizon}_{dimension:02d}"
            for horizon in requested
            for dimension in range(z_dim)
        ],
    ]
    return pd.DataFrame(rows, columns=columns)


def export_from_checkpoint(
    model_path: str | Path,
    frame: pd.DataFrame,
    *,
    start_month: str,
    end_month: str,
    horizons: Sequence[int],
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
    features = export_current_horizon_features(
        model, normalizer, work, export_args, target_device, horizons=horizons
    )
    if features.empty:
        raise RuntimeError("frozen encoder produced no current-time horizon features")
    if features.duplicated(["ticker", "trade_date", "minute"]).any():
        raise RuntimeError("current-time horizon export contains duplicate keys")
    contract = {
        "schema_version": 1,
        "component": "event_phys_td_current_horizon_features",
        "model_path": str(model_path),
        "model_sha256": sha256_file(model_path),
        "encoder_deploy_month": deploy_month,
        "encoder_training_months": training_months,
        "start_month": str(start_month),
        "end_month": str(end_month),
        "horizons": [int(value) for value in horizons],
        "horizon_minutes": [int(value) * int(export_args.expected_step_minutes) for value in horizons],
        "rows": int(len(features)),
        "tickers": sorted(features["ticker"].astype(str).unique().tolist()),
        "date_min": str(features["trade_date"].min()),
        "date_max": str(features["trade_date"].max()),
        "uses_future_target": False,
        "june_2026_sealed": True,
    }
    return features, contract


def main() -> int:
    parser = argparse.ArgumentParser(description="Export current-time Phys-TD predictions for fixed horizons.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", required=True)
    parser.add_argument("--end-month", required=True)
    parser.add_argument("--horizons", nargs="+", type=int, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    source_path = Path(args.data)
    features, metadata = export_from_checkpoint(
        args.model,
        pd.read_parquet(source_path),
        start_month=args.start_month,
        end_month=args.end_month,
        horizons=args.horizons,
        device=args.device,
    )
    output_path = output_dir / "current_horizon_features.parquet"
    features.to_parquet(output_path, index=False)
    metadata.update(
        {
            "source_path": str(source_path),
            "source_sha256": sha256_file(source_path),
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
