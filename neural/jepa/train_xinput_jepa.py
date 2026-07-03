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

from neural.jepa.dataset import split_dates
from neural.jepa.features import write_feature_names
from neural.jepa.sigreg import (
    SIGRegLoss,
    VISRegLoss,
    VarianceCovarianceLoss,
    latent_diagnostics,
    latent_temporal_straightening_loss,
)
from neural.jepa.xinput_dataset import XInputJEPADataset, fit_xinput_normalizers, prepare_xinput_frame
from neural.jepa.xinput_model import XInputJEPAConfig, XInputMarketJEPA, save_xinput_model


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


def direction_metrics(logits: torch.Tensor, y: torch.Tensor) -> dict:
    probs = torch.softmax(logits, dim=-1)
    pred = probs.argmax(dim=-1)
    trade_mask = pred != 1
    return {
        "acc": float((pred == y).float().mean().item()),
        "trade_precision": float((pred[trade_mask] == y[trade_mask]).float().mean().item()) if trade_mask.any() else 0.0,
        "trade_rate": float(trade_mask.float().mean().item()),
        "avg_trade_conf": float(probs[:, [0, 2]].max(dim=1).values.mean().item()),
    }


def evaluate(model, loader, sigreg, visreg, vicreg, ce_weight, args, device) -> dict:
    model.eval()
    total = 0
    sums = {"pred": 0.0, "sig": 0.0, "vis": 0.0, "vic": 0.0, "straight": 0.0, "ce": 0.0, "total": 0.0}
    logits_all, y_all, z_batches, u_batches = [], [], [], []
    with torch.no_grad():
        for state_ctx, input_ctx, targets, y in loader:
            state_ctx = state_ctx.to(device).float()
            input_ctx = input_ctx.to(device).float()
            targets = targets.to(device).float()
            y = y.to(device)
            b, h, l, f = targets.shape
            z, u, pred_z, logits = model(state_ctx, input_ctx)
            target_z = model.encode_state(targets.reshape(b * h, l, f)).reshape(b, h, -1)
            pred_loss = F.mse_loss(pred_z, target_z.detach())
            z_all = torch.cat([z, target_z.reshape(b * h, -1)], dim=0)
            sig_loss = sigreg(z_all)
            vis_loss = visreg(z_all)
            vic_loss = vicreg(z_all)
            straight_loss = latent_temporal_straightening_loss(
                torch.cat([z.unsqueeze(1), target_z], dim=1),
                speed_weight=float(args.straightening_speed_weight),
            )
            ce_loss = F.cross_entropy(logits, y, weight=ce_weight)
            loss = (
                pred_loss
                + args.lambda_sigreg * sig_loss
                + args.lambda_visreg * vis_loss
                + args.lambda_vicreg * vic_loss
                + args.lambda_straightening * straight_loss
                + args.lambda_ce * ce_loss
            )
            n = len(state_ctx)
            total += n
            sums["pred"] += float(pred_loss.item()) * n
            sums["sig"] += float(sig_loss.item()) * n
            sums["vis"] += float(vis_loss.item()) * n
            sums["vic"] += float(vic_loss.item()) * n
            sums["straight"] += float(straight_loss.item()) * n
            sums["ce"] += float(ce_loss.item()) * n
            sums["total"] += float(loss.item()) * n
            logits_all.append(logits.cpu())
            y_all.append(y.cpu())
            if len(z_batches) < 20:
                z_batches.append(z.cpu())
                u_batches.append(u.cpu())
    metrics = {k: v / max(1, total) for k, v in sums.items()}
    metrics.update(direction_metrics(torch.cat(logits_all), torch.cat(y_all)))
    metrics.update({f"diag_z_{k}": v for k, v in latent_diagnostics(torch.cat(z_batches)).items()})
    metrics.update({f"diag_u_{k}": v for k, v in latent_diagnostics(torch.cat(u_batches)).items()})
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Train explicit exogenous-input Market JEPA.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--context-len", type=int, default=24)
    parser.add_argument("--horizons", default="1,3,6,12,24,36")
    parser.add_argument("--z-dim", type=int, default=16)
    parser.add_argument("--u-dim", type=int, default=12)
    parser.add_argument("--hidden-dim", type=int, default=96)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.15)
    parser.add_argument("--lambda-sigreg", type=float, default=0.15)
    parser.add_argument("--lambda-visreg", type=float, default=0.0)
    parser.add_argument("--lambda-vicreg", type=float, default=0.20)
    parser.add_argument("--lambda-straightening", type=float, default=0.0)
    parser.add_argument("--straightening-speed-weight", type=float, default=0.0)
    parser.add_argument("--lambda-ce", type=float, default=0.35)
    parser.add_argument("--visreg-slices", type=int, default=64)
    parser.add_argument("--visreg-center-weight", type=float, default=1.0)
    parser.add_argument("--visreg-scale-weight", type=float, default=1.0)
    parser.add_argument("--visreg-shape-weight", type=float, default=1.0)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=7e-4)
    parser.add_argument("--weight-decay", type=float, default=2e-2)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--clip", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=44)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--balanced-sampler", action="store_true")
    parser.add_argument(
        "--final-fit-all-dates",
        action="store_true",
        help="After selecting best_epoch on validation, refit a fresh production model on all available dates.",
    )
    args = parser.parse_args()

    set_seed(args.seed)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    horizons = parse_horizons(args.horizons)
    df, split = prepare_xinput_frame(args.data)
    train_dates, val_dates = split_dates(df, args.val_fraction)
    normalizers = fit_xinput_normalizers(df, split, train_dates, clip=args.clip)
    normalizers.save(out / "normalizers.json")
    (out / "feature_split.json").write_text(
        json.dumps(
            {"state_features": split.state_features, "input_features": split.input_features},
            indent=2,
        ),
        encoding="utf-8",
    )

    train_ds = XInputJEPADataset(df, normalizers, args.context_len, horizons, train_dates)
    val_ds = XInputJEPADataset(df, normalizers, args.context_len, horizons, val_dates)
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

    config = XInputJEPAConfig(
        state_dim=len(split.state_features),
        input_dim=len(split.input_features),
        context_len=args.context_len,
        horizons=horizons,
        hidden_dim=args.hidden_dim,
        z_dim=args.z_dim,
        u_dim=args.u_dim,
        num_layers=args.num_layers,
        dropout=args.dropout,
    )
    device = torch.device(args.device)
    model = XInputMarketJEPA(config).to(device)
    sigreg = SIGRegLoss(args.z_dim, num_projections=96).to(device)
    visreg = VISRegLoss(
        args.z_dim,
        num_slices=int(args.visreg_slices),
        center_weight=float(args.visreg_center_weight),
        scale_weight=float(args.visreg_scale_weight),
        shape_weight=float(args.visreg_shape_weight),
    ).to(device)
    vicreg = VarianceCovarianceLoss(min_std=0.75, cov_weight=0.05, var_weight=1.0).to(device)
    ce_weight = class_weights(train_ds.labels, device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    resolved = vars(args).copy()
    resolved.update(
        {
            "horizons": horizons,
            "state_dim": len(split.state_features),
            "input_dim": len(split.input_features),
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
        "train_vis",
        "train_vic",
        "train_straight",
        "train_ce",
        "val_total",
        "val_pred",
        "val_sig",
        "val_vis",
        "val_vic",
        "val_straight",
        "val_ce",
        "val_acc",
        "val_trade_precision",
        "val_trade_rate",
        "val_z_rank",
        "val_u_rank",
    ]
    best_score = float("inf")
    best_epoch = 0
    bad = 0
    with (out / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for epoch in range(1, args.epochs + 1):
            model.train()
            sums = {"pred": 0.0, "sig": 0.0, "vis": 0.0, "vic": 0.0, "straight": 0.0, "ce": 0.0, "total": 0.0}
            total = 0
            for state_ctx, input_ctx, targets, y in train_loader:
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
                vis_loss = visreg(z_all)
                vic_loss = vicreg(z_all)
                straight_loss = latent_temporal_straightening_loss(
                    torch.cat([z.unsqueeze(1), target_z], dim=1),
                    speed_weight=float(args.straightening_speed_weight),
                )
                ce_loss = F.cross_entropy(logits, y, weight=ce_weight)
                loss = (
                    pred_loss
                    + args.lambda_sigreg * sig_loss
                    + args.lambda_visreg * vis_loss
                    + args.lambda_vicreg * vic_loss
                    + args.lambda_straightening * straight_loss
                    + args.lambda_ce * ce_loss
                )
                opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                n = len(state_ctx)
                total += n
                sums["pred"] += float(pred_loss.item()) * n
                sums["sig"] += float(sig_loss.item()) * n
                sums["vis"] += float(vis_loss.item()) * n
                sums["vic"] += float(vic_loss.item()) * n
                sums["straight"] += float(straight_loss.item()) * n
                sums["ce"] += float(ce_loss.item()) * n
                sums["total"] += float(loss.item()) * n

            train = {k: v / max(1, total) for k, v in sums.items()}
            val = evaluate(model, val_loader, sigreg, visreg, vicreg, ce_weight, args, device)
            row = {
                "epoch": epoch,
                "train_total": train["total"],
                "train_pred": train["pred"],
                "train_sig": train["sig"],
                "train_vis": train["vis"],
                "train_vic": train["vic"],
                "train_straight": train["straight"],
                "train_ce": train["ce"],
                "val_total": val["total"],
                "val_pred": val["pred"],
                "val_sig": val["sig"],
                "val_vis": val["vis"],
                "val_vic": val["vic"],
                "val_straight": val["straight"],
                "val_ce": val["ce"],
                "val_acc": val["acc"],
                "val_trade_precision": val["trade_precision"],
                "val_trade_rate": val["trade_rate"],
                "val_z_rank": val["diag_z_effective_rank_ratio"],
                "val_u_rank": val["diag_u_effective_rank_ratio"],
            }
            writer.writerow(row)
            f.flush()
            print(
                f"epoch={epoch:03d} train={train['total']:.5f} val={val['total']:.5f} "
                f"ce={val['ce']:.4f} acc={val['acc']:.3f} trade_prec={val['trade_precision']:.3f} "
                f"z_rank={val['diag_z_effective_rank_ratio']:.3f} u_rank={val['diag_u_effective_rank_ratio']:.3f}"
            )
            health_penalty = max(0.0, 0.50 - float(val["diag_z_effective_rank_ratio"]))
            score = float(val["total"]) + 0.25 * health_penalty
            if score < best_score - 1e-5:
                best_score = score
                best_epoch = epoch
                bad = 0
                save_xinput_model(model, out, extra={"best_epoch": best_epoch, "best_score": best_score})
            else:
                bad += 1
                if bad >= args.patience:
                    print(f"early_stop epoch={epoch} best_epoch={best_epoch} best_score={best_score:.6f}")
                    break

    if args.final_fit_all_dates:
        all_dates = set(df["date"].astype(str).unique().tolist())
        final_epochs = max(1, int(best_epoch or args.epochs))
        print(f"production_final_fit_all_dates=true epochs={final_epochs} dates={len(all_dates)}")
        final_normalizers = fit_xinput_normalizers(df, split, all_dates, clip=args.clip)
        final_normalizers.save(out / "normalizers.json")
        final_ds = XInputJEPADataset(df, final_normalizers, args.context_len, horizons, all_dates)
        final_sampler = sampler_for_labels(final_ds.labels) if args.balanced_sampler else None
        final_loader = DataLoader(
            final_ds,
            batch_size=args.batch_size,
            shuffle=final_sampler is None,
            sampler=final_sampler,
            num_workers=args.num_workers,
            pin_memory=torch.cuda.is_available(),
        )
        model = XInputMarketJEPA(config).to(device)
        sigreg = SIGRegLoss(args.z_dim, num_projections=96).to(device)
        visreg = VISRegLoss(
            args.z_dim,
            num_slices=int(args.visreg_slices),
            center_weight=float(args.visreg_center_weight),
            scale_weight=float(args.visreg_scale_weight),
            shape_weight=float(args.visreg_shape_weight),
        ).to(device)
        vicreg = VarianceCovarianceLoss(min_std=0.75, cov_weight=0.05, var_weight=1.0).to(device)
        ce_weight = class_weights(final_ds.labels, device)
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

        for epoch in range(1, final_epochs + 1):
            model.train()
            sums = {"pred": 0.0, "sig": 0.0, "vis": 0.0, "vic": 0.0, "straight": 0.0, "ce": 0.0, "total": 0.0}
            total = 0
            for state_ctx, input_ctx, targets, y in final_loader:
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
                vis_loss = visreg(z_all)
                vic_loss = vicreg(z_all)
                straight_loss = latent_temporal_straightening_loss(
                    torch.cat([z.unsqueeze(1), target_z], dim=1),
                    speed_weight=float(args.straightening_speed_weight),
                )
                ce_loss = F.cross_entropy(logits, y, weight=ce_weight)
                loss = (
                    pred_loss
                    + args.lambda_sigreg * sig_loss
                    + args.lambda_visreg * vis_loss
                    + args.lambda_vicreg * vic_loss
                    + args.lambda_straightening * straight_loss
                    + args.lambda_ce * ce_loss
                )
                opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                n = len(state_ctx)
                total += n
                sums["pred"] += float(pred_loss.item()) * n
                sums["sig"] += float(sig_loss.item()) * n
                sums["vis"] += float(vis_loss.item()) * n
                sums["vic"] += float(vic_loss.item()) * n
                sums["straight"] += float(straight_loss.item()) * n
                sums["ce"] += float(ce_loss.item()) * n
                sums["total"] += float(loss.item()) * n
            train = {k: v / max(1, total) for k, v in sums.items()}
            if epoch == 1 or epoch == final_epochs or epoch % 5 == 0:
                print(
                    f"production_epoch={epoch:03d} total={train['total']:.5f} "
                    f"pred={train['pred']:.5f} ce={train['ce']:.5f}"
                )

        save_xinput_model(
            model,
            out,
            extra={
                "production_final_fit": True,
                "selected_best_epoch": int(best_epoch),
                "final_epochs": int(final_epochs),
                "final_dates": int(len(all_dates)),
                "final_windows": int(len(final_ds)),
            },
        )
        resolved["production_final_fit"] = True
        resolved["production_final_epochs"] = int(final_epochs)
        resolved["production_final_dates"] = int(len(all_dates))
        resolved["production_final_windows"] = int(len(final_ds))
        (out / "config.json").write_text(json.dumps(resolved, indent=2), encoding="utf-8")

    live_safe = [f"xjepa_z_{i:02d}" for i in range(args.z_dim)] + [f"xjepa_u_{i:02d}" for i in range(args.u_dim)] + [
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
    write_feature_names(out / "jepa_feature_names.json", live_safe)
    print(f"saved_best_model={out / 'model.pt'} best_epoch={best_epoch} best_score={best_score:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
