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

from neural.jepa.dataset import infer_sort_columns
from neural.jepa.features import write_feature_names
from neural.jepa.xinput_dataset import XInputNormalizers
from neural.jepa.xinput_model import load_xinput_model


def build_contexts(arr: np.ndarray, context_len: int) -> tuple[np.ndarray, list[int]]:
    contexts = []
    positions = []
    for pos in range(context_len - 1, len(arr)):
        contexts.append(arr[pos - context_len + 1 : pos + 1])
        positions.append(pos)
    if not contexts:
        return np.zeros((0, context_len, arr.shape[1]), dtype=np.float32), []
    return np.stack(contexts, axis=0).astype(np.float32), positions


def pairwise_dispersion(preds: np.ndarray, indices: list[int]) -> float:
    valid = [i for i in indices if i >= 0]
    if len(valid) < 2:
        return 0.0
    vals = preds[valid]
    dists = []
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            dists.append(float(np.linalg.norm(vals[i] - vals[j])))
    return float(np.mean(dists)) if dists else 0.0


def infer_batches(model, state_ctx: np.ndarray, input_ctx: np.ndarray, batch_size: int, device: torch.device):
    z_out, u_out, pred_out, prob_out = [], [], [], []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(state_ctx), batch_size):
            s = torch.from_numpy(state_ctx[start : start + batch_size]).to(device).float()
            uin = torch.from_numpy(input_ctx[start : start + batch_size]).to(device).float()
            z, u, pred, logits = model(s, uin)
            z_out.append(z.cpu().numpy())
            u_out.append(u.cpu().numpy())
            pred_out.append(pred.cpu().numpy())
            prob_out.append(torch.softmax(logits, dim=-1).cpu().numpy())
    if not z_out:
        return (
            np.zeros((0, model.config.z_dim), dtype=np.float32),
            np.zeros((0, model.config.u_dim), dtype=np.float32),
            np.zeros((0, len(model.config.horizons), model.config.z_dim), dtype=np.float32),
            np.zeros((0, 3), dtype=np.float32),
        )
    return np.concatenate(z_out), np.concatenate(u_out), np.concatenate(pred_out), np.concatenate(prob_out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append explicit exogenous-input JEPA features.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--batch-size", type=int, default=4096)
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    normalizers = XInputNormalizers.load(model_dir / "normalizers.json")
    model = load_xinput_model(model_dir, map_location="cpu")
    device = torch.device(args.device)
    model.to(device)

    df = pd.read_parquet(args.data)
    n = len(df)
    work = df.copy()
    work["_orig_index"] = np.arange(n, dtype=np.int64)
    work["date"] = work["date"].astype(str)
    work = work.sort_values(infer_sort_columns(work)).reset_index(drop=True)

    z_dim = model.config.z_dim
    u_dim = model.config.u_dim
    horizons = [int(h) for h in model.config.horizons]
    h_to_idx = {h: i for i, h in enumerate(horizons)}

    feature_data: dict[str, np.ndarray] = {}
    for i in range(z_dim):
        feature_data[f"xjepa_z_{i:02d}"] = np.zeros(n, dtype=np.float32)
    for i in range(u_dim):
        feature_data[f"xjepa_u_{i:02d}"] = np.zeros(n, dtype=np.float32)
    scalar_cols = [
        "xjepa_latent_velocity",
        "xjepa_input_velocity",
        "xjepa_pred_dispersion_short",
        "xjepa_pred_dispersion_long",
        "xjepa_lagged_pred_30m_err",
        "xjepa_lagged_pred_60m_err",
        "xjepa_lagged_pred_180m_err",
        "xjepa_prob_short",
        "xjepa_prob_hold",
        "xjepa_prob_long",
        "xjepa_trade_confidence",
        "xjepa_direction_score",
        "xjepa_entropy",
        "xjepa_context_valid",
    ]
    for c in scalar_cols:
        feature_data[c] = np.zeros(n, dtype=np.float32)

    for _, group in work.groupby(["ticker", "date"], sort=False):
        s_arr = normalizers.state.transform_frame(group)
        u_arr = normalizers.input.transform_frame(group)
        s_ctx, positions = build_contexts(s_arr, model.config.context_len)
        u_ctx, _ = build_contexts(u_arr, model.config.context_len)
        if len(s_ctx) == 0:
            continue
        z, u_lat, pred, probs = infer_batches(model, s_ctx, u_ctx, args.batch_size, device)
        z_by_pos = np.zeros((len(group), z_dim), dtype=np.float32)
        u_by_pos = np.zeros((len(group), u_dim), dtype=np.float32)
        pred_by_pos = np.zeros((len(group), len(horizons), z_dim), dtype=np.float32)
        prob_by_pos = np.zeros((len(group), 3), dtype=np.float32)
        valid = np.zeros(len(group), dtype=bool)
        for row_i, pos in enumerate(positions):
            z_by_pos[pos] = z[row_i]
            u_by_pos[pos] = u_lat[row_i]
            pred_by_pos[pos] = pred[row_i]
            prob_by_pos[pos] = probs[row_i]
            valid[pos] = True

        orig = group["_orig_index"].to_numpy(dtype=np.int64)
        for pos in range(len(group)):
            out_i = orig[pos]
            if not valid[pos]:
                continue
            feature_data["xjepa_context_valid"][out_i] = 1.0
            for zi in range(z_dim):
                feature_data[f"xjepa_z_{zi:02d}"][out_i] = z_by_pos[pos, zi]
            for ui in range(u_dim):
                feature_data[f"xjepa_u_{ui:02d}"][out_i] = u_by_pos[pos, ui]
            if pos >= 1 and valid[pos - 1]:
                feature_data["xjepa_latent_velocity"][out_i] = float(np.linalg.norm(z_by_pos[pos] - z_by_pos[pos - 1]))
                feature_data["xjepa_input_velocity"][out_i] = float(np.linalg.norm(u_by_pos[pos] - u_by_pos[pos - 1]))
            short_idx = [h_to_idx.get(h, -1) for h in (1, 3, 6)]
            long_idx = [h_to_idx.get(h, -1) for h in (12, 24, 36)]
            feature_data["xjepa_pred_dispersion_short"][out_i] = pairwise_dispersion(pred_by_pos[pos], short_idx)
            feature_data["xjepa_pred_dispersion_long"][out_i] = pairwise_dispersion(pred_by_pos[pos], long_idx)
            for h, col in [
                (6, "xjepa_lagged_pred_30m_err"),
                (12, "xjepa_lagged_pred_60m_err"),
                (36, "xjepa_lagged_pred_180m_err"),
            ]:
                hi = h_to_idx.get(h)
                src = pos - h
                if hi is not None and src >= 0 and valid[src]:
                    feature_data[col][out_i] = float(np.linalg.norm(pred_by_pos[src, hi] - z_by_pos[pos]))
            p = prob_by_pos[pos]
            entropy = -float(np.sum(p * np.log(np.clip(p, 1e-8, 1.0))))
            feature_data["xjepa_prob_short"][out_i] = float(p[0])
            feature_data["xjepa_prob_hold"][out_i] = float(p[1])
            feature_data["xjepa_prob_long"][out_i] = float(p[2])
            feature_data["xjepa_trade_confidence"][out_i] = float(max(p[0], p[2]))
            feature_data["xjepa_direction_score"][out_i] = float(p[2] - p[0])
            feature_data["xjepa_entropy"][out_i] = entropy

    out_df = df.copy()
    for col, values in feature_data.items():
        out_df[col] = values
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(output, index=False)
    write_feature_names(model_dir / "jepa_feature_names.json", list(feature_data.keys()))
    (model_dir / "jepa_append_last.json").write_text(
        json.dumps(
            {"input": str(args.data), "output": str(output), "rows": int(len(out_df)), "features": list(feature_data.keys())},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote={output} rows={len(out_df)} added_features={len(feature_data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

