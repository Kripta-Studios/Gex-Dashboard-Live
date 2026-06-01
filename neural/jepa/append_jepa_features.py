from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.dataset import RobustNormalizer, infer_sort_columns
from neural.jepa.features import write_feature_names
from neural.jepa.model import load_model


def horizon_label(step_horizon: int) -> str:
    return f"{int(step_horizon) * 5}m"


def pairwise_dispersion(preds: np.ndarray, horizon_indices: list[int]) -> float:
    valid = [i for i in horizon_indices if i >= 0]
    if len(valid) < 2:
        return 0.0
    vals = preds[valid]
    dists = []
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            dists.append(float(np.linalg.norm(vals[i] - vals[j])))
    return float(np.mean(dists)) if dists else 0.0


def build_contexts(arr: np.ndarray, context_len: int) -> tuple[np.ndarray, list[int]]:
    contexts = []
    positions = []
    for pos in range(context_len - 1, len(arr)):
        contexts.append(arr[pos - context_len + 1 : pos + 1])
        positions.append(pos)
    if not contexts:
        return np.zeros((0, context_len, arr.shape[1]), dtype=np.float32), []
    return np.stack(contexts, axis=0).astype(np.float32), positions


def infer_all_latents(
    model,
    contexts: np.ndarray,
    batch_size: int,
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray]:
    z_out = []
    pred_out = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(contexts), batch_size):
            batch = torch.from_numpy(contexts[start : start + batch_size]).to(device).float()
            z, pred = model(batch)
            z_out.append(z.cpu().numpy())
            pred_out.append(pred.cpu().numpy())
    if not z_out:
        z_dim = model.config.z_dim
        return (
            np.zeros((0, z_dim), dtype=np.float32),
            np.zeros((0, len(model.config.horizons), z_dim), dtype=np.float32),
        )
    return np.concatenate(z_out, axis=0), np.concatenate(pred_out, axis=0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append live-safe JEPA features to a parquet file.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--live-safe-only", action="store_true")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    normalizer = RobustNormalizer.load(model_dir / "normalizer.json")
    model = load_model(model_dir, map_location="cpu")
    device = torch.device(args.device)
    model.to(device)
    model.eval()

    df = pd.read_parquet(args.data)
    original_len = len(df)
    work = df.copy()
    work["_orig_index"] = np.arange(len(work), dtype=np.int64)
    work["date"] = work["date"].astype(str)
    sort_cols = infer_sort_columns(work)
    work = work.sort_values(sort_cols).reset_index(drop=True)

    z_dim = model.config.z_dim
    horizons = [int(h) for h in model.config.horizons]
    h_to_idx = {h: i for i, h in enumerate(horizons)}
    feature_data: dict[str, np.ndarray] = {}
    for i in range(z_dim):
        feature_data[f"jepa_z_{i:02d}"] = np.zeros(original_len, dtype=np.float32)
    scalar_cols = [
        "jepa_latent_velocity",
        "jepa_latent_accel",
        "jepa_pred_norm_5m",
        "jepa_pred_norm_30m",
        "jepa_pred_norm_60m",
        "jepa_pred_norm_180m",
        "jepa_pred_dispersion_short",
        "jepa_pred_dispersion_long",
        "jepa_lagged_pred_30m_err",
        "jepa_lagged_pred_60m_err",
        "jepa_lagged_pred_180m_err",
        "jepa_context_valid",
    ]
    for c in scalar_cols:
        feature_data[c] = np.zeros(original_len, dtype=np.float32)

    for (ticker, date), group in work.groupby(["ticker", "date"], sort=False):
        arr = normalizer.transform_frame(group)
        contexts, positions = build_contexts(arr, model.config.context_len)
        if len(contexts) == 0:
            continue
        z, pred = infer_all_latents(model, contexts, args.batch_size, device)
        z_by_pos = np.zeros((len(group), z_dim), dtype=np.float32)
        pred_by_pos = np.zeros((len(group), len(horizons), z_dim), dtype=np.float32)
        valid = np.zeros(len(group), dtype=bool)
        for row_i, pos in enumerate(positions):
            z_by_pos[pos] = z[row_i]
            pred_by_pos[pos] = pred[row_i]
            valid[pos] = True

        orig = group["_orig_index"].to_numpy(dtype=np.int64)
        for pos in range(len(group)):
            out_i = orig[pos]
            if not valid[pos]:
                continue
            feature_data["jepa_context_valid"][out_i] = 1.0
            for zi in range(z_dim):
                feature_data[f"jepa_z_{zi:02d}"][out_i] = z_by_pos[pos, zi]

            if pos >= 1 and valid[pos - 1]:
                feature_data["jepa_latent_velocity"][out_i] = float(np.linalg.norm(z_by_pos[pos] - z_by_pos[pos - 1]))
            if pos >= 2 and valid[pos - 1] and valid[pos - 2]:
                v1 = z_by_pos[pos] - z_by_pos[pos - 1]
                v0 = z_by_pos[pos - 1] - z_by_pos[pos - 2]
                feature_data["jepa_latent_accel"][out_i] = float(np.linalg.norm(v1 - v0))

            for h, col in [
                (1, "jepa_pred_norm_5m"),
                (6, "jepa_pred_norm_30m"),
                (12, "jepa_pred_norm_60m"),
                (36, "jepa_pred_norm_180m"),
            ]:
                hi = h_to_idx.get(h)
                if hi is not None:
                    feature_data[col][out_i] = float(np.linalg.norm(pred_by_pos[pos, hi]))

            short_idx = [h_to_idx.get(h, -1) for h in (1, 3, 6)]
            long_idx = [h_to_idx.get(h, -1) for h in (12, 24, 36)]
            feature_data["jepa_pred_dispersion_short"][out_i] = pairwise_dispersion(pred_by_pos[pos], short_idx)
            feature_data["jepa_pred_dispersion_long"][out_i] = pairwise_dispersion(pred_by_pos[pos], long_idx)

            for h, col in [
                (6, "jepa_lagged_pred_30m_err"),
                (12, "jepa_lagged_pred_60m_err"),
                (36, "jepa_lagged_pred_180m_err"),
            ]:
                hi = h_to_idx.get(h)
                src = pos - h
                if hi is not None and src >= 0 and valid[src]:
                    feature_data[col][out_i] = float(np.linalg.norm(pred_by_pos[src, hi] - z_by_pos[pos]))

    out_df = df.copy()
    for col, values in feature_data.items():
        out_df[col] = values

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(output, index=False)

    live_safe = list(feature_data.keys())
    write_feature_names(model_dir / "jepa_feature_names.json", live_safe)
    (model_dir / "jepa_append_last.json").write_text(
        json.dumps(
            {
                "input": str(args.data),
                "output": str(output),
                "rows": int(len(out_df)),
                "features": live_safe,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote={output} rows={len(out_df)} added_features={len(live_safe)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

