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
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.dataset import RobustNormalizer, TemporalJEPADataset, prepare_jepa_frame, split_dates
from neural.jepa.features import write_feature_names
from neural.jepa.model import JEPAConfig, TemporalJEPA, save_model
from neural.jepa.sigreg import SIGRegLoss, latent_diagnostics


def parse_horizons(text: str) -> list[int]:
    return [int(x.strip()) for x in str(text).split(",") if x.strip()]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def evaluate(model: TemporalJEPA, loader: DataLoader, sigreg: SIGRegLoss, lambda_sigreg: float, device: torch.device) -> dict:
    model.eval()
    total = 0
    pred_sum = 0.0
    sig_sum = 0.0
    z_batches = []
    with torch.no_grad():
        for ctx, targets in loader:
            ctx = ctx.to(device, non_blocking=True).float()
            targets = targets.to(device, non_blocking=True).float()
            b, h, l, f = targets.shape
            z = model.encode(ctx)
            target_z = model.encode(targets.reshape(b * h, l, f)).reshape(b, h, -1)
            pred_z = model.predict(z)
            pred_loss = F.mse_loss(pred_z, target_z)
            sig_loss = sigreg(torch.cat([z, target_z.reshape(b * h, -1)], dim=0))
            n = len(ctx)
            total += n
            pred_sum += float(pred_loss.item()) * n
            sig_sum += float(sig_loss.item()) * n
            if len(z_batches) < 20:
                z_batches.append(z.detach().cpu())
    pred_avg = pred_sum / max(1, total)
    sig_avg = sig_sum / max(1, total)
    diag = latent_diagnostics(torch.cat(z_batches, dim=0)) if z_batches else {}
    return {
        "prediction_loss": pred_avg,
        "sigreg_loss": sig_avg,
        "total_loss": pred_avg + lambda_sigreg * sig_avg,
        **{f"diag_{k}": v for k, v in diag.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a Temporal Tabular LeJEPA encoder.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--context-len", type=int, default=24)
    parser.add_argument("--horizons", default="1,3,6,12,24,36")
    parser.add_argument("--z-dim", type=int, default=32)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.10)
    parser.add_argument("--lambda-sigreg", type=float, default=0.05)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-2)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--clip", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--num-workers", type=int, default=0)
    args = parser.parse_args()

    set_seed(args.seed)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    horizons = parse_horizons(args.horizons)
    df, feature_names = prepare_jepa_frame(args.data)
    train_dates, val_dates = split_dates(df, val_fraction=args.val_fraction)
    train_df = df[df["date"].astype(str).isin(train_dates)].copy()

    normalizer = RobustNormalizer.fit(train_df, feature_names, clip=args.clip)
    normalizer.save(out / "normalizer.json")
    (out / "feature_columns.json").write_text(
        json.dumps({"feature_names": feature_names}, indent=2),
        encoding="utf-8",
    )

    train_ds = TemporalJEPADataset(df, normalizer, args.context_len, horizons, train_dates)
    val_ds = TemporalJEPADataset(df, normalizer, args.context_len, horizons, val_dates)
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
        drop_last=False,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
        drop_last=False,
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
    model = TemporalJEPA(config).to(device)
    sigreg = SIGRegLoss(args.z_dim).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    resolved_config = vars(args).copy()
    resolved_config.update(
        {
            "horizons": horizons,
            "n_rows": int(len(df)),
            "n_train_dates": int(len(train_dates)),
            "n_val_dates": int(len(val_dates)),
            "n_train_windows": int(len(train_ds)),
            "n_val_windows": int(len(val_ds)),
            "input_dim": int(len(feature_names)),
        }
    )
    (out / "config.json").write_text(json.dumps(resolved_config, indent=2), encoding="utf-8")

    metrics_path = out / "metrics.csv"
    best_loss = float("inf")
    best_epoch = 0
    bad_epochs = 0
    fieldnames = [
        "epoch",
        "train_prediction_loss",
        "train_sigreg_loss",
        "train_total_loss",
        "val_prediction_loss",
        "val_sigreg_loss",
        "val_total_loss",
        "val_effective_rank_ratio",
        "val_max_pc_var_ratio",
        "lr",
    ]

    with metrics_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for epoch in range(1, args.epochs + 1):
            model.train()
            total = 0
            pred_sum = 0.0
            sig_sum = 0.0
            for ctx, targets in train_loader:
                ctx = ctx.to(device, non_blocking=True).float()
                targets = targets.to(device, non_blocking=True).float()
                b, h, l, feat = targets.shape
                z = model.encode(ctx)
                target_z = model.encode(targets.reshape(b * h, l, feat)).reshape(b, h, -1)
                pred_z = model.predict(z)
                pred_loss = F.mse_loss(pred_z, target_z)
                sig_loss = sigreg(torch.cat([z, target_z.reshape(b * h, -1)], dim=0))
                loss = pred_loss + args.lambda_sigreg * sig_loss

                opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()

                n = len(ctx)
                total += n
                pred_sum += float(pred_loss.item()) * n
                sig_sum += float(sig_loss.item()) * n

            train_pred = pred_sum / max(1, total)
            train_sig = sig_sum / max(1, total)
            train_total = train_pred + args.lambda_sigreg * train_sig
            val = evaluate(model, val_loader, sigreg, args.lambda_sigreg, device)
            row = {
                "epoch": epoch,
                "train_prediction_loss": train_pred,
                "train_sigreg_loss": train_sig,
                "train_total_loss": train_total,
                "val_prediction_loss": val["prediction_loss"],
                "val_sigreg_loss": val["sigreg_loss"],
                "val_total_loss": val["total_loss"],
                "val_effective_rank_ratio": val.get("diag_effective_rank_ratio", 0.0),
                "val_max_pc_var_ratio": val.get("diag_max_pc_var_ratio", 1.0),
                "lr": opt.param_groups[0]["lr"],
            }
            writer.writerow(row)
            f.flush()

            print(
                f"epoch={epoch:03d} train={train_total:.6f} "
                f"val={val['total_loss']:.6f} pred={val['prediction_loss']:.6f} "
                f"sig={val['sigreg_loss']:.6f} rank={row['val_effective_rank_ratio']:.3f}"
            )

            if val["total_loss"] < best_loss - 1e-5:
                best_loss = val["total_loss"]
                best_epoch = epoch
                bad_epochs = 0
                save_model(model, out, extra={"best_epoch": best_epoch, "best_val_loss": best_loss})
            else:
                bad_epochs += 1
                if bad_epochs >= args.patience:
                    print(f"early_stop epoch={epoch} best_epoch={best_epoch} best_val_loss={best_loss:.6f}")
                    break

    live_safe = [f"jepa_z_{i:02d}" for i in range(args.z_dim)] + [
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
    write_feature_names(out / "jepa_feature_names.json", live_safe)
    print(f"saved_best_model={out / 'model.pt'} best_epoch={best_epoch} best_val_loss={best_loss:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

