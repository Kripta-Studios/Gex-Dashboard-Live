from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .walkforward_event_option_gate import metrics
else:
    from walkforward_event_option_gate import metrics


ARMS = ("return", "win")
TICKERS = ("SPXW", "QQQ", "SPY")
BUCKETS = {"SPXW": 25, "QQQ": 35, "SPY": 35}
MONTHS = ["202601", "202602", "202603", "202604", "202605"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _months(value: object) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def load_cell(root: Path, arm: str, ticker: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    cell = root / arm / ticker
    trades_path = cell / "event_option_profile_trades.csv"
    folds_path = cell / "selected_folds.csv"
    metrics_path = cell / "metrics.json"
    if not folds_path.exists() or not metrics_path.exists():
        raise FileNotFoundError(f"incomplete ablation cell: {cell}")
    trades = pd.read_csv(trades_path) if trades_path.exists() and trades_path.stat().st_size > 0 else pd.DataFrame()
    folds = pd.read_csv(folds_path, dtype={"month": str})
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    expected_profile = f"target_zero_dte_d{BUCKETS[ticker]:02d}_{arm}"
    observed_profiles = set(folds.loc[folds.get("selected", False).astype(bool), "profile"].astype(str))
    if observed_profiles and observed_profiles != {expected_profile}:
        raise ValueError(f"unexpected profiles for {arm}/{ticker}: {sorted(observed_profiles)}")
    observed_months = sorted(folds["month"].astype(str).unique())
    if observed_months != MONTHS:
        raise ValueError(f"unexpected folds for {arm}/{ticker}: {observed_months}")
    for row in folds.to_dict("records"):
        test_month = str(row["month"])
        prior = _months(row.get("training_months")) + _months(row.get("selection_months"))
        if any(month >= test_month for month in prior):
            raise ValueError(f"non-causal fold {arm}/{ticker}/{test_month}: {prior}")
    args = payload.get("metadata", {}).get("args", {})
    if str(args.get("end_month")) != "202605" or str(args.get("start_month")) != "202601":
        raise ValueError(f"unexpected evaluation window for {arm}/{ticker}")
    if any(str(value).startswith("202606") for value in folds.astype(str).to_numpy().ravel()):
        raise ValueError(f"June 2026 found in folds for {arm}/{ticker}")
    return trades, folds, payload


def ticker_summary(trades: pd.DataFrame) -> dict:
    result = metrics(trades, expected_months=MONTHS)
    if trades.empty:
        result["min_hold_minutes"] = None
        result["all_holds_at_least_30m"] = False
        result["monthly"] = {month: metrics(pd.DataFrame(), expected_months=[month]) for month in MONTHS}
        return result
    work = trades.copy()
    work["month"] = work["month"].astype(str).str.replace(r"\.0$", "", regex=True)
    holds = pd.to_numeric(work["exit_minutes"], errors="coerce")
    result["min_hold_minutes"] = float(holds.min())
    result["all_holds_at_least_30m"] = bool(holds.notna().all() and holds.ge(30.0).all())
    result["monthly"] = {
        month: metrics(work[work["month"].eq(month)], expected_months=[month]) for month in MONTHS
    }
    return result


def passes(summary: dict) -> bool:
    return bool(
        int(summary.get("min_month_trades", 0)) >= 18
        and float(summary.get("win_rate", float("nan"))) >= 0.50
        and float(summary.get("profit_factor", float("nan"))) >= 1.30
        and float(summary.get("positive_month_rate", 0.0)) >= 1.0
        and bool(summary.get("all_holds_at_least_30m"))
    )


def report(payload: dict) -> str:
    lines = [
        "# Exact objective ablation v1 — informe final",
        "",
        "Comparación de un solo factor: regresión del retorno ejecutable frente a probabilidad de win, con bucket y contrato fijos.",
        "",
        "| Arm | Ticker | Trades | WR | PF | PnL (R) | Min/mes | Meses + | Hold min | Gate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for arm in ARMS:
        for ticker in TICKERS:
            row = payload["arms"][arm]["tickers"][ticker]
            hold = "n/a" if row["min_hold_minutes"] is None else f"{row['min_hold_minutes']:.0f}"
            lines.append(
                f"| {arm} | {ticker} | {row['trades']} | {100*row['win_rate']:.2f}% | "
                f"{row['profit_factor']:.3f} | {row['pnl_return']:+.3f} | {row['min_month_trades']} | "
                f"{100*row['positive_month_rate']:.0f}% | {hold} | {row['passes_full_gate']} |"
            )
    lines += [
        "",
        f"- Return arm full gate: `{payload['decision']['return_meets_full_ticker_gate']}`.",
        f"- Win arm full gate: `{payload['decision']['win_meets_full_ticker_gate']}`.",
        f"- Junio de 2026 sellado: `{payload['june_2026_sealed']}`.",
        "- Este resultado no altera ni promociona producción.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze exact return-vs-win objective ablation.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--data", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    data_path = Path(args.data)
    payload: dict = {
        "schema_version": 1,
        "single_factor": "executable_return_regression_vs_win_probability",
        "data": str(data_path),
        "data_sha256": sha256(data_path),
        "months": MONTHS,
        "buckets": BUCKETS,
        "june_2026_sealed": True,
        "production_unchanged": True,
        "arms": {},
    }
    for arm in ARMS:
        arm_trades: list[pd.DataFrame] = []
        cells: dict = {}
        for ticker in TICKERS:
            trades, folds, _ = load_cell(root, arm, ticker)
            if not trades.empty:
                arm_trades.append(trades)
            summary = ticker_summary(trades)
            summary["selected_folds"] = int(folds.get("selected", False).astype(bool).sum())
            summary["abstained_folds"] = int((~folds.get("selected", False).astype(bool)).sum())
            summary["passes_full_gate"] = passes(summary)
            cells[ticker] = summary
        combined = pd.concat(arm_trades, ignore_index=True, sort=False) if arm_trades else pd.DataFrame()
        payload["arms"][arm] = {
            "tickers": cells,
            "overall": ticker_summary(combined),
        }
    payload["decision"] = {
        "return_meets_full_ticker_gate": all(
            payload["arms"]["return"]["tickers"][ticker]["passes_full_gate"] for ticker in TICKERS
        ),
        "win_meets_full_ticker_gate": all(
            payload["arms"]["win"]["tickers"][ticker]["passes_full_gate"] for ticker in TICKERS
        ),
        "production_live_ready": False,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps(payload, indent=2, allow_nan=True), encoding="utf-8")
    (root / "REPORT.md").write_text(report(payload), encoding="utf-8")
    print(json.dumps(payload["decision"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
