from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def recalc_prefix(frame: pd.DataFrame, prefix: str, risk_capital: float) -> None:
    pct_col = f"{prefix}_pnl_pct"
    pnl_col = f"{prefix}_pnl_dollars"
    ret_col = f"{prefix}_return_on_risk"
    if pct_col not in frame.columns:
        return
    pnl = (
        frame[pct_col].astype(float)
        * frame["entry_premium"].astype(float)
        * 100.0
        * frame["contracts"].astype(int)
    )
    frame[pnl_col] = pnl.astype(float)
    frame[ret_col] = (pnl / float(risk_capital)).astype(float)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recalculate option candidate contracts/PnL for a different risk capital.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--risk-capital", type=float, required=True)
    args = parser.parse_args()

    risk_capital = float(args.risk_capital)
    if risk_capital <= 0.0:
        raise ValueError("--risk-capital must be positive")

    frame = pd.read_parquet(args.input)
    entry_cost_one = frame["entry_premium"].astype(float) * 100.0
    contracts = np.floor(risk_capital / entry_cost_one.replace(0.0, np.nan)).fillna(0.0).astype(int)
    contracts = contracts.clip(lower=1)
    frame["contracts"] = contracts.astype(int)
    frame["entry_cost_dollars"] = (frame["entry_premium"].astype(float) * 100.0 * frame["contracts"].astype(int)).astype(float)
    for prefix in ("rule", "hold180", "oracle"):
        recalc_prefix(frame, prefix, risk_capital)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    summary = {
        "input": str(args.input),
        "output": str(output),
        "risk_capital": risk_capital,
        "rows": int(len(frame)),
        "contracts": {
            "min": int(frame["contracts"].min()),
            "median": float(frame["contracts"].median()),
            "max": int(frame["contracts"].max()),
        },
        "entry_cost_dollars": {
            "median": float(frame["entry_cost_dollars"].median()),
            "p95": float(frame["entry_cost_dollars"].quantile(0.95)),
            "max": float(frame["entry_cost_dollars"].max()),
        },
    }
    (output.parent / f"{output.stem}_risk_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
