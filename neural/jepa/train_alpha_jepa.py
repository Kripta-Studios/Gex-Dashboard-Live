from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, WeightedRandomSampler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.dataset import AlphaTemporalJEPADataset, RobustNormalizer, prepare_jepa_frame, split_dates
from neural.jepa.features import write_feature_names
from neural.jepa.model import AlphaTemporalJEPA, JEPAConfig, save_model
from neural.jepa.sigreg import SIGRegLoss, VarianceCovarianceLoss, latent_diagnostics


def parse_horizons(text: str) -> list[int]:
    return [int(x.strip()) for x in str(text).split(",") if x.strip()]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


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


def directional_metrics(logits: torch.Tensor, y: torch.Tensor) -> dict:
    probs = torch.softmax(logits, dim=-1)
    pred = probs.argmax(dim=-1)
    out = {"acc": float((pred == y).float().mean().item())}
    for cls, name in [(0, "short"), (2, "long")]:
        mask = y == cls
        if mask.any():
            out[f"{name}_recall"] = float((pred[mask] == cls).float().mean().item())
        else:
            out[f"{name}_recall"] = 0.0
    trade_mask = pred != 1
    if trade_mask.any():
        out["trade_precision"] = float((pred[trade_mask] == y[trade_mask]).float().mean().item())
        out["trade_rate"] = float(trade_mask.float().mean().item())
    else:
        out["trade_precision"] = 0.0
        out["trade_rate"] = 0.0
    return out


def run_eval(
    model: AlphaTemporalJEPA,
    loader: DataLoader,
    sigreg: SIGRegLoss,
    vicreg: VarianceCovarianceLoss,
    ce_weight: torch.Tensor,
    args,
    device: torch.device,
) -> dict:
    model.eval()
    total = 0
    sums = {"pred": 0.0, "sig": 0.0, "vic": 0.0, "ce": 0.0, "total": 0.0}
    logits_all = []
    y_all = []
    z_batches = []
    with torch.no_grad():
        for ctx, targets, y in loader:
            ctx = ctx.to(device, non_blocking=True).float()
            targets = targets.to(device, non_blocking=True).float()
            y = y.to(device, non_blocking=True)
            b, h, l, f = targets.shape
            z, pred_z, logits = model(ctx)
            target_z = model.encode(targets.reshape(b * h, l, f)).reshape(b, h, -1)
            if args.stop_gradient_target:
                target_for_pred = target_z.detach()
            else:
                target_for_pred = target_z
            pred_loss = F.mse_loss(pred_z, target_for_pred)
            z_all = torch.cat([z, target_z.reshape(b * h, -1)], dim=0)
            sig_loss = sigreg(z_all)
            vic_loss = vicreg(z_all)
            ce_loss = F.cross_entropy(logits, y, weight=ce_weight)
            loss = (
                pred_loss
                + args.lambda_sigreg * sig_loss
                + args.lambda_vicreg * vic_loss
                + args.lambda_ce * ce_loss
            )
            n = len(ctx)
            total += n
            sums["pred"] += float(pred_loss.item()) * n
            sums["sig"] += float(sig_loss.item()) * n
            sums["vic"] += float(vic_loss.item()) * n
            sums["ce"] += float(ce_loss.item()) * n
            sums["total"] += float(loss.item()) * n
            logits_all.append(logits.cpu())
            y_all.append(y.cpu())
            if len(z_batches) < 20:
                z_batches.append(z.detach().cpu())
    metrics = {k: v / max(1, total) for k, v in sums.items()}
    metrics.update(directional_metrics(torch.cat(logits_all), torch.cat(y_all)))
    metrics.update({f"diag_{k}": v for k, v in latent_diagnostics(torch.cat(z_batches)).items()})
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Train AlphaJEPA v2 with trading-aligned auxiliary heads.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--context-len", type=int, default=24)
    parser.add_argument("--horizons", default="1,3,6,12,24,36")
    parser.add_argument("--z-dim", type=int, default=16)
    parser.add_argument("--hidden-dim", type=int, default=96)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.15)
    parser.add_argument("--lambda-sigreg", type=float, default=0.15)
    parser.add_argument("--lambda-vicreg", type=float, default=0.20)
    parser.add_argument("--lambda-ce", type=float, default=0.35)
    parser.add_argument("--stop-gradient-target", action="store_true")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=7e-4)
    parser.add_argument("--weight-decay", type=float, default=2e-2)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--clip", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--balanced-sampler", action="store_true")
    args = parser.parse_args()

    set_seed(args.seed)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    horizons = parse_horizons(args.horizons)
    df, feature_names = prepare_jepa_frame(args.data)
    train_dates, val_dates = split_dates(df, args.val_fraction)
    train_df = df[df["date"].astype(str).isin(train_dates)].copy()
    normalizer = RobustNormalizer.fit(train_df, feature_names, clip=args.clip)
    normalizer.save(out / "normalizer.json")
    (out / "feature_columns.json").write_text(
        json.dumps({"feature_names": feature_names}, indent=2),
        encoding="utf-8",
    )

    train_ds = AlphaTemporalJEPADataset(df, normalizer, args.context_len, horizons, train_dates)
    val_ds = AlphaTemporalJEPADataset(df, normalizer, args.context_len, horizons, val_dates)
    sampler = sampler_for_labels(train_ds.labels) if args.balanced_sampler else None
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=sampler is None,
        sampler=sampler,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
    )

    config = JEPAConfig(
        input_dim=len(feature_names),
        context_len=args.context_len,
        horizons=horizons,
        hidden_dim=args.hidden_dim,
        z_dim=args.z_dim,
        num_layers=args.num_layers,
        dropout=args.dropout,
    )
    device = torch.device(args.device)
    model = AlphaTemporalJEPA(config).to(device)
    sigreg = SIGRegLoss(args.z_dim, num_projections=96).to(device)
    vicreg = VarianceCovarianceLoss(min_std=0.75, cov_weight=0.05, var_weight=1.0).to(device)
    ce_weight = class_weights(train_ds.labels, device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    resolved = vars(args).copy()
    resolved.update(
        {
            "horizons": horizons,
            "input_dim": len(feature_names),
            "n_rows": len(df),
            "n_train_dates": len(train_dates),
            "n_val_dates": len(val_dates),
            "n_train_windows": len(train_ds),
            "n_val_windows": len(val_ds),
            "class_weights": ce_weight.detach().cpu().tolist(),
        }
    )
    (out / "config.json").write_text(json.dumps(resolved, indent=2), encoding="utf-8")

    fields = [
        "epoch",
        "train_total",
        "train_pred",
        "train_sig",
        "train_vic",
        "train_ce",
        "val_total",
        "val_pred",
        "val_sig",
        "val_vic",
        "val_ce",
        "val_acc",
        "val_trade_precision",
        "val_trade_rate",
        "val_effective_rank_ratio",
        "val_max_pc_var_ratio",
    ]
    best_score = float("inf")
    best_epoch = 0
    bad = 0
    with (out / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for epoch in range(1, args.epochs + 1):
            model.train()
            sums = {"pred": 0.0, "sig": 0.0, "vic": 0.0, "ce": 0.0, "total": 0.0}
            total = 0
            for ctx, targets, y in train_loader:
                ctx = ctx.to(device, non_blocking=True).float()
                targets = targets.to(device, non_blocking=True).float()
                y = y.to(device, non_blocking=True)
                b, h, l, feat = targets.shape
                z, pred_z, logits = model(ctx)
                target_z = model.encode(targets.reshape(b * h, l, feat)).reshape(b, h, -1)
                target_for_pred = target_z.detach() if args.stop_gradient_target else target_z
                pred_loss = F.mse_loss(pred_z, target_for_pred)
                z_all = torch.cat([z, target_z.reshape(b * h, -1)], dim=0)
                sig_loss = sigreg(z_all)
                vic_loss = vicreg(z_all)
                ce_loss = F.cross_entropy(logits, y, weight=ce_weight)
                loss = (
                    pred_loss
                    + args.lambda_sigreg * sig_loss
                    + args.lambda_vicreg * vic_loss
                    + args.lambda_ce * ce_loss
                )
                opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                n = len(ctx)
                total += n
                sums["pred"] += float(pred_loss.item()) * n
                sums["sig"] += float(sig_loss.item()) * n
                sums["vic"] += float(vic_loss.item()) * n
                sums["ce"] += float(ce_loss.item()) * n
                sums["total"] += float(loss.item()) * n

            train = {k: v / max(1, total) for k, v in sums.items()}
            val = run_eval(model, val_loader, sigreg, vicreg, ce_weight, args, device)
            row = {
                "epoch": epoch,
                "train_total": train["total"],
                "train_pred": train["pred"],
                "train_sig": train["sig"],
                "train_vic": train["vic"],
                "train_ce": train["ce"],
                "val_total": val["total"],
                "val_pred": val["pred"],
                "val_sig": val["sig"],
                "val_vic": val["vic"],
                "val_ce": val["ce"],
                "val_acc": val["acc"],
                "val_trade_precision": val["trade_precision"],
                "val_trade_rate": val["trade_rate"],
                "val_effective_rank_ratio": val["diag_effective_rank_ratio"],
                "val_max_pc_var_ratio": val["diag_max_pc_var_ratio"],
            }
            writer.writerow(row)
            f.flush()
            print(
                f"epoch={epoch:03d} train={train['total']:.5f} val={val['total']:.5f} "
                f"ce={val['ce']:.4f} acc={val['acc']:.3f} trade_prec={val['trade_precision']:.3f} "
                f"rank={val['diag_effective_rank_ratio']:.3f}"
            )

            # Favor useful validation loss, but reject increasingly collapsed models.
            health_penalty = max(0.0, 0.50 - float(val["diag_effective_rank_ratio"]))
            score = float(val["total"]) + 0.25 * health_penalty
            if score < best_score - 1e-5:
                best_score = score
                best_epoch = epoch
                bad = 0
                save_model(model, out, extra={"best_epoch": best_epoch, "best_score": best_score})
            else:
                bad += 1
                if bad >= args.patience:
                    print(f"early_stop epoch={epoch} best_epoch={best_epoch} best_score={best_score:.6f}")
                    break

    live_safe = [f"ajepa_z_{i:02d}" for i in range(args.z_dim)] + [
        "ajepa_latent_velocity",
        "ajepa_latent_accel",
        "ajepa_pred_dispersion_short",
        "ajepa_pred_dispersion_long",
        "ajepa_lagged_pred_30m_err",
        "ajepa_lagged_pred_60m_err",
        "ajepa_lagged_pred_180m_err",
        "ajepa_prob_short",
        "ajepa_prob_hold",
        "ajepa_prob_long",
        "ajepa_trade_confidence",
        "ajepa_direction_score",
        "ajepa_entropy",
        "ajepa_context_valid",
    ]
    write_feature_names(out / "jepa_feature_names.json", live_safe)
    print(f"saved_best_model={out / 'model.pt'} best_epoch={best_epoch} best_score={best_score:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

