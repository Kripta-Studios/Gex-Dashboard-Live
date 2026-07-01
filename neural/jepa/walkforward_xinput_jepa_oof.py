from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, WeightedRandomSampler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.append_xinput_jepa_features import build_contexts, infer_batches, pairwise_dispersion
from neural.jepa.dataset import infer_sort_columns
from neural.jepa.features import write_feature_names
from neural.jepa.sigreg import SIGRegLoss, VarianceCovarianceLoss, latent_diagnostics
from neural.jepa.xinput_dataset import XInputJEPADataset, XInputNormalizers, fit_xinput_normalizers, prepare_xinput_frame
from neural.jepa.xinput_model import XInputJEPAConfig, XInputMarketJEPA, save_xinput_model


def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)


def parse_horizons(text: str) -> list[int]:
    return [int(x.strip()) for x in str(text).split(",") if x.strip()]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def month_add(yyyymm: str, delta: int) -> str:
    value = int(yyyymm)
    year = value // 100
    month = value % 100 + int(delta)
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return f"{year:04d}{month:02d}"


def class_weights(labels: list[int], device: torch.device) -> torch.Tensor:
    counts = np.bincount(np.asarray(labels, dtype=np.int64), minlength=3).astype(np.float32)
    weights = counts.sum() / np.maximum(counts, 1.0)
    weights = weights / weights.mean()
    return torch.tensor(weights, dtype=torch.float32, device=device)


def sampler_for_labels(labels: list[int]) -> WeightedRandomSampler:
    counts = np.bincount(np.asarray(labels, dtype=np.int64), minlength=3).astype(np.float64)
    inv = 1.0 / np.maximum(counts, 1.0)
    weights = inv[np.asarray(labels, dtype=np.int64)]
    return WeightedRandomSampler(weights=weights, num_samples=len(weights), replacement=True)


def make_loader(ds: XInputJEPADataset, args: argparse.Namespace, shuffle: bool, sampler=None) -> DataLoader:
    return DataLoader(
        ds,
        batch_size=int(args.batch_size),
        shuffle=shuffle and sampler is None,
        sampler=sampler,
        num_workers=int(args.num_workers),
        pin_memory=torch.cuda.is_available(),
        persistent_workers=bool(args.num_workers > 0),
    )


def train_epoch(
    model: XInputMarketJEPA,
    loader: DataLoader,
    sigreg: SIGRegLoss,
    vicreg: VarianceCovarianceLoss,
    ce_weight: torch.Tensor,
    opt: torch.optim.Optimizer,
    args: argparse.Namespace,
    device: torch.device,
) -> dict:
    model.train()
    sums = {"pred": 0.0, "sig": 0.0, "vic": 0.0, "ce": 0.0, "total": 0.0}
    total = 0
    for state_ctx, input_ctx, targets, y in loader:
        state_ctx = state_ctx.to(device).float()
        input_ctx = input_ctx.to(device).float()
        targets = targets.to(device).float()
        y = y.to(device)
        b, h, l, feat = targets.shape
        z, u, pred_z, logits = model(state_ctx, input_ctx)
        target_z = model.encode_state(targets.reshape(b * h, l, feat)).reshape(b, h, -1)
        pred_loss = F.mse_loss(pred_z, target_z.detach())
        z_all = torch.cat([z, target_z.reshape(b * h, -1)], dim=0)
        sig_loss = sigreg(z_all)
        vic_loss = vicreg(z_all)
        ce_loss = F.cross_entropy(logits, y, weight=ce_weight)
        loss = (
            pred_loss
            + float(args.lambda_sigreg) * sig_loss
            + float(args.lambda_vicreg) * vic_loss
            + float(args.lambda_ce) * ce_loss
        )
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        n = len(state_ctx)
        total += n
        sums["pred"] += float(pred_loss.item()) * n
        sums["sig"] += float(sig_loss.item()) * n
        sums["vic"] += float(vic_loss.item()) * n
        sums["ce"] += float(ce_loss.item()) * n
        sums["total"] += float(loss.item()) * n
    return {k: v / max(1, total) for k, v in sums.items()}


def evaluate_model(
    model: XInputMarketJEPA,
    loader: DataLoader,
    sigreg: SIGRegLoss,
    vicreg: VarianceCovarianceLoss,
    ce_weight: torch.Tensor,
    args: argparse.Namespace,
    device: torch.device,
) -> dict:
    model.eval()
    total = 0
    sums = {"pred": 0.0, "sig": 0.0, "vic": 0.0, "ce": 0.0, "total": 0.0}
    logits_all, y_all, z_batches = [], [], []
    with torch.no_grad():
        for state_ctx, input_ctx, targets, y in loader:
            state_ctx = state_ctx.to(device).float()
            input_ctx = input_ctx.to(device).float()
            targets = targets.to(device).float()
            y = y.to(device)
            b, h, l, feat = targets.shape
            z, _, pred_z, logits = model(state_ctx, input_ctx)
            target_z = model.encode_state(targets.reshape(b * h, l, feat)).reshape(b, h, -1)
            pred_loss = F.mse_loss(pred_z, target_z.detach())
            z_all = torch.cat([z, target_z.reshape(b * h, -1)], dim=0)
            sig_loss = sigreg(z_all)
            vic_loss = vicreg(z_all)
            ce_loss = F.cross_entropy(logits, y, weight=ce_weight)
            loss = (
                pred_loss
                + float(args.lambda_sigreg) * sig_loss
                + float(args.lambda_vicreg) * vic_loss
                + float(args.lambda_ce) * ce_loss
            )
            n = len(state_ctx)
            total += n
            sums["pred"] += float(pred_loss.item()) * n
            sums["sig"] += float(sig_loss.item()) * n
            sums["vic"] += float(vic_loss.item()) * n
            sums["ce"] += float(ce_loss.item()) * n
            sums["total"] += float(loss.item()) * n
            logits_all.append(logits.cpu())
            y_all.append(y.cpu())
            if len(z_batches) < 10:
                z_batches.append(z.cpu())
    out = {k: v / max(1, total) for k, v in sums.items()}
    if logits_all:
        logits = torch.cat(logits_all)
        y = torch.cat(y_all)
        probs = torch.softmax(logits, dim=-1)
        pred = probs.argmax(dim=-1)
        trade_mask = pred != 1
        out.update(
            {
                "acc": float((pred == y).float().mean().item()),
                "trade_precision": float((pred[trade_mask] == y[trade_mask]).float().mean().item()) if trade_mask.any() else 0.0,
                "trade_rate": float(trade_mask.float().mean().item()),
            }
        )
    if z_batches:
        diag = latent_diagnostics(torch.cat(z_batches))
        out.update({f"z_{k}": v for k, v in diag.items()})
    return out


def export_fold_features(
    model: XInputMarketJEPA,
    normalizers: XInputNormalizers,
    frame: pd.DataFrame,
    args: argparse.Namespace,
    device: torch.device,
) -> pd.DataFrame:
    work = frame.copy()
    work["_orig_index"] = np.arange(len(work), dtype=np.int64)
    work = work.sort_values(infer_sort_columns(work)).reset_index(drop=True)
    z_dim = int(model.config.z_dim)
    u_dim = int(model.config.u_dim)
    horizons = [int(h) for h in model.config.horizons]
    h_to_idx = {h: i for i, h in enumerate(horizons)}
    feature_data: dict[str, np.ndarray] = {}
    for i in range(z_dim):
        feature_data[f"xjepa_z_{i:02d}"] = np.zeros(len(work), dtype=np.float32)
    for i in range(u_dim):
        feature_data[f"xjepa_u_{i:02d}"] = np.zeros(len(work), dtype=np.float32)
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
    for col in scalar_cols:
        feature_data[col] = np.zeros(len(work), dtype=np.float32)

    for _, group in work.groupby(["ticker", "date"], sort=False):
        s_arr = normalizers.state.transform_frame(group)
        u_arr = normalizers.input.transform_frame(group)
        s_ctx, positions = build_contexts(s_arr, int(model.config.context_len))
        u_ctx, _ = build_contexts(u_arr, int(model.config.context_len))
        if len(s_ctx) == 0:
            continue
        z, u_lat, pred, probs = infer_batches(model, s_ctx, u_ctx, int(args.infer_batch_size), device)
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
        short_idx = [h_to_idx.get(h, -1) for h in (1, 3, 6)]
        long_idx = [h_to_idx.get(h, -1) for h in (12, 24, 36)]
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

    out = work[["ticker", "date", "time"]].copy()
    for col, values in feature_data.items():
        out[col] = values
    return out.sort_values(["ticker", "date", "time"]).reset_index(drop=True)


def train_fold(
    ticker: str,
    test_month: str,
    frame: pd.DataFrame,
    split,
    args: argparse.Namespace,
    device: torch.device,
) -> tuple[pd.DataFrame, dict]:
    val_months = [month_add(test_month, -i) for i in range(int(args.val_months), 0, -1)]
    first_val = val_months[0]
    fit = frame[frame["month"].astype(str) < first_val].copy()
    val = frame[frame["month"].astype(str).isin(val_months)].copy()
    test = frame[frame["month"].astype(str) == str(test_month)].copy()
    if fit.empty or val.empty or test.empty:
        raise ValueError(f"empty fold split for {ticker} {test_month}")

    fit_dates = set(fit["date"].astype(str).unique().tolist())
    val_dates = set(val["date"].astype(str).unique().tolist())
    normalizers = fit_xinput_normalizers(frame, split, fit_dates, clip=float(args.clip))
    train_ds = XInputJEPADataset(frame, normalizers, int(args.context_len), parse_horizons(args.horizons), fit_dates)
    val_ds = XInputJEPADataset(frame, normalizers, int(args.context_len), parse_horizons(args.horizons), val_dates)
    sampler = sampler_for_labels(train_ds.labels) if args.balanced_sampler else None
    train_loader = make_loader(train_ds, args, shuffle=True, sampler=sampler)
    val_loader = make_loader(val_ds, args, shuffle=False)
    config = XInputJEPAConfig(
        state_dim=len(split.state_features),
        input_dim=len(split.input_features),
        context_len=int(args.context_len),
        horizons=parse_horizons(args.horizons),
        hidden_dim=int(args.hidden_dim),
        z_dim=int(args.z_dim),
        u_dim=int(args.u_dim),
        num_layers=int(args.num_layers),
        dropout=float(args.dropout),
    )
    model = XInputMarketJEPA(config).to(device)
    sigreg = SIGRegLoss(int(args.z_dim), num_projections=int(args.sigreg_projections)).to(device)
    vicreg = VarianceCovarianceLoss(min_std=float(args.vicreg_min_std), cov_weight=0.05, var_weight=1.0).to(device)
    ce_weight = class_weights(train_ds.labels, device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(args.lr), weight_decay=float(args.weight_decay))
    best_state = None
    best_epoch = 0
    best_score = float("inf")
    history: list[dict] = []
    for epoch in range(1, int(args.epochs) + 1):
        train_metrics = train_epoch(model, train_loader, sigreg, vicreg, ce_weight, opt, args, device)
        val_metrics = evaluate_model(model, val_loader, sigreg, vicreg, ce_weight, args, device)
        health_penalty = max(0.0, 0.50 - float(val_metrics.get("z_effective_rank_ratio", 0.0)))
        score = float(val_metrics["total"]) + 0.25 * health_penalty
        row = {
            "epoch": epoch,
            **{f"train_{k}": v for k, v in train_metrics.items()},
            **{f"val_{k}": v for k, v in val_metrics.items()},
            "score": score,
        }
        history.append(row)
        if score < best_score - 1e-5:
            best_score = score
            best_epoch = epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)

    features = export_fold_features(model, normalizers, test, args, device)
    fold_row = {
        "ticker": ticker,
        "month": test_month,
        "val_months": ",".join(val_months),
        "fit_rows": int(len(fit)),
        "val_rows": int(len(val)),
        "test_rows": int(len(test)),
        "train_windows": int(len(train_ds)),
        "val_windows": int(len(val_ds)),
        "best_epoch": int(best_epoch),
        "best_score": float(best_score),
        "context_valid_rate": float(features["xjepa_context_valid"].mean()) if not features.empty else 0.0,
        "val_total": float(history[best_epoch - 1]["val_total"]) if best_epoch > 0 else float("nan"),
        "val_acc": float(history[best_epoch - 1].get("val_acc", float("nan"))) if best_epoch > 0 else float("nan"),
        "val_trade_precision": float(history[best_epoch - 1].get("val_trade_precision", float("nan"))) if best_epoch > 0 else float("nan"),
        "val_rank_ratio": float(history[best_epoch - 1].get("val_z_effective_rank_ratio", float("nan"))) if best_epoch > 0 else float("nan"),
    }
    if args.save_fold_models:
        model_dir = Path(args.output_dir) / "fold_models" / f"{ticker}_{test_month}"
        normalizers.save(model_dir / "normalizers.json")
        save_xinput_model(model, model_dir, extra={"fold": fold_row, "history": history})
    history_path = Path(args.output_dir) / "fold_logs" / f"{ticker}_{test_month}_metrics.csv"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sorted({k for row in history for k in row}))
        writer.writeheader()
        writer.writerows(history)
    return features, fold_row


def load_done(output_dir: Path, resume: bool) -> tuple[list[dict], set[tuple[str, str]]]:
    folds_path = output_dir / "fold_configs.csv"
    if not resume or not folds_path.exists():
        return [], set()
    fold_df = pd.read_csv(folds_path, dtype={"month": str})
    rows = fold_df.to_dict("records")
    done = {(str(r["ticker"]).upper(), str(r["month"])) for r in rows}
    return rows, done


def write_summary(output_dir: Path, metadata: dict, folds: list[dict]) -> None:
    fold_df = pd.DataFrame(folds)
    feature_path = output_dir / "oof_xinput_features.parquet"
    feature_rows = 0
    if feature_path.exists():
        try:
            feature_rows = int(len(pd.read_parquet(feature_path, columns=["ticker"])))
        except Exception:
            feature_rows = 0
    lines = [
        "# Walk-Forward XInputJEPA OOF",
        "",
        "Each fold trains only on months before the validation block and exports features for the held-out test month.",
        "",
        f"- OOF feature rows: `{feature_rows}`",
        f"- Completed folds: `{len(folds)}`",
        "",
        "## Fold Configs",
        "",
        "```csv",
        fold_df.to_csv(index=False) if not fold_df.empty else "",
        "```",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(metadata, indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def consolidate_features(output_dir: Path) -> None:
    chunk_dir = output_dir / "feature_chunks"
    chunks = sorted(chunk_dir.glob("*.parquet")) if chunk_dir.exists() else []
    if not chunks:
        return
    frames = [pd.read_parquet(path) for path in chunks]
    out = pd.concat(frames, ignore_index=True).drop_duplicates(["ticker", "date", "time"], keep="last")
    out = out.sort_values(["ticker", "date", "time"]).reset_index(drop=True)
    out.to_parquet(output_dir / "oof_xinput_features.parquet", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and export causal OOF XInputJEPA features by ticker/month.")
    parser.add_argument("--data", default="training_data/training_data_spx_qqq_spy.parquet")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPX", "SPY", "QQQ"])
    parser.add_argument("--start-month", default="202507")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument("--val-months", type=int, default=3)
    parser.add_argument("--context-len", type=int, default=6)
    parser.add_argument("--horizons", default="1,3,6,12,24,36")
    parser.add_argument("--z-dim", type=int, default=16)
    parser.add_argument("--u-dim", type=int, default=12)
    parser.add_argument("--hidden-dim", type=int, default=96)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.15)
    parser.add_argument("--lambda-sigreg", type=float, default=0.15)
    parser.add_argument("--lambda-vicreg", type=float, default=0.20)
    parser.add_argument("--lambda-ce", type=float, default=0.15)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--infer-batch-size", type=int, default=4096)
    parser.add_argument("--lr", type=float, default=7e-4)
    parser.add_argument("--weight-decay", type=float, default=2e-2)
    parser.add_argument("--clip", type=float, default=10.0)
    parser.add_argument("--sigreg-projections", type=int, default=64)
    parser.add_argument("--vicreg-min-std", type=float, default=0.75)
    parser.add_argument("--balanced-sampler", action="store_true")
    parser.add_argument("--seed", type=int, default=20260616)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--save-fold-models", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    set_seed(int(args.seed))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir = output_dir / "feature_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    df, split = prepare_xinput_frame(args.data)
    df["date"] = df["date"].map(normalize_date)
    df["time"] = df["time"].astype(str).str[:5]
    df["month"] = df["date"].str[:6]
    tickers = [str(t).upper() for t in args.tickers]
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df = df[df["ticker"].isin(tickers)].copy()
    metadata = {
        "args": vars(args),
        "split": asdict(split),
        "feature_count": len(split.all_features),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    write_feature_names(
        output_dir / "jepa_feature_names.json",
        [f"xjepa_z_{i:02d}" for i in range(int(args.z_dim))]
        + [f"xjepa_u_{i:02d}" for i in range(int(args.u_dim))]
        + [
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
        ],
    )
    fold_rows, done = load_done(output_dir, resume=not args.no_resume)
    months = [m for m in sorted(df["month"].unique()) if str(args.start_month) <= str(m) <= str(args.end_month)]
    device = torch.device(args.device)
    for ticker in tickers:
        t_frame = df[df["ticker"] == ticker].copy()
        for test_month in months:
            fold_key = (ticker, str(test_month))
            chunk_path = chunk_dir / f"{ticker}_{test_month}.parquet"
            if fold_key in done and chunk_path.exists():
                print(f"[XINPUT_OOF] skip checkpointed {ticker} {test_month}", flush=True)
                continue
            fold_seed = int(args.seed) + int(test_month[-2:]) + 1000 * (tickers.index(ticker) + 1)
            set_seed(fold_seed)
            features, fold_row = train_fold(ticker, str(test_month), t_frame, split, args, device)
            features.to_parquet(chunk_path, index=False)
            fold_rows.append(fold_row)
            pd.DataFrame(fold_rows).to_csv(output_dir / "fold_configs.csv", index=False)
            done.add(fold_key)
            consolidate_features(output_dir)
            write_summary(output_dir, metadata, fold_rows)
            print(
                f"[XINPUT_OOF] {ticker} {test_month} rows={len(features)} "
                f"ctx_valid={fold_row['context_valid_rate']:.3f} "
                f"best_epoch={fold_row['best_epoch']} val_total={fold_row['val_total']:.4f} "
                f"val_acc={fold_row['val_acc']:.3f}",
                flush=True,
            )
    consolidate_features(output_dir)
    write_summary(output_dir, metadata, fold_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
