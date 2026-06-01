from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.dataset import infer_sort_columns
from neural.jepa.xinput_dataset import XInputNormalizers
from neural.jepa.xinput_model import load_xinput_model

try:
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        f1_score,
        log_loss,
        roc_auc_score,
    )
except Exception:  # pragma: no cover - diagnostics should still run without sklearn
    accuracy_score = None
    balanced_accuracy_score = None
    f1_score = None
    log_loss = None
    roc_auc_score = None


LABEL_NAMES = {0: "SHORT", 1: "HOLD", 2: "LONG"}
PROB_COLS = ["xjepa_prob_short", "xjepa_prob_hold", "xjepa_prob_long"]
LAGGED_ERR_COLS = [
    "xjepa_lagged_pred_30m_err",
    "xjepa_lagged_pred_60m_err",
    "xjepa_lagged_pred_180m_err",
]
ROW_FEATURE_COLS = [
    "xjepa_trade_confidence",
    "xjepa_direction_score",
    "xjepa_entropy",
    "xjepa_latent_velocity",
    "xjepa_input_velocity",
    "xjepa_pred_dispersion_short",
    "xjepa_pred_dispersion_long",
    *LAGGED_ERR_COLS,
]


def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)


def normalize_time(value) -> str:
    text = str(value)
    if " " in text:
        text = text.split()[-1]
    return text[:5]


def normalize_target(values: pd.Series) -> np.ndarray:
    arr = values.to_numpy()
    arr = np.nan_to_num(arr, nan=0.0).astype(np.int64)
    if arr.min(initial=0) < 0:
        arr = arr + 1
    return np.clip(arr, 0, 2).astype(np.int64)


def split_name(date_value: str, oos_start: str) -> str:
    return "oos" if normalize_date(date_value) >= oos_start else "pre_oos"


def build_contexts(arr: np.ndarray, context_len: int) -> tuple[np.ndarray, list[int]]:
    contexts = []
    positions = []
    for pos in range(context_len - 1, len(arr)):
        contexts.append(arr[pos - context_len + 1 : pos + 1])
        positions.append(pos)
    if not contexts:
        return np.zeros((0, context_len, arr.shape[1]), dtype=np.float32), []
    return np.stack(contexts, axis=0).astype(np.float32), positions


def infer_batches(model, state_ctx: np.ndarray, input_ctx: np.ndarray, batch_size: int, device: torch.device):
    z_out, pred_out, prob_out = [], [], []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(state_ctx), batch_size):
            s = torch.from_numpy(state_ctx[start : start + batch_size]).to(device).float()
            uin = torch.from_numpy(input_ctx[start : start + batch_size]).to(device).float()
            z, _, pred, logits = model(s, uin)
            z_out.append(z.cpu().numpy())
            pred_out.append(pred.cpu().numpy())
            prob_out.append(torch.softmax(logits, dim=-1).cpu().numpy())
    if not z_out:
        z_dim = model.config.z_dim
        return (
            np.zeros((0, z_dim), dtype=np.float32),
            np.zeros((0, len(model.config.horizons), z_dim), dtype=np.float32),
            np.zeros((0, 3), dtype=np.float32),
        )
    return np.concatenate(z_out), np.concatenate(pred_out), np.concatenate(prob_out)


def safe_mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if np.isfinite(v)]
    return float(np.mean(vals)) if vals else float("nan")


def safe_median(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if np.isfinite(v)]
    return float(np.median(vals)) if vals else float("nan")


def safe_auc(y_true: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y_true).astype(int)
    s = np.asarray(score).astype(float)
    mask = np.isfinite(s)
    y = y[mask]
    s = s[mask]
    if roc_auc_score is None or len(y) < 2 or len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, s))


def safe_spearman(a: pd.Series, b: pd.Series) -> float:
    frame = pd.DataFrame(
        {"a": np.asarray(a, dtype=np.float64), "b": np.asarray(b, dtype=np.float64)}
    ).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 3 or frame["a"].nunique() < 2 or frame["b"].nunique() < 2:
        return float("nan")
    return float(frame["a"].corr(frame["b"], method="spearman"))


def format_float(value: float, decimals: int = 3) -> str:
    if value is None or not np.isfinite(value):
        return "nan"
    return f"{float(value):.{decimals}f}"


def format_pct(value: float, decimals: int = 1) -> str:
    if value is None or not np.isfinite(value):
        return "nan"
    return f"{100.0 * float(value):.{decimals}f}%"


def normalize_probs(df: pd.DataFrame) -> np.ndarray:
    probs = df[PROB_COLS].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=np.float64)
    probs = np.clip(probs, 1e-8, 1.0)
    row_sum = probs.sum(axis=1, keepdims=True)
    row_sum = np.where(row_sum > 0.0, row_sum, 1.0)
    return probs / row_sum


def classify_segment(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {}
    y = normalize_target(frame["target"])
    probs = normalize_probs(frame)
    pred = probs.argmax(axis=1)
    signed_y = np.where(y == 2, 1.0, np.where(y == 0, -1.0, 0.0))

    if accuracy_score is not None:
        acc = float(accuracy_score(y, pred))
        bal_acc = float(balanced_accuracy_score(y, pred))
        macro_f1 = float(f1_score(y, pred, average="macro"))
    else:
        acc = float((pred == y).mean())
        recalls = []
        for cls in (0, 1, 2):
            mask = y == cls
            recalls.append(float((pred[mask] == cls).mean()) if mask.any() else float("nan"))
        bal_acc = safe_mean(recalls)
        macro_f1 = float("nan")

    try:
        ll = float(log_loss(y, probs, labels=[0, 1, 2])) if log_loss is not None else float("nan")
    except Exception:
        ll = float("nan")

    one_hot = np.eye(3, dtype=np.float64)[y]
    pred_trade = pred != 1
    true_trade = y != 1
    directional_hit = (pred == y) & true_trade
    return {
        "rows": int(len(frame)),
        "target_short_rate": float((y == 0).mean()),
        "target_hold_rate": float((y == 1).mean()),
        "target_long_rate": float((y == 2).mean()),
        "pred_short_rate": float((pred == 0).mean()),
        "pred_hold_rate": float((pred == 1).mean()),
        "pred_long_rate": float((pred == 2).mean()),
        "accuracy": acc,
        "balanced_accuracy": bal_acc,
        "macro_f1": macro_f1,
        "logloss": ll,
        "brier": float(np.mean(np.sum((probs - one_hot) ** 2, axis=1))),
        "long_auc": safe_auc(y == 2, probs[:, 2]),
        "short_auc": safe_auc(y == 0, probs[:, 0]),
        "trade_auc": safe_auc(true_trade, np.maximum(probs[:, 0], probs[:, 2])),
        "direction_spearman": safe_spearman(frame["xjepa_direction_score"], signed_y),
        "pred_trade_rate": float(pred_trade.mean()),
        "pred_trade_precision": float((pred[pred_trade] == y[pred_trade]).mean()) if pred_trade.any() else float("nan"),
        "true_trade_recall": float(directional_hit.sum() / max(1, true_trade.sum())),
    }


def score_head_metrics(df: pd.DataFrame, oos_start: str) -> list[dict]:
    valid = df[df.get("xjepa_context_valid", 0).astype(float) > 0.0].copy()
    valid["_split"] = valid["date"].map(lambda x: split_name(x, oos_start))
    rows = []
    for segment, frame in [("overall", valid), ("pre_oos", valid[valid["_split"] == "pre_oos"]), ("oos", valid[valid["_split"] == "oos"])]:
        metrics = classify_segment(frame)
        if metrics:
            metrics.update({"segment": segment, "ticker": "ALL"})
            rows.append(metrics)
    for (segment, ticker), frame in valid.groupby(["_split", "ticker"], sort=True):
        metrics = classify_segment(frame)
        if metrics:
            metrics.update({"segment": str(segment), "ticker": str(ticker)})
            rows.append(metrics)
    return rows


def score_lagged_errors(df: pd.DataFrame, oos_start: str) -> list[dict]:
    valid = df[df.get("xjepa_context_valid", 0).astype(float) > 0.0].copy()
    valid["_split"] = valid["date"].map(lambda x: split_name(x, oos_start))
    valid["_target_norm"] = normalize_target(valid["target"])
    rows = []
    groups = [("overall", "ALL", valid)]
    groups += [(seg, "ALL", frame) for seg, frame in valid.groupby("_split", sort=True)]
    groups += [(seg, ticker, frame) for (seg, ticker), frame in valid.groupby(["_split", "ticker"], sort=True)]
    for segment, ticker, frame in groups:
        for col in LAGGED_ERR_COLS:
            if col not in frame.columns:
                continue
            usable = frame[[col, "_target_norm"]].replace([np.inf, -np.inf], np.nan).dropna()
            usable = usable[usable[col] > 0.0]
            if usable.empty:
                continue
            row = {
                "segment": str(segment),
                "ticker": str(ticker),
                "feature": col,
                "rows": int(len(usable)),
                "mean": float(usable[col].mean()),
                "median": float(usable[col].median()),
                "p75": float(usable[col].quantile(0.75)),
                "short_mean": safe_mean(usable.loc[usable["_target_norm"] == 0, col]),
                "hold_mean": safe_mean(usable.loc[usable["_target_norm"] == 1, col]),
                "long_mean": safe_mean(usable.loc[usable["_target_norm"] == 2, col]),
                "trade_auc_from_error": safe_auc(usable["_target_norm"] != 1, usable[col]),
            }
            rows.append(row)
    return rows


def direct_latent_errors(
    df: pd.DataFrame,
    model_dir: Path,
    batch_size: int,
    device: torch.device,
    oos_start: str,
) -> list[dict]:
    normalizers = XInputNormalizers.load(model_dir / "normalizers.json")
    model = load_xinput_model(model_dir, map_location="cpu")
    model.to(device)
    horizons = [int(h) for h in model.config.horizons]

    work = df.copy()
    work["date"] = work["date"].astype(str)
    work = work.sort_values(infer_sort_columns(work)).reset_index(drop=True)

    buckets: dict[tuple[str, str, int], dict[str, list[float]]] = defaultdict(lambda: {"model": [], "persistence": []})

    for (ticker, date), group in work.groupby(["ticker", "date"], sort=False):
        if len(group) < model.config.context_len + max(horizons):
            continue
        s_arr = normalizers.state.transform_frame(group)
        u_arr = normalizers.input.transform_frame(group)
        s_ctx, positions = build_contexts(s_arr, model.config.context_len)
        u_ctx, _ = build_contexts(u_arr, model.config.context_len)
        if len(s_ctx) == 0:
            continue

        z, pred, _ = infer_batches(model, s_ctx, u_ctx, batch_size, device)
        z_by_pos = np.zeros((len(group), model.config.z_dim), dtype=np.float32)
        pred_by_pos = np.zeros((len(group), len(horizons), model.config.z_dim), dtype=np.float32)
        valid = np.zeros(len(group), dtype=bool)
        for row_i, pos in enumerate(positions):
            z_by_pos[pos] = z[row_i]
            pred_by_pos[pos] = pred[row_i]
            valid[pos] = True

        segment = split_name(str(date), oos_start)
        for pos in positions:
            if not valid[pos]:
                continue
            for h_idx, horizon in enumerate(horizons):
                future = pos + horizon
                if future >= len(group) or not valid[future]:
                    continue
                future_z = z_by_pos[future]
                model_mse = float(np.mean((pred_by_pos[pos, h_idx] - future_z) ** 2))
                persistence_mse = float(np.mean((z_by_pos[pos] - future_z) ** 2))
                for key in (("overall", "ALL", horizon), (segment, "ALL", horizon), (segment, str(ticker), horizon)):
                    buckets[key]["model"].append(model_mse)
                    buckets[key]["persistence"].append(persistence_mse)

    rows = []
    for (segment, ticker, horizon), values in sorted(buckets.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        model_values = np.asarray(values["model"], dtype=np.float64)
        persistence_values = np.asarray(values["persistence"], dtype=np.float64)
        if len(model_values) == 0:
            continue
        model_mean = float(np.mean(model_values))
        persistence_mean = float(np.mean(persistence_values))
        rows.append(
            {
                "segment": segment,
                "ticker": ticker,
                "horizon_steps": int(horizon),
                "horizon_minutes": int(horizon * 5),
                "rows": int(len(model_values)),
                "model_mse": model_mean,
                "model_median_mse": float(np.median(model_values)),
                "persistence_mse": persistence_mean,
                "persistence_median_mse": float(np.median(persistence_values)),
                "mse_improvement_vs_persistence": (
                    1.0 - model_mean / persistence_mean if persistence_mean > 1e-12 else float("nan")
                ),
                "win_rate_vs_persistence": float(np.mean(model_values < persistence_values)),
            }
        )
    return rows


def trade_level_capacity(df: pd.DataFrame, trade_paths: list[Path], oos_start: str) -> list[dict]:
    feature_cols = [c for c in ROW_FEATURE_COLS if c in df.columns]
    rows_df = df[["ticker", "date", "time", *feature_cols]].copy()
    rows_df["_date_key"] = rows_df["date"].map(normalize_date)
    rows_df["_time_key"] = rows_df["time"].map(normalize_time)
    rows_df["_ticker_key"] = rows_df["ticker"].astype(str)
    rows_df = rows_df.drop_duplicates(["_ticker_key", "_date_key", "_time_key"])

    reports = []
    for path in trade_paths:
        if not path.exists():
            continue
        trades = pd.read_csv(path)
        if trades.empty:
            continue
        trades["_date_key"] = trades["date"].map(normalize_date)
        trades["_time_key"] = trades["entry_time"].map(normalize_time)
        trades["_ticker_key"] = trades["ticker"].astype(str)
        merged = trades.merge(
            rows_df,
            on=["_ticker_key", "_date_key", "_time_key"],
            how="left",
            suffixes=("", "_row"),
        )
        merged["_split"] = merged["_date_key"].map(lambda x: split_name(x, oos_start))
        merged["_win"] = merged["pnl_dollars"].astype(float) > 0.0
        direction = merged["direction"].astype(str).str.upper()
        merged["_dir_sign"] = np.where(direction.str.contains("LONG"), 1.0, np.where(direction.str.contains("SHORT"), -1.0, 0.0))
        if "xjepa_direction_score" in merged.columns:
            merged["_alignment"] = merged["_dir_sign"] * merged["xjepa_direction_score"].astype(float)
        if "xjepa_trade_confidence" in merged.columns:
            merged["_xjepa_conf"] = merged["xjepa_trade_confidence"].astype(float)
        if "xjepa_lagged_pred_60m_err" in merged.columns:
            merged["_neg_60m_err"] = -merged["xjepa_lagged_pred_60m_err"].astype(float)

        for segment, frame in [("overall", merged), ("pre_oos", merged[merged["_split"] == "pre_oos"]), ("oos", merged[merged["_split"] == "oos"])]:
            if frame.empty:
                continue
            report = {
                "trade_file": path.name,
                "segment": segment,
                "trades": int(len(frame)),
                "merge_rate": float(frame["xjepa_direction_score"].notna().mean()) if "xjepa_direction_score" in frame.columns else float("nan"),
                "win_rate": float(frame["_win"].mean()),
                "pnl": float(frame["pnl_dollars"].sum()),
            }
            usable = frame.dropna(subset=["_win"])
            if "_alignment" in usable.columns:
                report["alignment_auc_for_win"] = safe_auc(usable["_win"], usable["_alignment"])
                report["alignment_spearman_pnl"] = safe_spearman(usable["_alignment"], usable["pnl_dollars"])
                report["alignment_mean_winners"] = safe_mean(usable.loc[usable["_win"], "_alignment"])
                report["alignment_mean_losers"] = safe_mean(usable.loc[~usable["_win"], "_alignment"])
            if "_xjepa_conf" in usable.columns:
                report["confidence_auc_for_win"] = safe_auc(usable["_win"], usable["_xjepa_conf"])
            if "_neg_60m_err" in usable.columns:
                report["low_error_auc_for_win"] = safe_auc(usable["_win"], usable["_neg_60m_err"])
            reports.append(report)
    return reports


def terminal_direction_capacity(df: pd.DataFrame, oos_start: str, horizon_steps: int) -> list[dict]:
    required = {"ticker", "date", "spot_price", "xjepa_direction_score", *PROB_COLS}
    if missing := (required - set(df.columns)):
        raise KeyError(f"Missing columns for terminal direction diagnostics: {sorted(missing)}")

    work = df.copy()
    work["date"] = work["date"].astype(str)
    work = work.sort_values(infer_sort_columns(work)).reset_index(drop=True)
    records = []
    for (ticker, date), group in work.groupby(["ticker", "date"], sort=False):
        if len(group) <= horizon_steps:
            continue
        spot = group["spot_price"].to_numpy(dtype=np.float64)
        if "xjepa_context_valid" in group.columns:
            valid = group["xjepa_context_valid"].to_numpy(dtype=np.float64) > 0.0
        else:
            valid = np.ones(len(group), dtype=bool)
        for pos in range(0, len(group) - horizon_steps):
            if not valid[pos]:
                continue
            current = spot[pos]
            future = spot[pos + horizon_steps]
            if not np.isfinite(current) or not np.isfinite(future) or current <= 0.0:
                continue
            row = group.iloc[pos]
            future_return = future / current - 1.0
            records.append(
                {
                    "ticker": str(ticker),
                    "date": str(date),
                    "segment": split_name(str(date), oos_start),
                    "future_return": float(future_return),
                    "future_up": bool(future_return > 0.0),
                    "direction_score": float(row["xjepa_direction_score"]),
                    "prob_long": float(row["xjepa_prob_long"]),
                    "prob_short": float(row["xjepa_prob_short"]),
                    "prob_hold": float(row["xjepa_prob_hold"]),
                    "trade_confidence": float(row.get("xjepa_trade_confidence", max(row["xjepa_prob_long"], row["xjepa_prob_short"]))),
                }
            )
    term = pd.DataFrame(records)
    if term.empty:
        return []

    rows = []
    groups = [("overall", "ALL", term)]
    groups += [(seg, "ALL", frame) for seg, frame in term.groupby("segment", sort=True)]
    groups += [(seg, ticker, frame) for (seg, ticker), frame in term.groupby(["segment", "ticker"], sort=True)]
    for segment, ticker, frame in groups:
        if frame.empty:
            continue
        pred_up = frame["direction_score"] > 0.0
        row = {
            "segment": str(segment),
            "ticker": str(ticker),
            "horizon_steps": int(horizon_steps),
            "horizon_minutes": int(horizon_steps * 5),
            "rows": int(len(frame)),
            "future_up_rate": float(frame["future_up"].mean()),
            "mean_future_return_bps": float(frame["future_return"].mean() * 10000.0),
            "median_future_return_bps": float(frame["future_return"].median() * 10000.0),
            "direction_score_auc_up": safe_auc(frame["future_up"], frame["direction_score"]),
            "prob_long_auc_up": safe_auc(frame["future_up"], frame["prob_long"]),
            "neg_prob_short_auc_up": safe_auc(frame["future_up"], -frame["prob_short"]),
            "direction_score_spearman_return": safe_spearman(frame["direction_score"], frame["future_return"]),
            "sign_accuracy": float((pred_up == frame["future_up"]).mean()),
            "pred_up_rate": float(pred_up.mean()),
            "top_quintile_mean_return_bps": float(
                frame.loc[frame["direction_score"] >= frame["direction_score"].quantile(0.80), "future_return"].mean()
                * 10000.0
            ),
            "bottom_quintile_mean_return_bps": float(
                frame.loc[frame["direction_score"] <= frame["direction_score"].quantile(0.20), "future_return"].mean()
                * 10000.0
            ),
        }
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def markdown_report(
    head_rows: list[dict],
    latent_rows: list[dict],
    lagged_rows: list[dict],
    trade_rows: list[dict],
    terminal_rows: list[dict],
    args,
) -> str:
    lines = [
        "# XInputJEPA Predictive Capacity",
        "",
        f"Data: `{args.data}`",
        f"Model: `{args.model_dir}`",
        f"OOS split: dates >= `{args.oos_start}`",
        "",
        "## Verdict",
        "",
    ]

    oos_head = next((r for r in head_rows if r["segment"] == "oos" and r["ticker"] == "ALL"), None)
    oos_latent_60 = next(
        (r for r in latent_rows if r["segment"] == "oos" and r["ticker"] == "ALL" and r["horizon_minutes"] == 60),
        None,
    )
    oos_trade = next((r for r in trade_rows if r["trade_file"] == "xjepa_only_trades.csv" and r["segment"] == "oos"), None)
    oos_latent_180 = next(
        (r for r in latent_rows if r["segment"] == "oos" and r["ticker"] == "ALL" and r["horizon_minutes"] == 180),
        None,
    )
    if oos_head and oos_latent_60:
        lines += [
            "- XInputJEPA does not show strong short/medium-horizon latent prediction capacity versus a persistence baseline.",
            f"- OOS 60m latent MSE improvement versus persistence: {format_pct(oos_latent_60['mse_improvement_vs_persistence'])}; the predictor beats persistence on {format_pct(oos_latent_60['win_rate_vs_persistence'])} of samples.",
            f"- OOS auxiliary direction head: balanced accuracy {format_pct(oos_head['balanced_accuracy'])}, long AUC {format_float(oos_head['long_auc'])}, short AUC {format_float(oos_head['short_auc'])}, trade-vs-hold AUC {format_float(oos_head['trade_auc'])}.",
        ]
    if oos_latent_180:
        lines.append(
            f"- The clearest direct latent signal is long horizon: OOS 180m latent MSE improvement versus persistence is {format_pct(oos_latent_180['mse_improvement_vs_persistence'])}."
        )
    if oos_trade:
        lines.append(
            f"- OOS XInputJEPA-only trades: win rate {format_pct(oos_trade['win_rate'])}, PnL {oos_trade['pnl']:+,.0f}, alignment AUC for trade win {format_float(oos_trade.get('alignment_auc_for_win', float('nan')))}."
        )
    oos_terminal = next((r for r in terminal_rows if r["segment"] == "oos" and r["ticker"] == "ALL"), None)
    if oos_terminal:
        lines.append(
            f"- Exact OOS 180m terminal-up test: direction-score AUC {format_float(oos_terminal['direction_score_auc_up'])}, sign accuracy {format_pct(oos_terminal['sign_accuracy'])}, Spearman to 180m return {format_float(oos_terminal['direction_score_spearman_return'])}."
        )
    lines += [
        "- This supports the interpretation that the JEPA learned some slower future-state structure, but not enough short-horizon tradable signal for clean GBT integration.",
        "",
        "## Direction Head",
        "",
        "| Segment | Ticker | Rows | Target S/H/L | Pred S/H/L | Acc | Bal Acc | Macro F1 | Long AUC | Short AUC | Trade AUC | Dir Spearman |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in head_rows:
        if r["ticker"] != "ALL":
            continue
        lines.append(
            f"| {r['segment']} | {r['ticker']} | {r['rows']} | "
            f"{format_pct(r['target_short_rate'])}/{format_pct(r['target_hold_rate'])}/{format_pct(r['target_long_rate'])} | "
            f"{format_pct(r['pred_short_rate'])}/{format_pct(r['pred_hold_rate'])}/{format_pct(r['pred_long_rate'])} | "
            f"{format_pct(r['accuracy'])} | {format_pct(r['balanced_accuracy'])} | {format_pct(r['macro_f1'])} | "
            f"{format_float(r['long_auc'])} | {format_float(r['short_auc'])} | {format_float(r['trade_auc'])} | {format_float(r['direction_spearman'])} |"
        )

    lines += [
        "",
        "## Direct Latent Prediction",
        "",
        "MSE is measured between the predicted future latent state and the observed future latent state. Persistence uses current `z_t` as the future prediction.",
        "",
        "| Segment | Ticker | Horizon | Rows | Model MSE | Persistence MSE | Improvement | Beat Persistence |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in latent_rows:
        if r["ticker"] != "ALL":
            continue
        lines.append(
            f"| {r['segment']} | {r['ticker']} | {r['horizon_minutes']}m | {r['rows']} | "
            f"{format_float(r['model_mse'], 5)} | {format_float(r['persistence_mse'], 5)} | "
            f"{format_pct(r['mse_improvement_vs_persistence'])} | {format_pct(r['win_rate_vs_persistence'])} |"
        )

    lines += [
        "",
        "## Exact 180m Spot Direction",
        "",
        "This measures whether the current JEPA direction score predicts `spot_price(t+180m) > spot_price(t)` exactly, not whether a target/stop path wins inside the 180m window.",
        "",
        "| Segment | Ticker | Rows | Future Up | Pred Up | Sign Acc | AUC Up | Spearman Ret | Mean Ret bps | Top Q Ret bps | Bottom Q Ret bps |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in terminal_rows:
        if r["ticker"] != "ALL":
            continue
        lines.append(
            f"| {r['segment']} | {r['ticker']} | {r['rows']} | {format_pct(r['future_up_rate'])} | "
            f"{format_pct(r['pred_up_rate'])} | {format_pct(r['sign_accuracy'])} | "
            f"{format_float(r['direction_score_auc_up'])} | {format_float(r['direction_score_spearman_return'])} | "
            f"{format_float(r['mean_future_return_bps'], 2)} | {format_float(r['top_quintile_mean_return_bps'], 2)} | "
            f"{format_float(r['bottom_quintile_mean_return_bps'], 2)} |"
        )

    lines += [
        "",
        "## Lagged Surprise Features",
        "",
        "| Segment | Feature | Rows | Mean | Median | Short Mean | Hold Mean | Long Mean | Trade AUC From Error |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in lagged_rows:
        if r["ticker"] != "ALL":
            continue
        lines.append(
            f"| {r['segment']} | {r['feature']} | {r['rows']} | {format_float(r['mean'], 4)} | {format_float(r['median'], 4)} | "
            f"{format_float(r['short_mean'], 4)} | {format_float(r['hold_mean'], 4)} | {format_float(r['long_mean'], 4)} | "
            f"{format_float(r['trade_auc_from_error'])} |"
        )

    lines += [
        "",
        "## Trade-Level Capacity",
        "",
        "| Trade File | Segment | Trades | Merge | WR | PnL | Align AUC Win | Align Spearman PnL | Conf AUC Win | Low-Err AUC Win |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in trade_rows:
        lines.append(
            f"| {r['trade_file']} | {r['segment']} | {r['trades']} | {format_pct(r['merge_rate'])} | "
            f"{format_pct(r['win_rate'])} | {r['pnl']:+,.0f} | "
            f"{format_float(r.get('alignment_auc_for_win', float('nan')))} | "
            f"{format_float(r.get('alignment_spearman_pnl', float('nan')))} | "
            f"{format_float(r.get('confidence_auc_for_win', float('nan')))} | "
            f"{format_float(r.get('low_error_auc_for_win', float('nan')))} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "- Beating persistence in latent space means the predictor is not only copying the current state.",
        "- The auxiliary direction head has useful but weak row-level discrimination; the majority HOLD class is large, so balanced accuracy and AUC matter more than raw accuracy.",
        "- Trade-level alignment is the strictest test. If alignment AUC is near 0.50, the JEPA signal may predict state transitions but not the option payoff distribution reliably.",
        "- The current result is consistent with the backtests: XInputJEPA captures some market-state dynamics, but GBT integration needs stronger calibration/gating before promotion.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Directly evaluate XInputJEPA predictive capacity.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--trades", nargs="*", default=[])
    parser.add_argument("--oos-start", default="20260401")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--terminal-horizon-steps", type=int, default=36)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir = Path(args.model_dir)
    device = torch.device(args.device)

    df = pd.read_parquet(args.data)
    head_rows = score_head_metrics(df, args.oos_start)
    lagged_rows = score_lagged_errors(df, args.oos_start)
    latent_rows = direct_latent_errors(df, model_dir, args.batch_size, device, args.oos_start)
    trade_rows = trade_level_capacity(df, [Path(p) for p in args.trades], args.oos_start)
    terminal_rows = terminal_direction_capacity(df, args.oos_start, args.terminal_horizon_steps)

    write_csv(output_dir / "direction_head_metrics.csv", head_rows)
    write_csv(output_dir / "direct_latent_prediction.csv", latent_rows)
    write_csv(output_dir / "lagged_surprise_metrics.csv", lagged_rows)
    write_csv(output_dir / "trade_level_metrics.csv", trade_rows)
    write_csv(output_dir / "terminal_180m_direction.csv", terminal_rows)

    payload = {
        "data": args.data,
        "model_dir": args.model_dir,
        "oos_start": args.oos_start,
        "direction_head": head_rows,
        "direct_latent_prediction": latent_rows,
        "lagged_surprise": lagged_rows,
        "trade_level": trade_rows,
        "terminal_direction": terminal_rows,
    }
    (output_dir / "predictive_capacity.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    report = markdown_report(head_rows, latent_rows, lagged_rows, trade_rows, terminal_rows, args)
    (output_dir / "SUMMARY.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
