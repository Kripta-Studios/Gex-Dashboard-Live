from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neural.jepa.walkforward_event_option_gate import metrics


DEFAULT_RESULT = Path(
    "research_papers/JEPA/results/_diagnostics/"
    "dense_candidate_frozen2025_2026_daily_guard_l4p1_vp0"
)


def month_range(start_month: str, end_month: str) -> list[str]:
    start_year, start_mon = int(start_month[:4]), int(start_month[4:6])
    end_year, end_mon = int(end_month[:4]), int(end_month[4:6])
    out: list[str] = []
    year, mon = start_year, start_mon
    while (year, mon) <= (end_year, end_mon):
        out.append(f"{year:04d}{mon:02d}")
        mon += 1
        if mon == 13:
            year += 1
            mon = 1
    return out


def read_trades(path: Path, months: list[str], tickers: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    trades = pd.read_csv(path, low_memory=False)
    required = {"ticker", "month", "date", "realized_return", "action"}
    missing = sorted(required.difference(trades.columns))
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")
    trades = trades.copy()
    trades["ticker"] = trades["ticker"].astype(str).str.upper()
    trades["month"] = trades["month"].astype(str).str[:6]
    trades["date"] = trades["date"].astype(str)
    trades["realized_return"] = pd.to_numeric(trades["realized_return"], errors="coerce").fillna(0.0)
    return trades[trades["ticker"].isin(tickers) & trades["month"].isin(months)].reset_index(drop=True)


def gate_passed(row: dict[str, Any], args: argparse.Namespace) -> bool:
    return bool(
        int(row.get("min_month_trades", 0)) >= int(args.min_month_trades)
        and float(row.get("win_rate", 0.0)) >= float(args.min_win_rate)
        and float(row.get("profit_factor", 0.0)) >= float(args.min_profit_factor)
        and float(row.get("pnl_return", 0.0)) > 0.0
        and float(row.get("call_rate", 0.0)) >= float(args.min_call_rate)
        and float(row.get("call_rate", 0.0)) <= float(args.max_call_rate)
    )


def wilson_interval(wins: int, n: int, z: float = 1.959963984540054) -> dict[str, float]:
    if n <= 0:
        return {"lower": float("nan"), "upper": float("nan")}
    p = wins / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) / n) + (z * z / (4.0 * n * n))) / denom
    return {"lower": float(max(0.0, center - half)), "upper": float(min(1.0, center + half))}


def binomial_survival(k: int, n: int, p: float) -> float:
    if n <= 0:
        return float("nan")
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    terms: list[float] = []
    log_p = math.log(p)
    log_q = math.log1p(-p)
    for i in range(k, n + 1):
        terms.append(
            math.lgamma(n + 1)
            - math.lgamma(i + 1)
            - math.lgamma(n - i + 1)
            + i * log_p
            + (n - i) * log_q
        )
    m = max(terms)
    return float(math.exp(m) * sum(math.exp(term - m) for term in terms))


def pf_from_returns(ret: np.ndarray) -> float:
    wins = ret[ret > 0.0]
    losses = ret[ret < 0.0]
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    return float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf")


def bootstrap_returns(ret: np.ndarray, iterations: int, seed: int) -> dict[str, Any]:
    if len(ret) <= 0 or iterations <= 0:
        return {
            "iterations": int(iterations),
            "win_rate_p05": float("nan"),
            "win_rate_p50": float("nan"),
            "profit_factor_p05": float("nan"),
            "profit_factor_p50": float("nan"),
            "pnl_return_p05": float("nan"),
            "pnl_return_p50": float("nan"),
        }
    rng = np.random.default_rng(seed)
    wr = np.empty(iterations, dtype=float)
    pf = np.empty(iterations, dtype=float)
    pnl = np.empty(iterations, dtype=float)
    n = len(ret)
    for idx in range(iterations):
        sample = ret[rng.integers(0, n, n)]
        wr[idx] = float((sample > 0.0).mean())
        pf[idx] = pf_from_returns(sample)
        pnl[idx] = float(sample.sum())
    finite_pf = pf[np.isfinite(pf)]
    pf_p05 = float(np.quantile(finite_pf, 0.05)) if len(finite_pf) else float("inf")
    pf_p50 = float(np.quantile(finite_pf, 0.50)) if len(finite_pf) else float("inf")
    return {
        "iterations": int(iterations),
        "win_rate_p05": float(np.quantile(wr, 0.05)),
        "win_rate_p50": float(np.quantile(wr, 0.50)),
        "profit_factor_p05": pf_p05,
        "profit_factor_p50": pf_p50,
        "pnl_return_p05": float(np.quantile(pnl, 0.05)),
        "pnl_return_p50": float(np.quantile(pnl, 0.50)),
    }


def ticker_audit(trades: pd.DataFrame, ticker: str, months: list[str], args: argparse.Namespace, seed: int) -> dict[str, Any]:
    part = trades[trades["ticker"].eq(ticker)].copy()
    observed = metrics(part, months)
    ret = part["realized_return"].astype(float).to_numpy()
    wins = int((ret > 0.0).sum())
    n = int(len(ret))
    ci = wilson_interval(wins, n)
    bootstrap = bootstrap_returns(ret, int(args.bootstrap_iterations), seed)
    lomo: dict[str, Any] = {}
    lomo_passed = True
    for excluded in months:
        eval_months = [month for month in months if month != excluded]
        subset = part[~part["month"].eq(excluded)].copy()
        row = metrics(subset, eval_months)
        row["passed"] = gate_passed(row, args)
        lomo[excluded] = row
        lomo_passed = bool(lomo_passed and row["passed"])

    stress: dict[str, Any] = {}
    stress_passed = True
    for k in [int(args.remove_top_winners)]:
        positives = part[part["realized_return"].astype(float) > 0.0].sort_values("realized_return", ascending=False)
        remove_index = positives.head(max(0, k)).index
        subset = part.drop(index=remove_index).copy()
        row = metrics(subset, months)
        row["removed_positive_trades"] = int(len(remove_index))
        row["removed_positive_return"] = float(positives.head(max(0, k))["realized_return"].sum()) if k > 0 else 0.0
        row["passed"] = gate_passed(row, args)
        stress[f"remove_top_{k}_winners"] = row
        stress_passed = bool(stress_passed and row["passed"])

    bootstrap_margin_passed = bool(
        float(bootstrap["win_rate_p05"]) >= float(args.min_win_rate)
        and float(bootstrap["profit_factor_p05"]) >= float(args.min_profit_factor)
        and float(bootstrap["pnl_return_p05"]) > 0.0
    )
    ci_margin_passed = bool(ci["lower"] >= float(args.min_win_rate))
    p_value = binomial_survival(wins, n, float(args.min_win_rate))
    return {
        "ticker": ticker,
        "observed": observed,
        "observed_gate_passed": gate_passed(observed, args),
        "wins": wins,
        "losses": int((ret < 0.0).sum()),
        "breakeven_or_flat": int((ret == 0.0).sum()),
        "wilson_95_win_rate": ci,
        "wilson_lower_passed": ci_margin_passed,
        "binomial_p_value_vs_min_win_rate": p_value,
        "bootstrap": bootstrap,
        "bootstrap_lower_quantile_passed": bootstrap_margin_passed,
        "leave_one_month_out": lomo,
        "leave_one_month_out_passed": lomo_passed,
        "top_winner_stress": stress,
        "top_winner_stress_passed": stress_passed,
        "issues": [
            issue
            for issue, failed in [
                ("observed gates failed", not gate_passed(observed, args)),
                ("Wilson 95% lower WR is below target", not ci_margin_passed),
                ("bootstrap 5% lower WR/PF/PnL is below target", not bootstrap_margin_passed),
                ("leave-one-month-out stress failed", not lomo_passed),
                ("top-winner removal stress failed", not stress_passed),
            ]
            if failed
        ],
    }


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Dense Candidate Statistical Robustness",
        "",
        f"- Passed: `{payload['passed']}`",
        f"- Result dir: `{payload['result_dir']}`",
        f"- Months: `{', '.join(payload['months'])}`",
        f"- Bootstrap iterations: `{payload['bootstrap_iterations']}`",
        "",
        "## Per Ticker",
        "",
        "| Ticker | Trades | WR | PF | Wilson WR Low | Boot WR p05 | Boot PF p05 | LOMO | Top Winners |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ticker, row in payload["tickers"].items():
        obs = row["observed"]
        lines.append(
            "| {ticker} | {trades} | {wr:.2%} | {pf:.3f} | {wilson:.2%} | {bwr:.2%} | {bpf:.3f} | {lomo} | {stress} |".format(
                ticker=ticker,
                trades=int(obs.get("trades", 0)),
                wr=float(obs.get("win_rate", float("nan"))),
                pf=float(obs.get("profit_factor", float("nan"))),
                wilson=float(row["wilson_95_win_rate"]["lower"]),
                bwr=float(row["bootstrap"]["win_rate_p05"]),
                bpf=float(row["bootstrap"]["profit_factor_p05"]),
                lomo=row["leave_one_month_out_passed"],
                stress=row["top_winner_stress_passed"],
            )
        )
    lines.extend(["", "## Issues", ""])
    if payload["issues"]:
        lines.extend(f"- {issue}" for issue in payload["issues"])
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This audit is a robustness stress test, not a new selection step. It does not change the candidate policy.",
            "Failures mean the causal walk-forward result is statistically thin or concentrated, so it should remain research evidence until more completed forward months and fill evidence exist.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress-test the guarded dense 0DTE candidate for statistical fragility.")
    parser.add_argument("--result-dir", default=str(DEFAULT_RESULT))
    parser.add_argument("--trade-file", default="")
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202604")
    parser.add_argument("--exclude-months", nargs="*", default=[])
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ"])
    parser.add_argument("--min-win-rate", type=float, default=0.45)
    parser.add_argument("--min-profit-factor", type=float, default=1.30)
    parser.add_argument("--min-month-trades", type=int, default=18)
    parser.add_argument("--min-call-rate", type=float, default=0.20)
    parser.add_argument("--max-call-rate", type=float, default=0.80)
    parser.add_argument("--bootstrap-iterations", type=int, default=5000)
    parser.add_argument("--remove-top-winners", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--exit-zero-on-fail", action="store_true")
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    output_dir = Path(args.output_dir) if args.output_dir else result_dir / "statistical_robustness"
    output_dir.mkdir(parents=True, exist_ok=True)
    trade_file = Path(args.trade_file) if args.trade_file else result_dir / "combined_trades.csv"
    excluded_months = {str(month)[:6] for month in args.exclude_months}
    months = [month for month in month_range(str(args.start_month), str(args.end_month)) if month not in excluded_months]
    tickers = [str(ticker).upper() for ticker in args.tickers]
    trades = read_trades(trade_file, months, tickers)

    ticker_rows: dict[str, Any] = {}
    for offset, ticker in enumerate(tickers):
        ticker_rows[ticker] = ticker_audit(trades, ticker, months, args, int(args.seed) + offset)

    issues: list[str] = []
    for ticker, row in ticker_rows.items():
        issues.extend(f"{ticker}: {issue}" for issue in row["issues"])

    observed_passed = all(bool(row["observed_gate_passed"]) for row in ticker_rows.values())
    lomo_passed = all(bool(row["leave_one_month_out_passed"]) for row in ticker_rows.values())
    bootstrap_passed = all(bool(row["bootstrap_lower_quantile_passed"]) for row in ticker_rows.values())
    wilson_passed = all(bool(row["wilson_lower_passed"]) for row in ticker_rows.values())
    top_winner_passed = all(bool(row["top_winner_stress_passed"]) for row in ticker_rows.values())
    payload = {
        "schema_version": 1,
        "audit": "dense_candidate_statistical_robustness",
        "passed": bool(observed_passed and lomo_passed and bootstrap_passed and wilson_passed and top_winner_passed),
        "result_dir": str(result_dir),
        "trade_file": str(trade_file),
        "months": months,
        "excluded_months": sorted(excluded_months),
        "tickers_requested": tickers,
        "bootstrap_iterations": int(args.bootstrap_iterations),
        "remove_top_winners": int(args.remove_top_winners),
        "thresholds": {
            "min_win_rate": float(args.min_win_rate),
            "min_profit_factor": float(args.min_profit_factor),
            "min_month_trades": int(args.min_month_trades),
            "min_call_rate": float(args.min_call_rate),
            "max_call_rate": float(args.max_call_rate),
        },
        "checks": {
            "observed_gate_passed": bool(observed_passed),
            "leave_one_month_out_passed": bool(lomo_passed),
            "bootstrap_lower_quantile_passed": bool(bootstrap_passed),
            "wilson_lower_passed": bool(wilson_passed),
            "top_winner_stress_passed": bool(top_winner_passed),
        },
        "tickers": ticker_rows,
        "issues": issues,
        "note": (
            "This is a robustness stress test for the already selected guarded candidate. "
            "It is not used for model selection and should not be treated as new walk-forward evidence."
        ),
    }
    (output_dir / "statistical_robustness.json").write_text(
        json.dumps(payload, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    write_report(output_dir / "STATISTICAL_ROBUSTNESS.md", payload)
    print(json.dumps(payload, indent=2, allow_nan=True))
    return 0 if payload["passed"] or args.exit_zero_on_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
