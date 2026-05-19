import json
import math
import re
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = ROOT / "backtest_results"
ANALYSIS_TEX = ROOT / "visualizer" / "analysis" / "All_backtest_analysis_report.tex"
GBT_MODEL = ROOT / "neural" / "models" / "codex_exp" / "gbt_18m_econ_pf150_minsel10_avail.joblib"
GBT_HISTORY = ROOT / "neural" / "models" / "codex_exp" / "gbt_18m_econ_pf150_minsel10_avail_history.joblib"
GBT_REGISTRY = ROOT / "neural" / "models" / "codex_exp" / "window_registry.json"
RL_HISTORY = ROOT / "rl_models" / "rl_training_history.json"
RL_BEST = ROOT / "rl_models" / "best_rl_agent.pt"
EPISODE_INDEX = ROOT / "rl_data" / "episode_index.parquet"


def _latest_report_pair() -> tuple[Path, Path]:
    if ANALYSIS_TEX.exists():
        text = ANALYSIS_TEX.read_text(encoding="utf-8", errors="ignore")
        gbt = re.search(r"GBT:\s*(gbt_only_\d+_\d+\.csv)", text)
        rl = re.search(r"RL:\s*(gbt_rl_\d+_\d+\.csv)", text)
        if gbt and rl:
            return BACKTEST_DIR / gbt.group(1), BACKTEST_DIR / rl.group(1)

    gbt_files = sorted(BACKTEST_DIR.glob("gbt_only_*.csv"), key=lambda p: p.stat().st_mtime)
    rl_files = sorted(BACKTEST_DIR.glob("gbt_rl_*.csv"), key=lambda p: p.stat().st_mtime)
    if not gbt_files or not rl_files:
        raise FileNotFoundError("No gbt_only/gbt_rl CSV pair found.")
    return gbt_files[-1], rl_files[-1]


def _profit_factor(values: pd.Series) -> float:
    values = values.astype(float)
    gross_profit = values[values > 0].sum()
    gross_loss = -values[values < 0].sum()
    if gross_loss > 0:
        return float(gross_profit / gross_loss)
    return math.inf if gross_profit > 0 else 0.0


def _max_drawdown(values: pd.Series) -> float:
    cum = values.astype(float).cumsum()
    if cum.empty:
        return 0.0
    return float((cum - cum.cummax()).min())


def _metrics(df: pd.DataFrame) -> dict:
    pnl = df["pnl_dollars"].astype(float)
    return {
        "trades": int(len(df)),
        "pnl": float(pnl.sum()),
        "win_rate_pct": float((pnl > 0).mean() * 100.0) if len(df) else 0.0,
        "profit_factor": _profit_factor(pnl),
        "avg_pnl": float(pnl.mean()) if len(df) else 0.0,
        "max_drawdown": _max_drawdown(pnl),
    }


def _group_metrics(df: pd.DataFrame, group_cols: list[str]) -> list[dict]:
    rows = []
    for keys, group in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {col: key for col, key in zip(group_cols, keys)}
        row.update(_metrics(group))
        if "direction" not in group_cols and "direction" in group.columns:
            n = max(len(group), 1)
            row["long_pct"] = float((group["direction"] == "LONG").sum() / n * 100.0)
            row["short_pct"] = float((group["direction"] == "SHORT").sum() / n * 100.0)
        rows.append(row)
    return rows


def _recent_backtest_summary(path: Path, label: str) -> dict:
    df = pd.read_csv(path)
    df["date"] = df["date"].astype(str)
    df["dt"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df["month"] = df["dt"].dt.strftime("%Y-%m")
    recent = df[df["month"].isin(["2026-03", "2026-04", "2026-05"])].copy()

    collapse_rows = []
    for (month, ticker), group in recent.groupby(["month", "ticker"]):
        n = len(group)
        if n < 3:
            continue
        long_pct = float((group["direction"] == "LONG").mean() * 100.0)
        short_pct = float((group["direction"] == "SHORT").mean() * 100.0)
        dominant = "LONG" if long_pct >= short_pct else "SHORT"
        dominant_pct = max(long_pct, short_pct)
        if dominant_pct >= 90.0:
            collapse_rows.append(
                {
                    "month": month,
                    "ticker": ticker,
                    "dominant_direction": dominant,
                    "dominant_pct": dominant_pct,
                    "trades": int(n),
                    "pnl": float(group["pnl_dollars"].sum()),
                    "profit_factor": _profit_factor(group["pnl_dollars"]),
                }
            )

    out = {
        "label": label,
        "file": str(path.relative_to(ROOT)),
        "date_min": str(df["date"].min()),
        "date_max": str(df["date"].max()),
        "overall": _metrics(df),
        "recent_total": _metrics(recent),
        "recent_by_month": _group_metrics(recent, ["month"]),
        "recent_by_month_ticker": _group_metrics(recent, ["month", "ticker"]),
        "recent_by_month_direction": _group_metrics(recent, ["month", "direction"]),
        "recent_by_ticker_direction": _group_metrics(recent, ["ticker", "direction"]),
        "direction_collapse_flags": collapse_rows,
    }
    if "strike_bucket" in recent.columns:
        out["recent_by_strike_bucket"] = _group_metrics(recent, ["month", "strike_bucket"])
        out["strike_distribution_pct"] = (
            recent["strike_bucket"].value_counts(normalize=True).mul(100.0).round(4).to_dict()
        )
        out["recent_by_exit_reason"] = _group_metrics(recent, ["month", "exit_reason"])
    return out


def _model_metadata() -> dict:
    rows = []
    if GBT_HISTORY.exists():
        for idx, item in enumerate(joblib.load(GBT_HISTORY)):
            metadata = dict(item.get("metadata", {}))
            metadata["model_idx"] = idx
            rows.append(metadata)

    grouped = []
    if rows:
        df = pd.DataFrame(rows)
        for window, group in df.groupby("window_idx"):
            grouped.append(
                {
                    "window_idx": int(window),
                    "n_models": int(len(group)),
                    "avg_pf": float(group["avg_pf"].iloc[0]),
                    "cutoff_date": int(group["cutoff_date"].min()),
                    "validation_start_date": int(group["validation_start_date"].min()),
                    "validation_end_date": int(group["validation_end_date"].max()),
                    "available_date": int(group["available_date"].max()),
                }
            )
        grouped = sorted(grouped, key=lambda r: r["window_idx"])

    registry = json.loads(GBT_REGISTRY.read_text()) if GBT_REGISTRY.exists() else []

    month_first_dates = {
        "2026-03": 20260303,
        "2026-04": 20260406,
        "2026-05": 20260504,
    }
    month_last_dates = {
        "2026-03": 20260331,
        "2026-04": 20260429,
        "2026-05": 20260515,
    }
    availability = {}
    for month in month_first_dates:
        first = month_first_dates[month]
        last = month_last_dates[month]
        availability[month] = {
            "eligible_on_first_trade_date": [
                r["window_idx"] for r in grouped if r["available_date"] < first
            ],
            "eligible_on_last_trade_date": [
                r["window_idx"] for r in grouped if r["available_date"] < last
            ],
        }

    return {
        "production_model": str(GBT_MODEL.relative_to(ROOT)),
        "history_model": str(GBT_HISTORY.relative_to(ROOT)),
        "n_history_models": int(len(rows)),
        "history_windows": grouped,
        "window_registry": registry,
        "month_model_availability": availability,
    }


def _rl_training_summary() -> dict:
    hist = json.loads(RL_HISTORY.read_text()) if RL_HISTORY.exists() else {}
    train = pd.DataFrame({k: v for k, v in hist.items() if k != "eval" and isinstance(v, list)})
    eval_src = hist.get("eval", {})
    max_len = max((len(v) for v in eval_src.values()), default=0)
    eval_df = pd.DataFrame(
        {
            k: (v if len(v) == max_len else [None] * max_len)
            for k, v in eval_src.items()
        }
    )

    best_step = None
    if RL_BEST.exists():
        checkpoint = torch.load(RL_BEST, map_location="cpu", weights_only=False)
        best_step = checkpoint.get("config", {}).get("update_step")

    eval_records = eval_df.drop(columns=["stochastic_train_pf"], errors="ignore").to_dict("records")
    best_eval = {}
    if not eval_df.empty:
        for col in ["eval_pf", "eval_wr", "eval_pnl", "train_pf", "train_wr", "train_pnl"]:
            idx = pd.to_numeric(eval_df[col], errors="coerce").idxmax()
            best_eval[col] = {
                "step": int(eval_df.loc[idx, "step"]),
                "value": float(eval_df.loc[idx, col]),
            }
        latest = eval_df.iloc[-1]
        latest_eval = {
            "step": int(latest["step"]),
            "eval_pf": float(latest["eval_pf"]),
            "train_pf": float(latest["train_pf"]),
            "pf_gap": float(latest["train_pf"] - latest["eval_pf"]),
            "eval_pnl": float(latest["eval_pnl"]),
            "train_pnl": float(latest["train_pnl"]),
            "pnl_gap": float(latest["train_pnl"] - latest["eval_pnl"]),
        }
    else:
        latest_eval = {}

    return {
        "best_rl_agent_step": best_step,
        "train_updates": int(len(train)),
        "train_tail": train.tail(5).to_dict("records"),
        "eval_records": eval_records,
        "best_eval": best_eval,
        "latest_eval_gap": latest_eval,
    }


def _episode_summary() -> dict:
    if not EPISODE_INDEX.exists():
        return {}
    ep = pd.read_parquet(EPISODE_INDEX, columns=["date", "ticker", "mlp_direction", "mlp_confidence"])
    ep["date"] = ep["date"].astype(str)
    ep["dt"] = pd.to_datetime(ep["date"], format="%Y%m%d")
    ep["month"] = ep["dt"].dt.strftime("%Y-%m")
    all_dates = sorted(ep["date"].unique())
    split_idx = int(len(all_dates) * 0.8)
    train_dates = all_dates[:split_idx]
    eval_dates = all_dates[split_idx:]
    recent = ep[ep["month"].isin(["2026-03", "2026-04", "2026-05"])].copy()

    return {
        "rows": int(len(ep)),
        "date_min": ep["date"].min(),
        "date_max": ep["date"].max(),
        "n_dates": int(ep["date"].nunique()),
        "direction_counts": ep["mlp_direction"].value_counts().to_dict(),
        "ticker_counts": ep["ticker"].value_counts().to_dict(),
        "chronological_split": {
            "train_days": len(train_dates),
            "train_start": train_dates[0] if train_dates else None,
            "train_end": train_dates[-1] if train_dates else None,
            "eval_days": len(eval_dates),
            "eval_start": eval_dates[0] if eval_dates else None,
            "eval_end": eval_dates[-1] if eval_dates else None,
        },
        "recent_direction_by_month_ticker": (
            recent.groupby(["month", "ticker", "mlp_direction"]).size().rename("n").reset_index().to_dict("records")
        ),
        "recent_confidence_by_month_ticker": (
            recent.groupby(["month", "ticker"])
            .agg(n=("date", "size"), mean_conf=("mlp_confidence", "mean"), min_conf=("mlp_confidence", "min"), max_conf=("mlp_confidence", "max"))
            .reset_index()
            .to_dict("records")
        ),
    }


def main() -> int:
    gbt_path, rl_path = _latest_report_pair()
    report = {
        "report_tex": str(ANALYSIS_TEX.relative_to(ROOT)),
        "gbt_only": _recent_backtest_summary(gbt_path, "GBT-only"),
        "gbt_rl": _recent_backtest_summary(rl_path, "GBT+RL"),
        "gbt_model": _model_metadata(),
        "rl_training": _rl_training_summary(),
        "episodes": _episode_summary(),
    }
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
