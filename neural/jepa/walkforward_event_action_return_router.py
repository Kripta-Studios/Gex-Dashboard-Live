from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.ensemble import HistGradientBoostingRegressor


META_COLS = ["ticker", "trade_date", "expiry_mode", "minute"]
DROP_PATTERNS = (
    "future",
    "spot_long",
    "spot_short",
    "spot_best",
    "_opt_win",
    "_opt_status",
    "_opt_exit_ret",
    "_opt_exit_minutes",
    "_opt_max_ret",
    "_opt_min_ret",
)


@dataclass(frozen=True)
class DeployConfig:
    threshold: float
    max_trades_per_day: int

    @property
    def name(self) -> str:
        max_day = "all" if self.max_trades_per_day >= 999 else str(self.max_trades_per_day)
        return f"thr{self.threshold:.5f}_maxday{max_day}"


def month_range(start: str, end: str) -> list[str]:
    y = int(str(start)[:4])
    m = int(str(start)[4:6])
    end_i = int(str(end))
    out: list[str] = []
    while y * 100 + m <= end_i:
        out.append(f"{y:04d}{m:02d}")
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def action_columns(deltas: list[int]) -> dict[str, str]:
    cols: dict[str, str] = {}
    for delta in deltas:
        cols[f"CALL_d{delta:02d}"] = f"call_d{delta:02d}_opt_exit_ret"
        cols[f"PUT_d{delta:02d}"] = f"put_d{delta:02d}_opt_exit_ret"
    return cols


def read_frame(path: Path, deltas: list[int], tickers: list[str], expiry_modes: list[str]) -> pd.DataFrame:
    available = set(pq.ParquetFile(path).schema.names)
    labels = list(action_columns(deltas).values())
    cols = [c for c in available if c in META_COLS or c in labels or is_candidate_feature(c)]
    frame = pd.read_parquet(path, columns=cols)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["trade_date"] = frame["trade_date"].astype(str).str.replace("-", "", regex=False).str[:8]
    frame["month"] = frame["trade_date"].str[:6]
    frame["date"] = frame["trade_date"]
    frame["minute"] = pd.to_numeric(frame["minute"], errors="coerce").fillna(0).astype(int)
    frame = frame[frame["ticker"].isin([t.upper() for t in tickers])].copy()
    if expiry_modes:
        frame = frame[frame["expiry_mode"].astype(str).isin({str(m) for m in expiry_modes})].copy()
    return frame.sort_values(["ticker", "date", "minute"]).reset_index(drop=True)


def is_candidate_feature(col: str) -> bool:
    low = str(col).lower()
    if any(pattern in low for pattern in DROP_PATTERNS):
        return False
    if low in {"ticker", "underlying_ticker", "trade_date", "expiration", "expiry_mode", "timestamp", "time", "date"}:
        return False
    return True


def feature_columns(frame: pd.DataFrame, args: argparse.Namespace) -> list[str]:
    include = tuple(str(x).lower() for x in args.feature_include_prefixes if str(x).strip())
    exclude = tuple(str(x).lower() for x in args.feature_exclude_prefixes if str(x).strip())
    cols: list[str] = []
    for col in frame.columns:
        low = str(col).lower()
        if not is_candidate_feature(col):
            continue
        if exclude and low.startswith(exclude):
            continue
        if include and not low.startswith(include):
            continue
        if pd.api.types.is_numeric_dtype(frame[col]):
            cols.append(col)
    return cols


def metrics(trades: pd.DataFrame, expected_months: list[str]) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_return": 0.0,
            "max_drawdown": 0.0,
            "call_rate": float("nan"),
            "min_month_trades": 0,
            "positive_month_rate": float("nan"),
            "days_with_trades": 0,
            "daily_win_rate": float("nan"),
            "median_daily_return": float("nan"),
        }
    ret = pd.to_numeric(trades["realized_return"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    wins = ret[ret > 0.0]
    losses = ret[ret < 0.0]
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    equity = np.cumsum(ret)
    peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    by_month = trades.groupby("month")["realized_return"].agg(["count", "sum"]).reindex(expected_months, fill_value=0)
    daily = trades.groupby("date")["realized_return"].sum().astype(float).sort_index()
    return {
        "trades": int(len(trades)),
        "win_rate": float((ret > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_return": float(ret.sum()),
        "max_drawdown": float((equity - peak).min()) if len(equity) else 0.0,
        "call_rate": float((trades["action"].astype(str).str.startswith("CALL")).mean()),
        "min_month_trades": int(by_month["count"].min()) if not by_month.empty else 0,
        "positive_month_rate": float((by_month["sum"] > 0.0).mean()) if not by_month.empty else float("nan"),
        "days_with_trades": int(len(daily)),
        "daily_win_rate": float((daily > 0.0).mean()) if len(daily) else float("nan"),
        "median_daily_return": float(daily.median()) if len(daily) else float("nan"),
    }


def pass_gate(row: dict, args: argparse.Namespace) -> bool:
    if int(row["trades"]) < int(args.min_trades):
        return False
    if int(row["min_month_trades"]) < int(args.min_month_trades):
        return False
    if not np.isfinite(float(row["win_rate"])) or float(row["win_rate"]) < float(args.min_win_rate):
        return False
    if not np.isfinite(float(row["profit_factor"])) or float(row["profit_factor"]) < float(args.min_pf):
        return False
    if float(row["pnl_return"]) <= 0.0:
        return False
    call_rate = float(row["call_rate"])
    return np.isfinite(call_rate) and float(args.min_call_rate) <= call_rate <= float(args.max_call_rate)


def score(row: dict) -> float:
    if int(row.get("trades", 0)) <= 0 or not np.isfinite(float(row.get("profit_factor", float("nan")))):
        return -1e18
    return (
        4.0 * math.log(max(float(row["profit_factor"]), 1e-6))
        + 2.0 * float(row["win_rate"])
        + float(row["pnl_return"]) / 20.0
        - abs(float(row["max_drawdown"])) / 8.0
        + float(row.get("positive_month_rate", 0.0))
    )


def fit_action_models(
    train: pd.DataFrame,
    features: list[str],
    actions: dict[str, str],
    args: argparse.Namespace,
) -> dict[str, HistGradientBoostingRegressor | HistGradientBoostingClassifier]:
    models: dict[str, HistGradientBoostingRegressor | HistGradientBoostingClassifier] = {}
    x_train = train[features]
    for action, col in actions.items():
        y = pd.to_numeric(train[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        mask = y.notna()
        if int(mask.sum()) < int(args.min_action_rows):
            continue
        if str(args.target_mode) == "win":
            target = (y[mask].astype(float) > 0.0).astype(int)
            if target.nunique() < 2:
                continue
            model = HistGradientBoostingClassifier(
                learning_rate=float(args.learning_rate),
                max_iter=int(args.max_iter),
                max_leaf_nodes=int(args.max_leaf_nodes),
                min_samples_leaf=int(args.min_samples_leaf),
                l2_regularization=float(args.l2_regularization),
                random_state=int(args.seed) + len(models),
            )
        else:
            target = y[mask].astype(float).clip(-float(args.clip_return), float(args.clip_return))
            model = HistGradientBoostingRegressor(
                loss=str(args.loss),
                learning_rate=float(args.learning_rate),
                max_iter=int(args.max_iter),
                max_leaf_nodes=int(args.max_leaf_nodes),
                min_samples_leaf=int(args.min_samples_leaf),
                l2_regularization=float(args.l2_regularization),
                random_state=int(args.seed) + len(models),
            )
        model.fit(x_train.loc[mask], target)
        models[action] = model
    return models


def score_actions(
    frame: pd.DataFrame,
    features: list[str],
    actions: dict[str, str],
    models: dict[str, HistGradientBoostingRegressor | HistGradientBoostingClassifier],
    clip_return: float,
) -> pd.DataFrame:
    if frame.empty or not models:
        return frame.iloc[0:0].copy()
    pred_cols: list[str] = []
    work = frame.copy()
    x = work[features]
    for action, model in models.items():
        pred_col = f"pred_{action}"
        if hasattr(model, "predict_proba"):
            work[pred_col] = model.predict_proba(x)[:, 1]
        else:
            work[pred_col] = model.predict(x)
        pred_cols.append(pred_col)
    pred_values = work[pred_cols].to_numpy(dtype=float)
    best_idx = np.nanargmax(pred_values, axis=1)
    action_list = [c.removeprefix("pred_") for c in pred_cols]
    work["action"] = [action_list[i] for i in best_idx]
    work["score"] = pred_values[np.arange(len(work)), best_idx]
    realized = []
    for action, row_idx in zip(work["action"].tolist(), work.index):
        col = actions[action]
        realized.append(work.at[row_idx, col])
    work["realized_return"] = pd.to_numeric(pd.Series(realized, index=work.index), errors="coerce")
    work = work[np.isfinite(work["realized_return"].astype(float))].copy()
    work["realized_return"] = work["realized_return"].clip(-float(clip_return), float(clip_return))
    return work


def deploy(scored: pd.DataFrame, cfg: DeployConfig, cooldown_minutes: int) -> pd.DataFrame:
    selected = scored[scored["score"].astype(float) >= float(cfg.threshold)].copy()
    if selected.empty:
        return selected
    rows: list[dict] = []
    for _, day in selected.sort_values(["date", "minute", "score"], ascending=[True, True, False]).groupby("date", sort=False):
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
    return pd.DataFrame(rows) if rows else selected.iloc[0:0].copy()


def build_grid(scored_select: pd.DataFrame, args: argparse.Namespace) -> list[DeployConfig]:
    thresholds = [float(x) for x in args.threshold_grid]
    finite = pd.to_numeric(scored_select["score"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if not finite.empty:
        thresholds.extend(float(x) for x in finite.quantile([float(q) for q in args.threshold_quantiles]).to_numpy())
    unique = sorted(set(round(float(x), 8) for x in thresholds if np.isfinite(float(x))))
    return [DeployConfig(float(thr), int(max_day)) for thr in unique for max_day in args.max_day_grid]


def choose_config(scored_select: pd.DataFrame, select_months: list[str], args: argparse.Namespace) -> tuple[DeployConfig | None, dict, pd.DataFrame]:
    rows: list[dict] = []
    best_cfg: DeployConfig | None = None
    best_score = -1e18
    best_metrics: dict = metrics(scored_select.iloc[0:0].copy(), select_months)
    for cfg in build_grid(scored_select, args):
        trades = deploy(scored_select, cfg, int(args.cooldown_minutes))
        row = metrics(trades, select_months)
        rows.append({**asdict(cfg), "name": cfg.name, "score": score(row), **row})
        if pass_gate(row, args):
            row_score = score(row)
            if row_score > best_score:
                best_score = row_score
                best_cfg = cfg
                best_metrics = row
    return best_cfg, best_metrics, pd.DataFrame(rows).sort_values(["score", "profit_factor", "pnl_return"], ascending=False)


def evaluate_ticker(frame: pd.DataFrame, ticker: str, features: list[str], actions: dict[str, str], args: argparse.Namespace) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    fit_months = month_range(args.fit_start_month, args.fit_end_month)
    select_months = month_range(args.select_start_month, args.select_end_month)
    test1_months = month_range(args.test1_start_month, args.test1_end_month)
    test2_months = month_range(args.test2_start_month, args.test2_end_month)
    tdf = frame[frame["ticker"].eq(ticker)].copy()
    train = tdf[tdf["month"].isin(fit_months)].copy()
    select = tdf[tdf["month"].isin(select_months)].copy()
    test1 = tdf[tdf["month"].isin(test1_months)].copy()
    test2 = tdf[tdf["month"].isin(test2_months)].copy()
    models = fit_action_models(train, features, actions, args)
    scored_select = score_actions(select, features, actions, models, float(args.clip_return))
    scored_test1 = score_actions(test1, features, actions, models, float(args.clip_return))
    scored_test2 = score_actions(test2, features, actions, models, float(args.clip_return))
    cfg, select_metrics, candidates = choose_config(scored_select, select_months, args)
    if cfg is None:
        return {
            "ticker": ticker,
            "status": "NO_SELECT_CONFIG",
            "models": sorted(models.keys()),
            "select_metrics": select_metrics,
            "test1_metrics": metrics(scored_test1.iloc[0:0].copy(), test1_months),
            "test2_metrics": metrics(scored_test2.iloc[0:0].copy(), test2_months),
        }, pd.DataFrame(), candidates
    selected_frames: list[pd.DataFrame] = []
    period_metrics: dict[str, dict] = {}
    for label, months, scored in [
        ("select", select_months, scored_select),
        ("test1", test1_months, scored_test1),
        ("test2", test2_months, scored_test2),
    ]:
        trades = deploy(scored, cfg, int(args.cooldown_minutes))
        period_metrics[f"{label}_metrics"] = metrics(trades, months)
        if not trades.empty:
            trades = trades.copy()
            trades["period"] = label
            selected_frames.append(trades)
    return {
        "ticker": ticker,
        "status": "DEPLOYED",
        "models": sorted(models.keys()),
        "deploy_config": asdict(cfg),
        **period_metrics,
    }, pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame(), candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen action-return router over event-option rows.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--expiry-modes", nargs="+", default=["zero_dte"])
    parser.add_argument("--fit-start-month", default="202201")
    parser.add_argument("--fit-end-month", default="202312")
    parser.add_argument("--select-start-month", default="202401")
    parser.add_argument("--select-end-month", default="202412")
    parser.add_argument("--test1-start-month", default="202501")
    parser.add_argument("--test1-end-month", default="202512")
    parser.add_argument("--test2-start-month", default="202601")
    parser.add_argument("--test2-end-month", default="202606")
    parser.add_argument("--deltas", nargs="+", type=int, default=[50, 65, 80])
    parser.add_argument("--feature-include-prefixes", nargs="*", default=[
        "minute",
        "underlying_volume",
        "dist_",
        "nearest_",
        "ib_",
        "ret_",
        "phys_",
        "ctx_",
    ])
    parser.add_argument("--feature-exclude-prefixes", nargs="*", default=[])
    parser.add_argument("--target-mode", choices=["return", "win"], default="return")
    parser.add_argument("--loss", default="squared_error")
    parser.add_argument("--max-iter", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--max-leaf-nodes", type=int, default=15)
    parser.add_argument("--min-samples-leaf", type=int, default=60)
    parser.add_argument("--l2-regularization", type=float, default=0.05)
    parser.add_argument("--min-action-rows", type=int, default=500)
    parser.add_argument("--threshold-grid", nargs="+", type=float, default=[-0.20, -0.10, 0.0, 0.05, 0.10, 0.15, 0.20])
    parser.add_argument("--threshold-quantiles", nargs="+", type=float, default=[0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95])
    parser.add_argument("--max-day-grid", nargs="+", type=int, default=[999, 8, 4, 2])
    parser.add_argument("--cooldown-minutes", type=int, default=30)
    parser.add_argument("--clip-return", type=float, default=2.0)
    parser.add_argument("--min-trades", type=int, default=216)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-pf", type=float, default=1.3)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--seed", type=int, default=20260626)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tickers = [str(t).upper() for t in args.tickers]
    deltas = [int(d) for d in args.deltas]
    actions = action_columns(deltas)
    frame = read_frame(Path(args.data), deltas, tickers, [str(m) for m in args.expiry_modes])
    features = feature_columns(frame, args)
    summaries: list[dict] = []
    trades: list[pd.DataFrame] = []
    candidate_grids: list[pd.DataFrame] = []
    for ticker in tickers:
        summary, selected, grid = evaluate_ticker(frame, ticker, features, actions, args)
        summaries.append(summary)
        if not selected.empty:
            selected.to_csv(out_dir / f"selected_trades_{ticker}.csv", index=False)
            trades.append(selected)
        if not grid.empty:
            grid["ticker"] = ticker
            grid.to_csv(out_dir / f"threshold_candidates_{ticker}.csv", index=False)
            candidate_grids.append(grid)
        print(
            f"[ACTION_ROUTER] {ticker} status={summary['status']} "
            f"cfg={summary.get('deploy_config', {}).get('threshold', 'none')}",
            flush=True,
        )
    selected_all = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    if not selected_all.empty:
        selected_all.to_csv(out_dir / "selected_trades_all.csv", index=False)
    if candidate_grids:
        pd.concat(candidate_grids, ignore_index=True).to_csv(out_dir / "threshold_candidates_all.csv", index=False)
    payload = {"args": vars(args), "features": features, "summaries": summaries}
    (out_dir / "metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")

    lines = [
        "# Frozen Event Action Return Router",
        "",
        "One return model is fit per ticker/action from fit months. Threshold/max-day are selected on the select window only, then frozen for test windows.",
        "",
        "| Ticker | Status | Config | Select WR | Select PF | Select MinM | Test1 WR | Test1 PF | Test1 MinM | Test2 WR | Test2 PF | Test2 MinM |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summaries:
        cfg = item.get("deploy_config", {})
        cfg_name = DeployConfig(**cfg).name if cfg else "none"
        sm = item.get("select_metrics", {})
        t1 = item.get("test1_metrics", {})
        t2 = item.get("test2_metrics", {})

        def pct(x: object) -> str:
            try:
                value = float(x)
            except Exception:
                return "nan"
            return "nan" if not np.isfinite(value) else f"{100*value:.1f}%"

        def num(x: object) -> str:
            try:
                value = float(x)
            except Exception:
                return "nan"
            return "nan" if not np.isfinite(value) else f"{value:.3f}"

        lines.append(
            f"| {item['ticker']} | {item['status']} | `{cfg_name}` | "
            f"{pct(sm.get('win_rate'))} | {num(sm.get('profit_factor'))} | {int(sm.get('min_month_trades', 0))} | "
            f"{pct(t1.get('win_rate'))} | {num(t1.get('profit_factor'))} | {int(t1.get('min_month_trades', 0))} | "
            f"{pct(t2.get('win_rate'))} | {num(t2.get('profit_factor'))} | {int(t2.get('min_month_trades', 0))} |"
        )
    lines += ["", "## JSON", "", "```json", json.dumps(payload, indent=2, allow_nan=True), "```", ""]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print((out_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
