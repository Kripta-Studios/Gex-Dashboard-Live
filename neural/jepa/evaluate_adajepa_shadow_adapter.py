from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from scipy.stats import wilcoxon
from torch import nn


class DiagonalResidualAdapter(nn.Module):
    def __init__(self, z_dim: int) -> None:
        super().__init__()
        self.motion_scale = nn.Parameter(torch.zeros(int(z_dim)))
        self.bias = nn.Parameter(torch.zeros(int(z_dim)))

    def forward(self, z_t: torch.Tensor, base_prediction: torch.Tensor) -> torch.Tensor:
        motion = base_prediction - z_t
        return base_prediction + self.motion_scale * motion + self.bias


def parameter_norm(model: nn.Module) -> float:
    return float(torch.sqrt(sum(parameter.detach().square().sum() for parameter in model.parameters())).cpu())


def update_adapter(
    model: DiagonalResidualAdapter,
    optimizer: torch.optim.Optimizer,
    z_t: torch.Tensor,
    base_prediction: torch.Tensor,
    observed_target: torch.Tensor,
    *,
    grad_clip: float,
    max_parameter_norm: float,
) -> tuple[float, bool]:
    before = {name: value.detach().clone() for name, value in model.state_dict().items()}
    optimizer.zero_grad(set_to_none=True)
    prediction = model(z_t, base_prediction)
    loss = torch.mean((prediction - observed_target).square())
    loss.backward()
    nn.utils.clip_grad_norm_(model.parameters(), float(grad_clip))
    optimizer.step()
    norm = parameter_norm(model)
    rollback = not math.isfinite(norm) or norm > float(max_parameter_norm)
    if rollback:
        model.load_state_dict(before)
    return float(loss.detach().cpu()), bool(rollback)


def latent_columns(frame: pd.DataFrame, prefix: str) -> list[str]:
    columns = sorted(column for column in frame.columns if column.startswith(prefix))
    if len(columns) != 32:
        raise ValueError(f"expected 32 {prefix} columns, got {len(columns)}")
    return columns


def evaluate_day(
    day: pd.DataFrame,
    *,
    learning_rate: float,
    grad_clip: float,
    max_parameter_norm: float,
    device: torch.device,
    include_live_vectors: bool = False,
) -> pd.DataFrame:
    ordered = day.sort_values(["timestamp", "target_timestamp"], kind="stable").reset_index(drop=True)
    z_cols = latent_columns(ordered, "z_t_")
    pred_cols = latent_columns(ordered, "pred_z_")
    target_cols = latent_columns(ordered, "target_z_")
    model = DiagonalResidualAdapter(len(z_cols)).to(device)
    optimizer = torch.optim.SGD(model.parameters(), lr=float(learning_rate))
    records: list[dict[str, Any]] = []
    previous: tuple[torch.Tensor, torch.Tensor, torch.Tensor, pd.Timestamp] | None = None
    updates = 0
    rollbacks = 0
    for row in ordered.itertuples(index=False):
        current_timestamp = pd.Timestamp(row.timestamp)
        if previous is not None:
            previous_z, previous_prediction, previous_target, available_at = previous
            if available_at > current_timestamp:
                raise RuntimeError("attempted to adapt before the previous target became observable")
            _, rolled_back = update_adapter(
                model,
                optimizer,
                previous_z,
                previous_prediction,
                previous_target,
                grad_clip=grad_clip,
                max_parameter_norm=max_parameter_norm,
            )
            updates += 1
            rollbacks += int(rolled_back)
        z_t = torch.tensor([getattr(row, column) for column in z_cols], dtype=torch.float32, device=device)
        base = torch.tensor([getattr(row, column) for column in pred_cols], dtype=torch.float32, device=device)
        target = torch.tensor([getattr(row, column) for column in target_cols], dtype=torch.float32, device=device)
        with torch.no_grad():
            adapted = model(z_t, base)
        base_error = float(torch.linalg.vector_norm(base - target).cpu())
        adapted_error = float(torch.linalg.vector_norm(adapted - target).cpu())
        persistence_error = float(torch.linalg.vector_norm(z_t - target).cpu())
        record: dict[str, Any] = {
                "ticker": str(row.ticker),
                "trade_date": str(row.trade_date),
                "expiration": str(row.expiration),
                "expiry_mode": str(row.expiry_mode),
                "month": str(row.trade_date)[:6],
                "timestamp": row.timestamp,
                "time": row.time,
                "target_timestamp": row.target_timestamp,
                "minute": int(row.minute),
                "updates_before_prediction": updates,
                "rollbacks_before_prediction": rollbacks,
                "adapter_parameter_norm": parameter_norm(model),
                "persistence_error": persistence_error,
                "frozen_error": base_error,
                "adapted_error": adapted_error,
            }
        if include_live_vectors:
            frozen_motion = base - z_t
            adapted_motion = adapted - z_t
            for dimension in range(len(z_cols)):
                record[f"ada_z_{dimension:02d}"] = float(z_t[dimension].cpu())
                record[f"ada_frozen_dz_{dimension:02d}"] = float(frozen_motion[dimension].cpu())
                record[f"ada_adapted_dz_{dimension:02d}"] = float(adapted_motion[dimension].cpu())
        records.append(record)
        previous = (z_t, base, target, pd.Timestamp(row.target_available_after_timestamp))
    return pd.DataFrame(records)


def evaluate_frame(
    frame: pd.DataFrame,
    *,
    learning_rate: float,
    grad_clip: float,
    max_parameter_norm: float,
    device: str,
    include_live_vectors: bool = False,
) -> pd.DataFrame:
    work = frame.copy()
    work["trade_date"] = work["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
    if int(work["trade_date"].astype(int).max()) >= 20260601:
        raise ValueError("June 2026 seal violated")
    outputs = []
    target_device = torch.device(device)
    for _, day in work.groupby(["ticker", "trade_date"], sort=True):
        outputs.append(
            evaluate_day(
                day,
                learning_rate=learning_rate,
                grad_clip=grad_clip,
                max_parameter_norm=max_parameter_norm,
                device=target_device,
                include_live_vectors=include_live_vectors,
            )
        )
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()


def export_live_adapter_features(
    frame: pd.DataFrame,
    *,
    learning_rate: float,
    grad_clip: float,
    max_parameter_norm: float,
    device: str,
) -> pd.DataFrame:
    evaluated = evaluate_frame(
        frame,
        learning_rate=learning_rate,
        grad_clip=grad_clip,
        max_parameter_norm=max_parameter_norm,
        device=device,
        include_live_vectors=True,
    )
    vector_cols = sorted(
        column
        for column in evaluated.columns
        if column.startswith(("ada_z_", "ada_frozen_dz_", "ada_adapted_dz_"))
    )
    causal_state = [
        "ticker",
        "trade_date",
        "expiration",
        "expiry_mode",
        "timestamp",
        "time",
        "minute",
        "updates_before_prediction",
        "rollbacks_before_prediction",
        "adapter_parameter_norm",
    ]
    output = evaluated[[*causal_state, *vector_cols]].copy()
    forbidden = ("target", "error", "future", "pnl", "return", "outcome")
    leaked = [column for column in output.columns if any(token in column.lower() for token in forbidden)]
    if leaked:
        raise RuntimeError(f"outcome-like columns entered AdaJEPA live feature export: {leaked}")
    return output


def paired_test(control: pd.Series, variant: pd.Series) -> dict[str, Any]:
    left = pd.to_numeric(control, errors="coerce").to_numpy(float)
    right = pd.to_numeric(variant, errors="coerce").to_numpy(float)
    finite = np.isfinite(left) & np.isfinite(right)
    difference = right[finite] - left[finite]
    p_value = float(wilcoxon(right[finite], left[finite], alternative="less").pvalue) if len(difference) and np.any(difference != 0) else float("nan")
    return {
        "pairs": int(len(difference)),
        "adapted_wins": int((difference < 0).sum()),
        "frozen_wins": int((difference > 0).sum()),
        "ties": int((difference == 0).sum()),
        "median_adapted_minus_frozen": float(np.median(difference)) if len(difference) else float("nan"),
        "mean_adapted_minus_frozen": float(np.mean(difference)) if len(difference) else float("nan"),
        "wilcoxon_one_sided_p": p_value,
    }


def summarize(rows: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    cells = (
        rows.groupby(["ticker", "month"], as_index=False)
        .agg(
            rows=("frozen_error", "size"),
            days=("trade_date", "nunique"),
            frozen_rmse=("frozen_error", lambda values: float(np.sqrt(np.mean(np.square(values))))),
            adapted_rmse=("adapted_error", lambda values: float(np.sqrt(np.mean(np.square(values))))),
            persistence_rmse=("persistence_error", lambda values: float(np.sqrt(np.mean(np.square(values))))),
            frozen_mean_error=("frozen_error", "mean"),
            adapted_mean_error=("adapted_error", "mean"),
            mean_parameter_norm=("adapter_parameter_norm", "mean"),
            rollbacks=("rollbacks_before_prediction", "max"),
        )
        .sort_values(["ticker", "month"])
        .reset_index(drop=True)
    )
    daily = (
        rows.groupby(["ticker", "trade_date", "month"], as_index=False)
        .agg(frozen_error=("frozen_error", "mean"), adapted_error=("adapted_error", "mean"))
        .sort_values(["ticker", "trade_date"])
    )
    cell_test = paired_test(cells["frozen_rmse"], cells["adapted_rmse"])
    daily_test = paired_test(daily["frozen_error"], daily["adapted_error"])
    reproducible = bool(
        len(cells) == 15
        and cell_test["adapted_wins"] >= 10
        and cell_test["median_adapted_minus_frozen"] < 0
        and cell_test["wilcoxon_one_sided_p"] < 0.05
        and daily_test["median_adapted_minus_frozen"] < 0
        and daily_test["wilcoxon_one_sided_p"] < 0.05
    )
    summary = {
        "schema_version": 1,
        "comparison": "frozen_predictor_vs_daily_reset_diagonal_adapter",
        "cell_paired_test": cell_test,
        "daily_paired_test": daily_test,
        "total_rows": int(len(rows)),
        "total_days": int(rows[["ticker", "trade_date"]].drop_duplicates().shape[0]),
        "total_rollbacks": int(rows.groupby(["ticker", "trade_date"])["rollbacks_before_prediction"].max().sum()),
        "decision": {
            "representation_improved_reproducibly": reproducible,
            "advance_to_separate_downstream_ablation": reproducible,
            "production_live_ready": False,
        },
    }
    return summary, cells, daily


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate an AdaJEPA-style daily-reset shadow adapter in coherent frozen spaces.")
    parser.add_argument("--spaces-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--max-parameter-norm", type=float, default=0.5)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    spaces_dir = Path(args.spaces_dir)
    manifest = json.loads((spaces_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    outputs = []
    input_rows = []
    for fold in manifest:
        month = str(fold["test_month"])
        path = Path(fold["transitions_path"])
        frame = pd.read_parquet(path)
        frame["trade_date"] = frame["trade_date"].astype(str).str.replace(r"\.0$", "", regex=True)
        test = frame[frame["trade_date"].str[:6].eq(month)].copy()
        evaluated = evaluate_frame(
            test,
            learning_rate=args.learning_rate,
            grad_clip=args.grad_clip,
            max_parameter_norm=args.max_parameter_norm,
            device=args.device,
        )
        outputs.append(evaluated)
        input_rows.append({"test_month": month, "rows": len(test), "transition_sha256": fold["transitions_sha256"]})
        print(f"[ADAJEPA_SHADOW] month={month} rows={len(evaluated)}", flush=True)
    rows = pd.concat(outputs, ignore_index=True)
    summary, cells, daily = summarize(rows)
    summary.update(
        {
            "args": vars(args),
            "input_folds": input_rows,
            "june_2026_sealed": True,
            "target_used_only_after_observation": True,
            "adapter_resets_each_ticker_day": True,
        }
    )
    rows.to_parquet(output_dir / "shadow_row_errors.parquet", index=False)
    cells.to_csv(output_dir / "ticker_month_metrics.csv", index=False)
    daily.to_csv(output_dir / "daily_metrics.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    print(json.dumps(summary["decision"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
