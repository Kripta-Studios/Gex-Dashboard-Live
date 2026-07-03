from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.dataset import infer_sort_columns
from neural.jepa.sigreg import latent_diagnostics


PROB_COLUMNS = ["xjepa_prob_short", "xjepa_prob_hold", "xjepa_prob_long"]


def parse_run(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("runs must be NAME=PATH")
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("run name cannot be empty")
    path = Path(raw_path.strip())
    if path.is_dir():
        path = path / "oof_xinput_features.parquet"
    if not path.exists():
        raise argparse.ArgumentTypeError(f"run path does not exist: {path}")
    return name, path


def as_month(date: pd.Series) -> pd.Series:
    return date.astype(str).str.replace("-", "", regex=False).str[:6]


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if not np.isfinite(float(value)):
            return None
        return float(value)
    return value


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, conf: np.ndarray | None = None) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=np.int64)
    y_pred = np.asarray(y_pred, dtype=np.int64)
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true = y_true[valid]
    y_pred = y_pred[valid]
    if conf is not None:
        conf = np.asarray(conf, dtype=np.float64)[valid]
    if len(y_true) == 0:
        return {
            "rows": 0,
            "acc": None,
            "bal_acc": None,
            "macro_f1": None,
            "trade_rate": None,
            "trade_precision": None,
            "avg_trade_conf": None,
        }

    recalls: list[float] = []
    f1s: list[float] = []
    for cls in (0, 1, 2):
        tp = float(((y_true == cls) & (y_pred == cls)).sum())
        fp = float(((y_true != cls) & (y_pred == cls)).sum())
        fn = float(((y_true == cls) & (y_pred != cls)).sum())
        support = float((y_true == cls).sum())
        recalls.append(tp / support if support > 0 else 0.0)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1s.append(2.0 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0)

    trade_mask = y_pred != 1
    return {
        "rows": int(len(y_true)),
        "acc": float((y_true == y_pred).mean()),
        "bal_acc": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1s)),
        "trade_rate": float(trade_mask.mean()),
        "trade_precision": float((y_true[trade_mask] == y_pred[trade_mask]).mean()) if trade_mask.any() else None,
        "avg_trade_conf": float(np.nanmean(conf[trade_mask])) if conf is not None and trade_mask.any() else None,
    }


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true = y_true[valid]
    y_pred = y_pred[valid]
    if len(y_true) == 0:
        return {"rows": 0, "mae": None, "r2": None, "direction_acc": None}
    err = y_pred - y_true
    denom = float(((y_true - y_true.mean()) ** 2).sum())
    r2 = 1.0 - float((err**2).sum()) / denom if denom > 1e-12 else None
    return {
        "rows": int(len(y_true)),
        "mae": float(np.abs(err).mean()),
        "r2": r2,
        "direction_acc": float((np.sign(y_pred) == np.sign(y_true)).mean()),
    }


def prepare_labels(training_data: Path, horizon_bars: int) -> pd.DataFrame:
    cols = ["ticker", "date", "time", "target", "spot_price"]
    df = pd.read_parquet(training_data, columns=cols)
    df["date"] = df["date"].astype(str)
    df["time"] = df["time"].astype(str)
    df["month"] = as_month(df["date"])
    raw_y = df["target"].to_numpy()
    if np.nanmin(raw_y) < 0:
        df["target_cls"] = np.clip(raw_y + 1, 0, 2).astype(np.int64)
    else:
        df["target_cls"] = np.clip(raw_y, 0, 2).astype(np.int64)

    sort_cols = infer_sort_columns(df)
    df = df.sort_values(sort_cols).reset_index(drop=True)
    future_spot = df.groupby(["ticker", "date"], sort=False)["spot_price"].shift(-int(horizon_bars))
    df["ret_30m_bps"] = (future_spot / df["spot_price"] - 1.0) * 10_000.0
    return df[["ticker", "date", "time", "month", "target_cls", "ret_30m_bps"]].copy()


def load_run(name: str, path: Path, labels: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_parquet(path)
    missing = {"ticker", "date", "time", *PROB_COLUMNS} - set(df.columns)
    if missing:
        raise KeyError(f"{path} missing columns: {sorted(missing)}")
    df["date"] = df["date"].astype(str)
    df["time"] = df["time"].astype(str)
    df["month"] = as_month(df["date"])
    df = df.merge(labels, on=["ticker", "date", "time", "month"], how="inner")
    df["run"] = str(name)
    probs = df[PROB_COLUMNS].to_numpy(dtype=np.float64)
    df["pred_cls"] = np.argmax(probs, axis=1).astype(np.int64)
    df["trade_confidence"] = np.maximum(probs[:, 0], probs[:, 2])
    return df


def direct_metrics(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups: list[tuple[str, pd.DataFrame]] = [("overall", df)]
    groups += [(f"ticker:{k}", g) for k, g in df.groupby("ticker", sort=True)]
    groups += [(f"month:{k}", g) for k, g in df.groupby("month", sort=True)]
    for group, part in groups:
        payload = classification_metrics(
            part["target_cls"].to_numpy(),
            part["pred_cls"].to_numpy(),
            part["trade_confidence"].to_numpy(),
        )
        payload["run"] = str(part["run"].iloc[0])
        payload["group"] = group
        rows.append(payload)
    return pd.DataFrame(rows)


def latent_metrics(df: pd.DataFrame) -> dict[str, Any]:
    z_cols = [c for c in df.columns if c.startswith("xjepa_z_")]
    z = df[z_cols].to_numpy(dtype=np.float32) if z_cols else np.zeros((len(df), 0), dtype=np.float32)
    diag = latent_diagnostics(__import__("torch").tensor(z)) if z_cols else {}
    out: dict[str, Any] = {
        "run": str(df["run"].iloc[0]),
        "rows": int(len(df)),
        "z_effective_rank": diag.get("effective_rank"),
        "z_effective_rank_ratio": diag.get("effective_rank_ratio"),
        "z_max_pc_var_ratio": diag.get("max_pc_var_ratio"),
    }
    scalar_cols = [
        "xjepa_latent_velocity",
        "xjepa_input_velocity",
        "xjepa_pred_dispersion_short",
        "xjepa_pred_dispersion_long",
        "xjepa_lagged_pred_30m_err",
        "xjepa_lagged_pred_60m_err",
        "xjepa_lagged_pred_180m_err",
        "xjepa_entropy",
    ]
    for col in scalar_cols:
        if col not in df.columns:
            continue
        values = df[col].to_numpy(dtype=np.float64)
        nonzero = values[np.isfinite(values) & (np.abs(values) > 1e-12)]
        out[f"{col}_mean"] = float(np.nanmean(values)) if len(values) else None
        out[f"{col}_p50_nonzero"] = float(np.nanpercentile(nonzero, 50)) if len(nonzero) else None
        out[f"{col}_p90_nonzero"] = float(np.nanpercentile(nonzero, 90)) if len(nonzero) else None
    return out


def prober_metrics(df: pd.DataFrame, min_train_rows: int) -> pd.DataFrame:
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("scikit-learn is required for prober metrics") from exc

    feature_cols = [
        c
        for c in df.columns
        if c.startswith("xjepa_z_")
        or c.startswith("xjepa_u_")
        or c
        in {
            "xjepa_latent_velocity",
            "xjepa_input_velocity",
            "xjepa_pred_dispersion_short",
            "xjepa_pred_dispersion_long",
            "xjepa_lagged_pred_30m_err",
            "xjepa_lagged_pred_60m_err",
            "xjepa_lagged_pred_180m_err",
            "xjepa_entropy",
        }
    ]
    if not feature_cols:
        return pd.DataFrame()

    work = df.copy()
    work[feature_cols] = work[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    months = sorted(work["month"].astype(str).unique().tolist())
    rows: list[dict[str, Any]] = []
    for month in months[1:]:
        train = work[work["month"].astype(str) < month]
        test = work[work["month"].astype(str) == month]
        if len(train) < int(min_train_rows) or test.empty:
            continue

        x_train = train[feature_cols].to_numpy(dtype=np.float32)
        x_test = test[feature_cols].to_numpy(dtype=np.float32)

        clf = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.05, max_leaf_nodes=15, random_state=17)
        clf.fit(x_train, train["target_cls"].to_numpy(dtype=np.int64))
        pred_cls = clf.predict(x_test)
        payload = classification_metrics(test["target_cls"].to_numpy(), pred_cls)
        payload.update({"run": str(df["run"].iloc[0]), "month": month, "task": "target_cls"})
        rows.append(payload)

        reg_train = train[np.isfinite(train["ret_30m_bps"].to_numpy(dtype=np.float64))]
        reg_test = test[np.isfinite(test["ret_30m_bps"].to_numpy(dtype=np.float64))]
        if len(reg_train) >= int(min_train_rows) and not reg_test.empty:
            reg = HistGradientBoostingRegressor(max_iter=80, learning_rate=0.05, max_leaf_nodes=15, random_state=17)
            reg.fit(reg_train[feature_cols].to_numpy(dtype=np.float32), reg_train["ret_30m_bps"].to_numpy(dtype=np.float64))
            pred_ret = reg.predict(reg_test[feature_cols].to_numpy(dtype=np.float32))
            payload = regression_metrics(reg_test["ret_30m_bps"].to_numpy(dtype=np.float64), pred_ret)
            payload.update({"run": str(df["run"].iloc[0]), "month": month, "task": "ret_30m_bps_reg"})
            rows.append(payload)
    return pd.DataFrame(rows)


def summarize_prober(prober: pd.DataFrame) -> pd.DataFrame:
    if prober.empty:
        return prober
    metric_cols = [
        "rows",
        "acc",
        "bal_acc",
        "macro_f1",
        "trade_rate",
        "trade_precision",
        "avg_trade_conf",
        "mae",
        "r2",
        "direction_acc",
    ]
    rows: list[dict[str, Any]] = []
    for (run, task), group in prober.groupby(["run", "task"], sort=True):
        payload: dict[str, Any] = {"run": run, "task": task}
        for col in metric_cols:
            if col in group.columns:
                payload[col] = float(pd.to_numeric(group[col], errors="coerce").mean())
        rows.append(payload)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare XInput-JEPA regularizer OOF outputs.")
    parser.add_argument("--training-data", required=True)
    parser.add_argument("--run", action="append", type=parse_run, required=True, help="NAME=OOF_PARQUET_OR_DIR")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--horizon-bars", type=int, default=6, help="5-minute bars for return probe; default 6 = 30m")
    parser.add_argument("--min-prober-train-rows", type=int, default=1000)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    labels = prepare_labels(Path(args.training_data), int(args.horizon_bars))

    all_direct: list[pd.DataFrame] = []
    all_latent: list[dict[str, Any]] = []
    all_probers: list[pd.DataFrame] = []
    run_names: list[str] = []

    for run_name, run_path in args.run:
        run_names.append(run_name)
        run_df = load_run(run_name, run_path, labels)
        all_direct.append(direct_metrics(run_df))
        all_latent.append(latent_metrics(run_df))
        all_probers.append(prober_metrics(run_df, int(args.min_prober_train_rows)))

    direct = pd.concat(all_direct, ignore_index=True)
    latent = pd.DataFrame(all_latent)
    prober = pd.concat([p for p in all_probers if not p.empty], ignore_index=True) if all_probers else pd.DataFrame()
    prober_summary = summarize_prober(prober)

    direct_path = output_dir / "xinput_direct_metrics.csv"
    latent_path = output_dir / "latent_rollout_metrics.csv"
    prober_path = output_dir / "skyjepa_style_prober_metrics.csv"
    direct.to_csv(direct_path, index=False)
    latent.to_csv(latent_path, index=False)
    if not prober.empty:
        prober.to_csv(prober_path, index=False)

    summary = {
        "runs": run_names,
        "overall_direct_metrics": direct[direct["group"].eq("overall")].to_dict(orient="records"),
        "latent_rollout_metrics": latent.to_dict(orient="records"),
        "prober_mean_metrics": prober_summary.to_dict(orient="records"),
        "outputs": {
            "direct": str(direct_path),
            "latent_rollout": str(latent_path),
            "prober": str(prober_path) if not prober.empty else None,
        },
    }
    summary_path = output_dir / "comparison_summary.json"
    summary_path.write_text(json.dumps(clean_json(summary), indent=2), encoding="utf-8")
    print(json.dumps(clean_json(summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
