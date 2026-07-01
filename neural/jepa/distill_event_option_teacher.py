from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.evaluate_xinput_level_filter import month_add, month_range  # noqa: E402
from neural.jepa.walkforward_event_option_gate import LEAKY_PATTERNS, metrics  # noqa: E402


ACTION_TO_CLASS = {"CALL": 1, "PUT": 2}
CLASS_TO_ACTION = {1: "CALL", 2: "PUT"}


@dataclass(frozen=True)
class DeployConfig:
    threshold: float
    max_trades_per_day: int

    @property
    def name(self) -> str:
        max_day = "all" if self.max_trades_per_day >= 999 else str(self.max_trades_per_day)
        return f"thr{self.threshold:.4f}_maxday{max_day}"


def parse_delta_map(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        if ":" not in str(value):
            raise ValueError(f"Invalid --delta-map item {value!r}; expected TICKER:DELTA")
        ticker, delta = str(value).split(":", 1)
        out[ticker.strip().upper()] = int(delta)
    return out


def parse_alias_map(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for value in values:
        if "=" not in str(value):
            raise ValueError(f"Invalid --ticker-alias item {value!r}; expected FROM=TO")
        src, dst = str(value).split("=", 1)
        out[src.strip().upper()] = dst.strip().upper()
    return out


def coalesce_columns(df: pd.DataFrame, names: list[str]) -> pd.Series:
    out = pd.Series(np.nan, index=df.index, dtype="float64")
    for name in names:
        if name not in df.columns:
            continue
        values = pd.to_numeric(df[name], errors="coerce")
        out = out.where(out.notna(), values)
    return out


def minute_from_time(values: pd.Series) -> pd.Series:
    text = values.astype(str).str.strip()
    hour_minute = text.str.extract(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})")
    hour = pd.to_numeric(hour_minute["hour"], errors="coerce")
    minute = pd.to_numeric(hour_minute["minute"], errors="coerce")
    return hour * 60 + minute


def normalize_action(value: object) -> str | None:
    text = str(value).strip().upper()
    if not text or text == "NAN":
        return None
    if "CALL" in text or text in {"C", "LONG"}:
        return "CALL"
    if "PUT" in text or text in {"P", "SHORT"}:
        return "PUT"
    return None


def normalize_teacher_path(path: Path, alias_map: dict[str, str]) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        return pd.DataFrame(columns=["ticker", "date", "month", "minute", "action", "teacher_return", "teacher_path"])

    if "ticker" not in df.columns:
        raise ValueError(f"{path} is missing ticker")
    date_col = "date" if "date" in df.columns else "trade_date"
    if date_col not in df.columns:
        raise ValueError(f"{path} is missing date/trade_date")

    minute = coalesce_columns(df, ["entry_minute", "minute", "minute_x", "minute_y", "known_minute"])
    if minute.isna().any() and "time" in df.columns:
        minute = minute.where(minute.notna(), minute_from_time(df["time"]))

    action_col = None
    for candidate in ["action", "option_action", "option_type", "side"]:
        if candidate in df.columns:
            action_col = candidate
            break
    if action_col is None:
        raise ValueError(f"{path} is missing action/side")

    out = pd.DataFrame(
        {
            "ticker": df["ticker"].astype(str).str.upper().map(lambda x: alias_map.get(x, x)),
            "date": df[date_col].astype(str).str.replace("-", "", regex=False).str[:8],
            "minute": minute.round().astype("Int64"),
            "action": df[action_col].map(normalize_action),
            "teacher_return": pd.to_numeric(df.get("realized_return", np.nan), errors="coerce"),
            "teacher_path": str(path),
        }
    )
    out["month"] = out["date"].astype(str).str[:6]
    out = out[out["minute"].notna() & out["action"].isin(["CALL", "PUT"])].copy()
    out["minute"] = out["minute"].astype(int)
    return out


def load_teacher(paths: list[str], alias_map: dict[str, str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(path)
        frames.append(normalize_teacher_path(path, alias_map))
    teacher = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if teacher.empty:
        return pd.DataFrame(columns=["ticker", "date", "month", "minute", "action", "teacher_return"])

    teacher["_rank_return"] = pd.to_numeric(teacher["teacher_return"], errors="coerce").fillna(-999.0)
    teacher = teacher.sort_values(
        ["ticker", "date", "minute", "_rank_return"],
        ascending=[True, True, True, False],
    )
    teacher = teacher.drop_duplicates(["ticker", "date", "minute"], keep="first")
    teacher = teacher.drop(columns=["_rank_return"])
    return teacher.reset_index(drop=True)


def prepare_frame(path: str | Path, tickers: list[str], expiry_modes: list[str]) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df = df[df["ticker"].isin(tickers)].copy()
    if expiry_modes:
        allowed = {str(mode) for mode in expiry_modes}
        df = df[df["expiry_mode"].astype(str).isin(allowed)].copy()
    df["date"] = df["trade_date"].astype(str).str.replace("-", "", regex=False).str[:8]
    df["month"] = df["date"].astype(str).str[:6]
    if "minute" not in df.columns:
        df["minute"] = minute_from_time(df["time"])
    df["minute"] = pd.to_numeric(df["minute"], errors="coerce").round().astype("Int64")
    df = df[df["minute"].notna()].copy()
    df["minute"] = df["minute"].astype(int)
    return df.reset_index(drop=True)


def attach_teacher_labels(frame: pd.DataFrame, teacher: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    keys = ["ticker", "date", "minute"]
    labeled = frame.merge(
        teacher[keys + ["action", "teacher_return"]].rename(
            columns={"action": "teacher_action", "teacher_return": "teacher_realized_return"}
        ),
        on=keys,
        how="left",
    )
    labeled["teacher_class"] = labeled["teacher_action"].map(ACTION_TO_CLASS).fillna(0).astype(int)
    summary = (
        labeled.groupby(["ticker", "month", "teacher_class"], dropna=False)
        .size()
        .rename("rows")
        .reset_index()
        .sort_values(["ticker", "month", "teacher_class"])
    )
    return labeled, summary


def feature_columns(frame: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, list[str]]:
    work = frame.copy()
    cats = [c for c in ["ticker", "expiry_mode", "nearest_level_name"] if c in work.columns]
    if cats:
        work = pd.concat([work, pd.get_dummies(work[cats].astype(str), prefix=cats, dtype=float)], axis=1)

    dummy_prefixes = tuple(f"{c}_" for c in cats)
    include_prefixes = tuple(str(x).lower() for x in args.feature_include_prefixes if str(x).strip())
    exclude_prefixes = tuple(str(x).lower() for x in args.feature_exclude_prefixes if str(x).strip())

    if args.feature_set == "physics":
        exclude_prefixes = tuple(sorted(set(exclude_prefixes + ("ptdj_",))))
    elif args.feature_set == "ptdj-only":
        include_prefixes = tuple(sorted(set(include_prefixes + ("ptdj_",))))

    excluded_exact = {
        "trade_date",
        "date",
        "month",
        "expiration",
        "timestamp",
        "time",
        "underlying_ticker",
        "nearest_level_name",
        "expiry_mode",
        "teacher_action",
        "teacher_realized_return",
        "teacher_class",
    }
    selected: list[str] = []
    for col in work.columns:
        low = str(col).lower()
        if col in excluded_exact:
            continue
        if any(pattern in low for pattern in LEAKY_PATTERNS):
            continue
        if exclude_prefixes and low.startswith(exclude_prefixes):
            continue
        if include_prefixes and not (low.startswith(include_prefixes) or low.startswith(dummy_prefixes)):
            continue
        if pd.api.types.is_numeric_dtype(work[col]):
            selected.append(col)
    return work, selected


def return_columns_for_delta(delta: int) -> tuple[str, str]:
    return f"call_d{int(delta):02d}_opt_exit_ret", f"put_d{int(delta):02d}_opt_exit_ret"


def score_metrics(
    row: dict[str, Any],
    min_trades: int,
    min_month_trades: int,
    min_pf: float,
    min_win_rate: float,
    min_call_rate: float,
    max_call_rate: float,
) -> float:
    trades = int(row.get("trades", 0))
    min_month = int(row.get("min_month_trades", 0))
    pf = float(row.get("profit_factor", 0.0))
    win_rate = float(row.get("win_rate", float("nan")))
    call_rate = float(row.get("call_rate", float("nan")))
    if trades < min_trades or min_month < min_month_trades:
        return -1e18 + trades
    if not np.isfinite(pf) or not np.isfinite(win_rate) or not np.isfinite(call_rate):
        return -1e18 + trades
    if pf < min_pf or win_rate < min_win_rate:
        return -1e18 + trades
    if call_rate < min_call_rate or call_rate > max_call_rate:
        return -1e18 + trades
    pnl = float(row.get("pnl_return", 0.0))
    dd = abs(float(row.get("max_drawdown", 0.0)))
    positive_month_rate = float(row.get("positive_month_rate", 0.0))
    return (
        3.0 * math.log1p(min(max(pf, 0.0), 10.0))
        + 0.45 * math.log1p(trades)
        + pnl / 10.0
        - dd / 5.0
        + positive_month_rate
    )


def deploy(scored: pd.DataFrame, cfg: DeployConfig, cooldown_minutes: int) -> pd.DataFrame:
    candidates = scored[scored["score"].astype(float) >= float(cfg.threshold)].copy()
    if candidates.empty:
        return candidates
    rows: list[dict[str, Any]] = []
    for _, day in candidates.sort_values(["date", "minute", "score"], ascending=[True, True, False]).groupby(
        "date", sort=False
    ):
        next_allowed = -1
        taken = 0
        for row in day.itertuples(index=False):
            minute = int(row.minute)
            if minute < next_allowed:
                continue
            if taken >= int(cfg.max_trades_per_day):
                break
            values = row._asdict()
            values["deploy_config"] = cfg.name
            rows.append(values)
            taken += 1
            next_allowed = minute + int(cooldown_minutes)
    return pd.DataFrame(rows) if rows else candidates.iloc[0:0].copy()


def build_fold_grid(scored_val: pd.DataFrame, args: argparse.Namespace) -> list[DeployConfig]:
    thresholds = [float(thr) for thr in args.threshold_grid]
    if args.threshold_quantiles and not scored_val.empty:
        finite = pd.to_numeric(scored_val["score"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if len(finite):
            thresholds.extend(float(value) for value in np.quantile(finite, [float(q) for q in args.threshold_quantiles]))
    thresholds = sorted(set(round(float(thr), 8) for thr in thresholds if np.isfinite(float(thr))))
    return [DeployConfig(thr, int(max_day)) for thr in thresholds for max_day in args.max_day_grid]


def class_sample_weight(y: pd.Series, multiplier: float, max_weight: float) -> np.ndarray:
    counts = y.value_counts().to_dict()
    classes = sorted(counts)
    if not classes:
        return np.ones(len(y), dtype=float)
    total = float(len(y))
    weights: dict[int, float] = {}
    for cls in classes:
        raw = total / (len(classes) * float(counts[cls]))
        if int(cls) != 0:
            raw *= float(multiplier)
        weights[int(cls)] = min(float(raw), float(max_weight))
    return y.map(weights).astype(float).to_numpy()


def predict_multiclass(model: lgb.LGBMClassifier, x: pd.DataFrame) -> np.ndarray:
    raw = model.predict_proba(x)
    out = np.zeros((len(x), 3), dtype=float)
    for idx, cls in enumerate(model.classes_):
        cls_int = int(cls)
        if 0 <= cls_int <= 2:
            out[:, cls_int] = raw[:, idx]
    return out


def score_part(
    part: pd.DataFrame,
    feature_cols: list[str],
    medians: pd.Series,
    model: lgb.LGBMClassifier,
    delta: int,
) -> pd.DataFrame:
    if part.empty:
        return part.copy()
    call_col, put_col = return_columns_for_delta(delta)
    out = part.copy()
    x = out[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    probs = predict_multiclass(model, x)
    out["pred_no_trade"] = probs[:, 0]
    out["pred_call_teacher"] = probs[:, 1]
    out["pred_put_teacher"] = probs[:, 2]
    call_action = out["pred_call_teacher"].astype(float) >= out["pred_put_teacher"].astype(float)
    out["action"] = np.where(call_action, "CALL", "PUT")
    out["score"] = np.where(call_action, out["pred_call_teacher"], out["pred_put_teacher"])
    out["call_return"] = pd.to_numeric(out[call_col], errors="coerce")
    out["put_return"] = pd.to_numeric(out[put_col], errors="coerce")
    out["realized_return"] = np.where(call_action, out["call_return"], out["put_return"])
    out["delta_bucket"] = int(delta)
    return out[np.isfinite(out["realized_return"].astype(float))].copy()


def fold_paths(output_dir: Path, ticker: str, test_month: str) -> tuple[Path, Path]:
    fold_dir = output_dir / "folds"
    return fold_dir / f"{ticker}_{test_month}_trades.csv", fold_dir / f"{ticker}_{test_month}_fold.json"


def fit_fold(task: dict[str, Any]) -> dict[str, Any]:
    ticker = str(task["ticker"]).upper()
    test_month = str(task["test_month"])
    frame: pd.DataFrame = task["frame"]
    feature_cols: list[str] = task["feature_cols"]
    args: argparse.Namespace = task["args"]
    delta_map: dict[str, int] = task["delta_map"]
    output_dir = Path(task["output_dir"])
    trades_path, fold_path = fold_paths(output_dir, ticker, test_month)
    trades_path.parent.mkdir(parents=True, exist_ok=True)

    if trades_path.exists() and fold_path.exists() and not bool(args.force):
        return {"ticker": ticker, "test_month": test_month, "status": "skipped_existing"}

    val_months = [month_add(test_month, -i) for i in range(int(args.val_months), 0, -1)]
    first_val = val_months[0]
    tdf = frame[frame["ticker"].astype(str).eq(ticker)].copy()
    train = tdf[tdf["month"].astype(str) < first_val].copy()
    val = tdf[tdf["month"].astype(str).isin(val_months)].copy()
    test = tdf[tdf["month"].astype(str).eq(test_month)].copy()

    fold_row: dict[str, Any] = {
        "ticker": ticker,
        "test_month": test_month,
        "train_months": ",".join(sorted(train["month"].astype(str).unique())),
        "val_months": ",".join(val_months),
        "train_rows": int(len(train)),
        "val_rows": int(len(val)),
        "test_rows": int(len(test)),
        "status": "OK",
    }
    if len(train) < int(args.min_train_rows) or len(val) < int(args.min_val_rows) or test.empty:
        fold_row["status"] = "INSUFFICIENT_ROWS"
        pd.DataFrame().to_csv(trades_path, index=False)
        fold_path.write_text(json.dumps(fold_row, indent=2, allow_nan=True), encoding="utf-8")
        return {"ticker": ticker, "test_month": test_month, "status": fold_row["status"]}

    y = train["teacher_class"].astype(int)
    positives = int((y > 0).sum())
    fold_row["train_positive_rows"] = positives
    fold_row["train_call_rows"] = int((y == 1).sum())
    fold_row["train_put_rows"] = int((y == 2).sum())
    if positives < int(args.min_train_positive) or y.nunique() < 2:
        fold_row["status"] = "INSUFFICIENT_POSITIVES"
        pd.DataFrame().to_csv(trades_path, index=False)
        fold_path.write_text(json.dumps(fold_row, indent=2, allow_nan=True), encoding="utf-8")
        return {"ticker": ticker, "test_month": test_month, "status": fold_row["status"]}

    medians = train[feature_cols].replace([np.inf, -np.inf], np.nan).median(numeric_only=True)
    x_train = train[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(medians).fillna(0.0)
    weights = class_sample_weight(y, float(args.positive_weight_multiplier), float(args.max_class_weight))

    model = lgb.LGBMClassifier(
        objective="multiclass",
        num_class=3,
        n_estimators=int(args.n_estimators),
        learning_rate=float(args.learning_rate),
        num_leaves=int(args.num_leaves),
        min_child_samples=int(args.min_child_samples),
        subsample=float(args.subsample),
        colsample_bytree=float(args.colsample_bytree),
        reg_lambda=float(args.reg_lambda),
        random_state=int(args.seed) + int(test_month[-2:]) + sum(ord(ch) for ch in ticker),
        n_jobs=int(args.lgb_jobs),
        verbose=-1,
    )
    model.fit(x_train, y, sample_weight=weights)

    delta = int(delta_map[ticker])
    val_scored = score_part(val, feature_cols, medians, model, delta)
    test_scored = score_part(test, feature_cols, medians, model, delta)
    fold_grid = build_fold_grid(val_scored, args)
    best_cfg = fold_grid[0]
    best_score = -1e18
    best_metrics: dict[str, Any] = {}
    for cfg in fold_grid:
        val_trades = deploy(val_scored, cfg, int(args.cooldown_minutes))
        row = metrics(val_trades, val_months)
        score = score_metrics(
            row,
            int(args.min_val_trades),
            int(args.min_month_trades),
            float(args.min_val_pf),
            float(args.min_val_win_rate),
            float(args.min_call_rate),
            float(args.max_call_rate),
        )
        if score > best_score:
            best_cfg = cfg
            best_score = score
            best_metrics = row

    valid_val_selection = bool(best_score > -1e17)
    if not valid_val_selection and not bool(args.allow_invalid_val_deploy):
        test_trades = pd.DataFrame()
        test_metrics = metrics(test_trades, [test_month])
        fold_row["status"] = "ABSTAIN_INVALID_VAL"
    else:
        test_trades = deploy(test_scored, best_cfg, int(args.cooldown_minutes))
        test_metrics = metrics(test_trades, [test_month])
        if not test_trades.empty:
            test_trades["test_month"] = test_month
            test_trades["fold_month"] = test_month
            test_trades["delta_bucket"] = delta
            test_trades["teacher_model_feature_set"] = str(args.feature_set)
            test_trades["teacher_model_config"] = best_cfg.name

    fold_row.update(
        {
            "deploy_config": best_cfg.name,
            "val_score": float(best_score),
            "abstained_invalid_val": bool(not valid_val_selection),
            **{f"val_{k}": v for k, v in best_metrics.items()},
            **{f"test_{k}": v for k, v in test_metrics.items()},
        }
    )
    keep_cols = [
        "ticker",
        "date",
        "month",
        "time",
        "minute",
        "expiry_mode",
        "action",
        "score",
        "pred_no_trade",
        "pred_call_teacher",
        "pred_put_teacher",
        "call_return",
        "put_return",
        "realized_return",
        "delta_bucket",
        "deploy_config",
        "test_month",
        "fold_month",
        "teacher_model_feature_set",
        "teacher_model_config",
    ]
    if test_trades.empty:
        pd.DataFrame(columns=keep_cols).to_csv(trades_path, index=False)
    else:
        test_trades[[c for c in keep_cols if c in test_trades.columns]].to_csv(trades_path, index=False)
    fold_path.write_text(json.dumps(fold_row, indent=2, allow_nan=True), encoding="utf-8")
    return {
        "ticker": ticker,
        "test_month": test_month,
        "status": fold_row["status"],
        "trades": int(test_metrics.get("trades", 0)),
        "pf": float(test_metrics.get("profit_factor", float("nan"))),
        "pnl_return": float(test_metrics.get("pnl_return", 0.0)),
    }


def load_checkpoints(output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    fold_dir = output_dir / "folds"
    trade_frames: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    if not fold_dir.exists():
        return pd.DataFrame(), pd.DataFrame()
    for trade_path in sorted(fold_dir.glob("*_trades.csv")):
        if trade_path.stat().st_size > 0:
            trade = pd.read_csv(trade_path, dtype={"date": str, "month": str, "test_month": str})
            if not trade.empty:
                trade_frames.append(trade)
    for fold_path in sorted(fold_dir.glob("*_fold.json")):
        fold_rows.append(json.loads(fold_path.read_text(encoding="utf-8")))
    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    return trades, folds


def write_curve(trades: pd.DataFrame, output_dir: Path, risk_capital: float) -> None:
    if trades.empty:
        return
    daily = (
        trades.assign(net_pnl=pd.to_numeric(trades["realized_return"], errors="coerce").fillna(0.0) * float(risk_capital))
        .groupby("date", as_index=False)["net_pnl"]
        .sum()
        .sort_values("date")
    )
    daily["cumulative_net_pnl"] = daily["net_pnl"].cumsum()
    daily.to_csv(output_dir / "daily_net_pnl.csv", index=False)
    try:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(pd.to_datetime(daily["date"], format="%Y%m%d"), daily["cumulative_net_pnl"], linewidth=1.8)
        ax.axhline(0.0, color="black", linewidth=0.8)
        ax.set_title("Teacher Distillation Cumulative Net PnL")
        ax.set_ylabel("Net PnL ($)")
        ax.grid(True, alpha=0.25)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(output_dir / "daily_net_pnl.png", dpi=140)
        plt.close(fig)
    except Exception:
        return


def write_summary(
    output_dir: Path,
    trades: pd.DataFrame,
    folds: pd.DataFrame,
    metadata: dict[str, Any],
    expected_months: list[str],
    risk_capital: float,
) -> None:
    if not trades.empty:
        trades["realized_return"] = pd.to_numeric(trades["realized_return"], errors="coerce").fillna(0.0)
    overall = metrics(trades, expected_months)
    by_ticker = (
        {str(ticker): metrics(part.copy(), expected_months) for ticker, part in trades.groupby("ticker", sort=True)}
        if not trades.empty
        else {}
    )
    payload = {
        "overall": overall,
        "by_ticker": by_ticker,
        "risk_capital": float(risk_capital),
        "net_pnl": float(overall.get("pnl_return", 0.0)) * float(risk_capital),
        "metadata": metadata,
    }
    (output_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Event Option Teacher Distillation",
        "",
        "Causal walk-forward student model trained only on prior teacher selections. The teacher can be profitable while this student fails if the selected feature set does not contain the teacher's routing information.",
        "",
        "## Overall",
        "",
        f"- Trades: {int(overall.get('trades', 0))}",
        f"- WR: {float(overall.get('win_rate', float('nan'))):.2%}",
        f"- PF: {float(overall.get('profit_factor', float('nan'))):.3f}",
        f"- PnL: {float(payload['net_pnl']):,.0f}",
        f"- Min month trades: {int(overall.get('min_month_trades', 0))}",
        f"- Positive month rate: {float(overall.get('positive_month_rate', float('nan'))):.1%}",
        "",
        "## Per Ticker",
        "",
        "| Ticker | Trades | WR | PF | PnL | Min Month Trades | Call Rate | Positive Months |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker, row in by_ticker.items():
        positive_months = float(row.get("positive_month_rate", 0.0)) * len(expected_months)
        lines.append(
            f"| {ticker} | {int(row.get('trades', 0))} | {float(row.get('win_rate', float('nan'))):.2%} | "
            f"{float(row.get('profit_factor', float('nan'))):.3f} | "
            f"{float(row.get('pnl_return', 0.0)) * float(risk_capital):,.0f} | "
            f"{int(row.get('min_month_trades', 0))} | {float(row.get('call_rate', float('nan'))):.2%} | "
            f"{positive_months:.0f}/{len(expected_months)} |"
        )
    lines += [
        "",
        "## Fold Checkpoints",
        "",
        f"- Folds written: {int(len(folds))}",
        f"- Output: `{output_dir}`",
        "",
        "## Config",
        "",
        "```json",
        json.dumps(metadata, indent=2, allow_nan=True),
        "```",
    ]
    (output_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Distill composed event-option teacher trades into a causal live-style student.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--teacher-path", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--ticker-alias", nargs="*", default=["SPX=SPXW"])
    parser.add_argument("--delta-map", nargs="+", default=["SPXW:35", "SPY:35", "QQQ:50"])
    parser.add_argument("--expiry-modes", nargs="*", default=[])
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202605")
    parser.add_argument("--val-months", type=int, default=2)
    parser.add_argument("--feature-set", choices=["physics", "ptdj", "ptdj-only", "custom"], default="physics")
    parser.add_argument("--feature-include-prefixes", nargs="*", default=[])
    parser.add_argument("--feature-exclude-prefixes", nargs="*", default=[])
    parser.add_argument("--min-train-rows", type=int, default=500)
    parser.add_argument("--min-val-rows", type=int, default=30)
    parser.add_argument("--min-train-positive", type=int, default=20)
    parser.add_argument("--min-val-trades", type=int, default=20)
    parser.add_argument("--min-month-trades", type=int, default=3)
    parser.add_argument("--min-val-pf", type=float, default=0.0)
    parser.add_argument("--min-val-win-rate", type=float, default=0.0)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--n-estimators", type=int, default=260)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=31)
    parser.add_argument("--min-child-samples", type=int, default=80)
    parser.add_argument("--subsample", type=float, default=0.85)
    parser.add_argument("--colsample-bytree", type=float, default=0.85)
    parser.add_argument("--reg-lambda", type=float, default=5.0)
    parser.add_argument("--positive-weight-multiplier", type=float, default=1.0)
    parser.add_argument("--max-class-weight", type=float, default=100.0)
    parser.add_argument("--lgb-jobs", type=int, default=1)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--threshold-grid",
        nargs="+",
        type=float,
        default=[0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50],
    )
    parser.add_argument("--threshold-quantiles", nargs="+", type=float, default=[0.50, 0.70, 0.85, 0.92, 0.97, 0.99])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[12, 8, 6, 4, 3, 2, 1])
    parser.add_argument("--allow-invalid-val-deploy", action="store_true")
    parser.add_argument("--risk-capital", type=float, default=5000.0)
    parser.add_argument("--seed", type=int, default=20260621)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tickers = [str(t).upper() for t in args.tickers]
    delta_map = parse_delta_map(args.delta_map)
    missing_delta = sorted(set(tickers).difference(delta_map))
    if missing_delta:
        raise ValueError(f"Missing --delta-map entries for {missing_delta}")

    alias_map = parse_alias_map(args.ticker_alias)
    teacher = load_teacher(args.teacher_path, alias_map)
    frame = prepare_frame(args.data, tickers, args.expiry_modes)
    frame, label_summary = attach_teacher_labels(frame, teacher)
    frame, features = feature_columns(frame, args)
    label_summary.to_csv(output_dir / "teacher_label_summary.csv", index=False)

    for ticker, delta in delta_map.items():
        if ticker not in tickers:
            continue
        call_col, put_col = return_columns_for_delta(delta)
        missing = [col for col in [call_col, put_col] if col not in frame.columns]
        if missing:
            raise ValueError(f"{ticker} delta {delta} missing return columns {missing}")

    months = month_range(str(args.start_month), str(args.end_month))
    tasks: list[dict[str, Any]] = []
    for ticker in tickers:
        for test_month in months:
            tasks.append(
                {
                    "ticker": ticker,
                    "test_month": test_month,
                    "frame": frame,
                    "feature_cols": features,
                    "args": args,
                    "delta_map": delta_map,
                    "output_dir": str(output_dir),
                }
            )

    metadata = {
        "args": vars(args),
        "feature_count": len(features),
        "features": features,
        "teacher_rows": int(len(teacher)),
        "data_rows": int(len(frame)),
        "grid": [asdict(cfg) for cfg in build_fold_grid(frame.iloc[0:0].assign(score=[]), args)],
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")

    max_workers = max(1, min(int(args.workers), len(tasks)))
    if max_workers == 1:
        for task in tasks:
            result = fit_fold(task)
            print(json.dumps(result, allow_nan=True), flush=True)
    else:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(fit_fold, task) for task in tasks]
            for future in as_completed(futures):
                result = future.result()
                print(json.dumps(result, allow_nan=True), flush=True)

    trades, folds = load_checkpoints(output_dir)
    if not trades.empty:
        trades = trades.sort_values(["date", "minute", "ticker"]).reset_index(drop=True)
        trades.to_csv(output_dir / "combined_trades.csv", index=False)
        trades.to_csv(output_dir / "teacher_distill_trades.csv", index=False)
    if not folds.empty:
        folds = folds.sort_values(["test_month", "ticker"]).reset_index(drop=True)
        folds.to_csv(output_dir / "combined_folds.csv", index=False)
        folds.to_csv(output_dir / "teacher_distill_folds.csv", index=False)
    write_curve(trades, output_dir, float(args.risk_capital))
    write_summary(output_dir, trades, folds, metadata, months, float(args.risk_capital))
    print((output_dir / "SUMMARY.md").read_text(encoding="utf-8"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
