from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FixedProfile:
    ticker: str
    delta_target: float
    max_minutes_to_close: float
    feature: str
    op: str
    threshold: float

    @property
    def name(self) -> str:
        time_part = "alltime" if self.max_minutes_to_close >= 9999 else f"mtc_le_{self.max_minutes_to_close:.0f}"
        return f"{self.ticker}_d{self.delta_target:.2f}_{time_part}_{self.feature}_{self.op}_{self.threshold:.5g}"


def parse_profile(text: str) -> FixedProfile:
    parts = str(text).split(":")
    if len(parts) != 6:
        raise ValueError("Profile must be TICKER:DELTA:MAX_MTC:FEATURE:le|ge:THRESHOLD")
    op = parts[4].lower()
    if op not in {"le", "ge"}:
        raise ValueError("Profile op must be le or ge")
    return FixedProfile(
        ticker=parts[0].upper(),
        delta_target=float(parts[1]),
        max_minutes_to_close=float(parts[2]),
        feature=parts[3],
        op="<=" if op == "le" else ">=",
        threshold=float(parts[5]),
    )


def month_list(start_month: str, end_month: str) -> list[str]:
    y = int(str(start_month)[:4])
    m = int(str(start_month)[4:6])
    end = int(str(end_month))
    out: list[str] = []
    while y * 100 + m <= end:
        out.append(f"{y:04d}{m:02d}")
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def normalize(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["date"] = frame["date"].astype(str).str.replace("-", "", regex=False).str[:8]
    frame["month"] = frame["date"].str[:6]
    frame["side"] = frame["side"].astype(str).str.upper()
    return frame.sort_values(["ticker", "date", "time", "signal_id", "candidate_id"]).reset_index(drop=True)


def select_profile(frame: pd.DataFrame, profile: FixedProfile) -> pd.DataFrame:
    selected = frame[
        frame["ticker"].eq(profile.ticker)
        & np.isclose(frame["delta_target"].astype(float), profile.delta_target)
    ].copy()
    if selected.empty:
        return selected
    if profile.max_minutes_to_close < 9999:
        selected = selected[selected["minutes_to_close"].astype(float) <= profile.max_minutes_to_close].copy()
    values = pd.to_numeric(selected[profile.feature], errors="coerce")
    if profile.op == "<=":
        selected = selected[values <= profile.threshold].copy()
    else:
        selected = selected[values >= profile.threshold].copy()
    if selected.empty:
        return selected
    selected = selected.sort_values(["signal_id", "candidate_id"]).drop_duplicates("signal_id", keep="first")
    selected["deploy_config"] = profile.name
    return selected


def metrics(trades: pd.DataFrame, expected_months: list[str]) -> dict:
    trades = trades[trades["month"].isin(expected_months)].copy() if not trades.empty else trades
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": float("nan"),
            "profit_factor": float("nan"),
            "pnl_dollars": 0.0,
            "return_on_risk": 0.0,
            "max_drawdown": 0.0,
            "long_rate": float("nan"),
            "min_month_trades": 0,
            "positive_month_rate": float("nan"),
            "monthly_counts": {m: 0 for m in expected_months},
            "monthly_pnl": {m: 0.0 for m in expected_months},
        }
    pnl = trades["rule_pnl_dollars"].astype(float)
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    equity = np.cumsum(pnl.to_numpy())
    peak = np.maximum.accumulate(np.insert(equity, 0, 0.0))[1:]
    counts = trades.groupby("month").size().reindex(expected_months, fill_value=0)
    monthly_pnl = trades.groupby("month")["rule_pnl_dollars"].sum().reindex(expected_months, fill_value=0.0)
    return {
        "trades": int(len(trades)),
        "win_rate": float((pnl > 0.0).mean()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0.0 else float("inf"),
        "pnl_dollars": float(pnl.sum()),
        "return_on_risk": float(trades["rule_return_on_risk"].astype(float).sum()),
        "max_drawdown": float((equity - peak).min()) if len(equity) else 0.0,
        "long_rate": float((trades["side"] == "LONG").mean()),
        "min_month_trades": int(counts.min()),
        "positive_month_rate": float((monthly_pnl > 0.0).mean()),
        "monthly_counts": {str(k): int(v) for k, v in counts.to_dict().items()},
        "monthly_pnl": {str(k): float(v) for k, v in monthly_pnl.to_dict().items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate fixed structural option profiles over candidate labels.")
    parser.add_argument("--candidate-labels", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--start-month", default="202601")
    parser.add_argument("--end-month", default="202606")
    parser.add_argument(
        "--profile",
        action="append",
        required=True,
        help="TICKER:DELTA:MAX_MTC:FEATURE:le|ge:THRESHOLD, for example SPX:0.6:9999:net_delta:le:17.445",
    )
    args = parser.parse_args()

    profiles = [parse_profile(text) for text in args.profile]
    months = month_list(args.start_month, args.end_month)
    frame = normalize(Path(args.candidate_labels))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    selected_parts = [select_profile(frame, profile) for profile in profiles]
    selected = pd.concat([part for part in selected_parts if not part.empty], ignore_index=True) if selected_parts else pd.DataFrame()
    if not selected.empty:
        selected = selected[selected["month"].isin(months)].sort_values(["date", "time", "ticker"]).reset_index(drop=True)
        selected.to_csv(out_dir / "selected_trades.csv", index=False)

    summary = {
        "args": vars(args),
        "profiles": [asdict(p) | {"name": p.name} for p in profiles],
        "overall": metrics(selected, months),
        "per_ticker": {
            ticker: metrics(part, months)
            for ticker, part in selected.groupby("ticker", sort=True)
        } if not selected.empty else {},
    }
    (out_dir / "metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    lines = [
        "# Fixed Structural Option Profiles",
        "",
        "```json",
        json.dumps(summary, indent=2, allow_nan=True),
        "```",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print((out_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
