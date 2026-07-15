from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


FILE_RE = re.compile(
    r"^(?P<ticker>.+)_(?P<expiration>\d{8})_(?P<trade_date>\d{8})_greeks\.parquet$"
)
TICKERS = ("SPXW", "QQQ", "SPY")
START_DATE = "20220101"
END_DATE = "20251231"
ENTRY_CLOCK = "10:35"
HOLD_SESSIONS = 2
TARGET_DELTA = 0.50

SNAPSHOT_COLUMNS = [
    "right",
    "strike",
    "underlying_price",
    "delta",
    "implied_vol",
    "theta",
    "vega",
    "ask",
    "bid",
    "underlying_timestamp",
]


@dataclass(frozen=True)
class ChainFile:
    ticker: str
    expiration: str
    trade_date: str
    path: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def profit_factor(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    gross_profit = float(numeric[numeric > 0].sum())
    gross_loss = float(-numeric[numeric < 0].sum())
    if gross_loss <= 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def metrics(values: pd.Series) -> dict[str, float | int]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return {
        "trades": int(len(numeric)),
        "win_rate": float((numeric > 0).mean()) if len(numeric) else 0.0,
        "profit_factor": profit_factor(numeric),
        "pnl_r": float(numeric.sum()),
        "mean_return": float(numeric.mean()) if len(numeric) else 0.0,
        "median_return": float(numeric.median()) if len(numeric) else 0.0,
    }


def yyyymmdd(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def inventory(theta_root: Path) -> list[ChainFile]:
    rows: list[ChainFile] = []
    for ticker in TICKERS:
        root = theta_root / "data_options" / ticker / "greeks"
        for path in sorted(root.rglob("*_greeks.parquet")):
            match = FILE_RE.match(path.name)
            if match is None:
                continue
            trade_date = match.group("trade_date")
            if not START_DATE <= trade_date <= END_DATE:
                continue
            rows.append(
                ChainFile(
                    ticker=ticker,
                    expiration=match.group("expiration"),
                    trade_date=trade_date,
                    path=path,
                )
            )
    return rows


def physical_pairs(files: list[ChainFile]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[ChainFile]] = defaultdict(list)
    for row in files:
        grouped[(row.ticker, row.expiration)].append(row)

    pairs: list[dict[str, Any]] = []
    for (ticker, expiration), group in sorted(grouped.items()):
        ordered = sorted(group, key=lambda row: row.trade_date)
        for index, entry in enumerate(ordered):
            dte = (yyyymmdd(expiration) - yyyymmdd(entry.trade_date)).days
            if not 0 < dte <= 7:
                continue
            exit_index = index + HOLD_SESSIONS
            if exit_index >= len(ordered):
                continue
            exit_row = ordered[exit_index]
            if exit_row.trade_date > expiration:
                continue
            pairs.append(
                {
                    "ticker": ticker,
                    "expiration": expiration,
                    "entry_date": entry.trade_date,
                    "exit_date": exit_row.trade_date,
                    "entry_dte_calendar": int(dte),
                    "entry_path": str(entry.path),
                    "exit_path": str(exit_row.path),
                }
            )
    return pairs


def _clock_mask(values: pd.Series) -> pd.Series:
    text = values.astype(str)
    return text.str.slice(11, 16).eq(ENTRY_CLOCK)


@lru_cache(maxsize=None)
def load_snapshot(path_text: str) -> pd.DataFrame:
    frame = pd.read_parquet(path_text, columns=SNAPSHOT_COLUMNS)
    frame = frame.loc[_clock_mask(frame["underlying_timestamp"])].copy()
    if frame.empty:
        return frame
    for column in [
        "strike",
        "underlying_price",
        "delta",
        "implied_vol",
        "theta",
        "vega",
        "ask",
        "bid",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["right"] = frame["right"].astype(str).str.upper().str.strip()
    frame = frame.loc[
        frame["right"].isin(["CALL", "PUT"])
        & np.isfinite(frame["strike"])
        & np.isfinite(frame["underlying_price"])
        & frame["underlying_price"].gt(0)
        & np.isfinite(frame["delta"])
        & np.isfinite(frame["ask"])
        & np.isfinite(frame["bid"])
        & frame["ask"].gt(0)
        & frame["bid"].ge(0)
        & frame["bid"].le(frame["ask"])
    ].copy()
    frame["spread_relative"] = (frame["ask"] - frame["bid"]) / frame["ask"]
    return frame.sort_values(["right", "strike", "spread_relative"]).drop_duplicates(
        ["right", "strike"], keep="first"
    )


def choose_entry(snapshot: pd.DataFrame, right: str) -> pd.Series | None:
    part = snapshot.loc[snapshot["right"].eq(right)].copy()
    if right == "CALL":
        part = part.loc[part["delta"].gt(0)]
    else:
        part = part.loc[part["delta"].lt(0)]
    if part.empty:
        return None
    part["delta_distance"] = (part["delta"].abs() - TARGET_DELTA).abs()
    part = part.sort_values(["delta_distance", "spread_relative", "strike"])
    return part.iloc[0]


def exact_exit(snapshot: pd.DataFrame, right: str, strike: float) -> pd.Series | None:
    part = snapshot.loc[
        snapshot["right"].eq(right) & np.isclose(snapshot["strike"], float(strike), atol=1e-9)
    ]
    if part.empty:
        return None
    return part.sort_values(["spread_relative", "strike"]).iloc[0]


def build_opportunity(pair: dict[str, Any]) -> dict[str, Any] | None:
    entry_snapshot = load_snapshot(pair["entry_path"])
    exit_snapshot = load_snapshot(pair["exit_path"])
    if entry_snapshot.empty or exit_snapshot.empty:
        return None

    output = {key: value for key, value in pair.items() if not key.endswith("_path")}
    for right in ("CALL", "PUT"):
        entry = choose_entry(entry_snapshot, right)
        if entry is None:
            return None
        exit_row = exact_exit(exit_snapshot, right, float(entry["strike"]))
        if exit_row is None:
            return None
        prefix = right.lower()
        entry_ask = float(entry["ask"])
        exit_bid = float(exit_row["bid"])
        output.update(
            {
                f"{prefix}_strike": float(entry["strike"]),
                f"{prefix}_entry_bid": float(entry["bid"]),
                f"{prefix}_entry_ask": entry_ask,
                f"{prefix}_entry_spread_relative": float(entry["spread_relative"]),
                f"{prefix}_entry_delta": float(entry["delta"]),
                f"{prefix}_entry_iv": float(entry["implied_vol"]),
                f"{prefix}_entry_theta": float(entry["theta"]),
                f"{prefix}_entry_vega": float(entry["vega"]),
                f"{prefix}_entry_spot": float(entry["underlying_price"]),
                f"{prefix}_exit_bid": exit_bid,
                f"{prefix}_exit_ask": float(exit_row["ask"]),
                f"{prefix}_exit_delta": float(exit_row["delta"]),
                f"{prefix}_exit_iv": float(exit_row["implied_vol"]),
                f"{prefix}_exit_theta": float(exit_row["theta"]),
                f"{prefix}_exit_vega": float(exit_row["vega"]),
                f"{prefix}_exit_spot": float(exit_row["underlying_price"]),
                f"{prefix}_return": (exit_bid - entry_ask) / entry_ask,
            }
        )
    output["oracle_side"] = (
        "CALL" if float(output["call_return"]) >= float(output["put_return"]) else "PUT"
    )
    output["oracle_return"] = max(float(output["call_return"]), float(output["put_return"]))
    output["month"] = str(output["entry_date"])[:6]
    output["event_id"] = (
        f"{output['ticker']}:{output['entry_date']}:{output['expiration']}:{ENTRY_CLOCK}:H{HOLD_SESSIONS}"
    )
    return output


def non_overlap_subset(opportunities: pd.DataFrame) -> pd.DataFrame:
    selected: list[pd.Series] = []
    for _, ticker_frame in opportunities.groupby("ticker", sort=True):
        open_until = ""
        for _, row in ticker_frame.sort_values(["entry_date", "expiration"]).iterrows():
            if open_until and str(row["entry_date"]) < open_until:
                continue
            selected.append(row)
            open_until = str(row["exit_date"])
    return pd.DataFrame(selected).reset_index(drop=True)


def policy_rows(opportunities: pd.DataFrame) -> pd.DataFrame:
    scheduled = non_overlap_subset(opportunities)
    rows: list[pd.DataFrame] = []
    definitions = [
        ("DAILY_OVERLAP_ORACLE", opportunities, "oracle_return", "oracle_side"),
        ("NON_OVERLAP_ORACLE", scheduled, "oracle_return", "oracle_side"),
        ("ALWAYS_CALL", scheduled, "call_return", None),
        ("ALWAYS_PUT", scheduled, "put_return", None),
    ]
    for policy, source, return_column, side_column in definitions:
        part = source[
            ["event_id", "ticker", "entry_date", "exit_date", "month", return_column]
        ].copy()
        part = part.rename(columns={return_column: "return_r"})
        part["policy"] = policy
        part["side"] = source[side_column].to_numpy() if side_column else policy.removeprefix("ALWAYS_")
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


def summarize_policies(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for (policy, ticker, month), part in trades.groupby(["policy", "ticker", "month"], sort=True):
        monthly_rows.append(
            {"policy": policy, "ticker": ticker, "month": month, **metrics(part["return_r"])}
        )
    monthly = pd.DataFrame(monthly_rows)
    for (policy, ticker), part in trades.groupby(["policy", "ticker"], sort=True):
        row: dict[str, Any] = {"policy": policy, "ticker": ticker, **metrics(part["return_r"])}
        cells = monthly.loc[(monthly["policy"] == policy) & (monthly["ticker"] == ticker)]
        row.update(
            {
                "months": int(len(cells)),
                "minimum_monthly_trades": int(cells["trades"].min()),
                "worst_month_pf": float(cells["profit_factor"].min()),
                "worst_month_wr": float(cells["win_rate"].min()),
                "worst_month_pnl_r": float(cells["pnl_r"].min()),
                "passing_months": int(
                    (
                        cells["profit_factor"].gt(1.30)
                        & cells["win_rate"].gt(0.50)
                        & cells["pnl_r"].gt(0)
                        & cells["trades"].ge(6)
                    ).sum()
                ),
            }
        )
        summary_rows.append(row)
    return monthly, pd.DataFrame(summary_rows)


def concentration(values: pd.Series) -> float:
    positive = pd.to_numeric(values, errors="coerce").dropna()
    positive = positive[positive > 0].sort_values(ascending=False)
    gross = float(positive.sum())
    return float(positive.head(5).sum() / gross) if gross > 0 else float("inf")


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else str(number)
    return value


def write_report(output_dir: Path, summary: dict[str, Any], policy_summary: pd.DataFrame) -> None:
    selected = policy_summary.loc[policy_summary["policy"].eq("NON_OVERLAP_ORACLE")]
    lines = [
        "# WEEKLY_MULTIDAY_ORACLE_V1",
        "",
        f"Status: **{summary['status']}**.",
        "",
        "Entrada 10:35 ET al ask; salida dos sesiones después a las 10:35 ET al bid; "
        "mismo contrato delta 0,50; 2022–2025; 2026 cerrado.",
        "",
        "| Ticker | Trades | WR | PF | PnL R | Min trades/mes | Worst PF | Passing months |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in selected.sort_values("ticker").iterrows():
        lines.append(
            f"| {row['ticker']} | {int(row['trades'])} | {float(row['win_rate']):.2%} | "
            f"{float(row['profit_factor']):.3f} | {float(row['pnl_r']):+.3f} | "
            f"{int(row['minimum_monthly_trades'])} | {float(row['worst_month_pf']):.3f} | "
            f"{int(row['passing_months'])}/{int(row['months'])} |"
        )
    lines.extend(
        [
            "",
            f"Avanza a un único desarrollo causal: `{summary['advance_to_single_weekly_development']}`.",
            "",
            "Los oracles usan el side futuro y no son políticas desplegables.",
        ]
    )
    (output_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the frozen two-session weekly executable oracle.")
    parser.add_argument("--theta-root", default=r"D:\ThetaData")
    parser.add_argument(
        "--output-dir",
        default="research_papers/JEPA/results/_diagnostics/weekly_multiday_oracle_202201_202512_v1",
    )
    args = parser.parse_args()

    theta_root = Path(args.theta_root)
    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)

    files = inventory(theta_root)
    pairs = physical_pairs(files)
    opportunities: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs, start=1):
        row = build_opportunity(pair)
        if row is not None:
            opportunities.append(row)
        if index % 100 == 0 or index == len(pairs):
            print(f"[WEEKLY_ORACLE] {index}/{len(pairs)} executable={len(opportunities)}", flush=True)

    frame = pd.DataFrame(opportunities).sort_values(["ticker", "entry_date", "expiration"])
    trades = policy_rows(frame)
    monthly, policy_summary = summarize_policies(trades)

    coverage_rows: list[dict[str, Any]] = []
    pair_frame = pd.DataFrame(pairs)
    for (ticker, year), physical in pair_frame.groupby(
        ["ticker", pair_frame["entry_date"].str.slice(0, 4)], sort=True
    ):
        executable = frame.loc[
            frame["ticker"].eq(ticker) & frame["entry_date"].str.startswith(str(year))
        ]
        coverage_rows.append(
            {
                "ticker": ticker,
                "year": year,
                "physical_opportunities": int(len(physical)),
                "executable_opportunities": int(len(executable)),
                "coverage": float(len(executable) / len(physical)) if len(physical) else 0.0,
            }
        )
    coverage = pd.DataFrame(coverage_rows)

    scheduled = trades.loc[trades["policy"].eq("NON_OVERLAP_ORACLE")]
    concentrations = {
        ticker: concentration(part["return_r"])
        for ticker, part in scheduled.groupby("ticker", sort=True)
    }
    concentrations["POOLED"] = concentration(scheduled["return_r"])

    oracle_summary = policy_summary.loc[policy_summary["policy"].eq("NON_OVERLAP_ORACLE")]
    monthly_oracle = monthly.loc[monthly["policy"].eq("NON_OVERLAP_ORACLE")]
    expected_cells = int(coverage[["ticker", "year"]].drop_duplicates().shape[0] * 12)
    coverage_pass = bool(not coverage.empty and coverage["coverage"].ge(0.90).all())
    monthly_pass = bool(
        len(monthly_oracle) == expected_cells
        and monthly_oracle["profit_factor"].gt(1.30).all()
        and monthly_oracle["win_rate"].gt(0.50).all()
        and monthly_oracle["pnl_r"].gt(0).all()
        and monthly_oracle["trades"].ge(6).all()
    )
    concentration_pass = bool(all(value <= 0.35 for value in concentrations.values()))
    advance = bool(coverage_pass and monthly_pass and concentration_pass)

    outputs = {
        "opportunities.csv": frame,
        "policy_trades.csv": trades,
        "monthly_metrics.csv": monthly,
        "policy_summary.csv": policy_summary,
        "coverage.csv": coverage,
    }
    file_meta: dict[str, Any] = {}
    for name, data in outputs.items():
        path = output_dir / name
        data.to_csv(path, index=False)
        file_meta[name] = {"rows": int(len(data)), "bytes": path.stat().st_size, "sha256": sha256_file(path)}

    predeclaration = Path("research_papers/JEPA/WEEKLY_MULTIDAY_ORACLE_V1_PREDECLARATION.md")
    summary = {
        "schema": "weekly_multiday_oracle_v1",
        "status": "PASS_ORACLE_FEASIBILITY" if advance else "CLOSED_ORACLE_GATE",
        "advance_to_single_weekly_development": advance,
        "hold_sessions": HOLD_SESSIONS,
        "target_delta": TARGET_DELTA,
        "entry_clock": ENTRY_CLOCK,
        "date_min": START_DATE,
        "date_max": END_DATE,
        "holdout_2026_opened": False,
        "production_modified": False,
        "physical_opportunities": int(len(pairs)),
        "executable_opportunities": int(len(frame)),
        "gates": {
            "coverage_gte_0_90": coverage_pass,
            "all_months_pf_gt_1_30_wr_gt_0_50_pnl_positive_trades_gte_6": monthly_pass,
            "top5_gross_profit_share_lte_0_35": concentration_pass,
        },
        "concentration": concentrations,
        "oracle_policy_summary": oracle_summary.to_dict(orient="records"),
        "predeclaration_sha256": sha256_file(predeclaration),
        "files": file_meta,
    }
    summary_path = output_dir / "SUMMARY.json"
    summary_path.write_text(json.dumps(json_safe(summary), indent=2), encoding="utf-8")
    write_report(output_dir, summary, policy_summary)
    print(json.dumps(json_safe(summary), indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
