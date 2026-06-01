from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def _time_plus_minutes(value: object, minutes: int) -> str:
    text = str(value)[:5]
    try:
        hour, minute = [int(part) for part in text.split(":")]
    except Exception:
        return text
    total = hour * 60 + minute + int(minutes)
    return f"{total // 60:02d}:{total % 60:02d}"


def _direction(series: pd.Series) -> pd.Series:
    if "direction" in series.index:
        return pd.Series([series["direction"]])
    if "side" in series.index:
        return pd.Series([series["side"]])
    return pd.Series([""])


def _strike_bucket(delta: float) -> str:
    d = abs(float(delta)) if np.isfinite(delta) else 0.0
    if d <= 0.10:
        return "deep_otm"
    if d <= 0.20:
        return "otm_far"
    if d <= 0.30:
        return "otm_near"
    if d <= 0.40:
        return "otm_light"
    if d <= 0.50:
        return "atm"
    if d <= 0.60:
        return "itm_light"
    return "itm"


def _add_balance(df: pd.DataFrame, base_balance: float) -> pd.DataFrame:
    out = df.copy()
    out["balance"] = float(base_balance) + out["pnl_dollars"].astype(float).cumsum()
    return out


def normalize_gbt_jepa_trades(path: Path, base_balance: float, notional: float) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        return df
    out = pd.DataFrame()
    out["date"] = df["date"].astype(str)
    out["entry_time"] = df.get("entry_time", df.get("time", "")).astype(str)
    out["hold_minutes"] = df.get("hold_minutes", pd.Series(180, index=df.index)).astype(int)
    out["exit_time"] = [
        _time_plus_minutes(t, h) for t, h in zip(out["entry_time"], out["hold_minutes"])
    ]
    out["ticker"] = df["ticker"].astype(str)
    out["direction"] = df.get("direction", df.get("side", "")).astype(str)
    out["entry_price"] = df.get("entry_price", df.get("spot_price", 0.0)).astype(float)
    if "exit_price" in df.columns:
        out["exit_price"] = df["exit_price"].astype(float)
    elif "future_return_bps" in df.columns:
        out["exit_price"] = out["entry_price"] * (1.0 + df["future_return_bps"].astype(float) / 10000.0)
    else:
        out["exit_price"] = 0.0
    out["pnl_dollars"] = df["pnl_dollars"].astype(float)
    if "pnl_pct" in df.columns:
        out["pnl_pct"] = df["pnl_pct"].astype(float)
    elif "net_bps" in df.columns:
        out["pnl_pct"] = df["net_bps"].astype(float) / 10000.0
    else:
        out["pnl_pct"] = out["pnl_dollars"] / float(notional)
    out["exit_reason"] = df.get("exit_reason", pd.Series("max_time_180m", index=df.index)).astype(str)
    out["confidence"] = df.get("confidence", df.get("jepa180_confidence", np.nan))
    out["contracts"] = df.get("contracts", pd.Series(1, index=df.index)).astype(int)
    out["source_model"] = "base_jepa_180m"
    return _add_balance(out.sort_values(["date", "entry_time", "ticker"]).reset_index(drop=True), base_balance)


def normalize_option_trades(
    path: Path,
    base_balance: float,
    candidate_labels: Path | None,
) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        return df

    candidate_cols = ["candidate_id", "spot_price"]
    if candidate_labels and candidate_labels.exists() and "candidate_id" in df.columns:
        candidates = pd.read_parquet(candidate_labels, columns=candidate_cols)
        df = df.merge(candidates, on="candidate_id", how="left", suffixes=("", "_candidate"))

    out = pd.DataFrame()
    out["date"] = df["date"].astype(str)
    out["entry_time"] = df.get("entry_time", df.get("time", "")).astype(str)
    out["exit_time"] = df.get("exit_time", "").astype(str)
    out["ticker"] = df["ticker"].astype(str)
    out["direction"] = df.get("direction", df.get("side", "")).astype(str)
    out["entry_price"] = df.get("entry_price", df.get("spot_price", 0.0)).fillna(0.0).astype(float)
    out["exit_price"] = df.get("exit_price", pd.Series(0.0, index=df.index)).fillna(0.0).astype(float)
    out["actual_strike"] = df.get("actual_strike", pd.Series(np.nan, index=df.index)).astype(float)
    out["entry_premium"] = df.get("entry_premium", pd.Series(0.0, index=df.index)).astype(float)
    out["pnl_pct"] = df["pnl_pct"].astype(float)
    if "exit_premium" in df.columns:
        out["exit_premium"] = df["exit_premium"].astype(float)
    else:
        out["exit_premium"] = out["entry_premium"] * (1.0 + out["pnl_pct"])
    out["pnl_dollars"] = df["pnl_dollars"].astype(float)
    out["hold_minutes"] = df["hold_minutes"].astype(int)
    out["exit_reason"] = df.get("exit_reason", "").astype(str)
    out["delta_target"] = df.get("delta_target", pd.Series(np.nan, index=df.index)).astype(float)
    out["actual_delta"] = df.get("actual_delta", df.get("actual_delta_abs", np.nan))
    out["actual_iv"] = df.get("actual_iv", pd.Series(np.nan, index=df.index))
    out["contracts"] = df.get("contracts", pd.Series(1, index=df.index)).fillna(1).astype(int)
    out["strike_bucket"] = [
        _strike_bucket(delta) for delta in out["delta_target"].astype(float).fillna(0.0)
    ]
    out["source_model"] = df.get("policy", pd.Series(path.stem, index=df.index)).astype(str)
    return _add_balance(out.sort_values(["date", "entry_time", "ticker"]).reset_index(drop=True), base_balance)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export JEPA backtests to visualizer-compatible CSVs.")
    parser.add_argument("--gbt-jepa-trades", required=True)
    parser.add_argument("--option-value-trades", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--label", default="jepa")
    parser.add_argument("--candidate-labels", default="")
    parser.add_argument("--base-balance", type=float, default=10000.0)
    parser.add_argument("--notional", type=float, default=100000.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in args.label)

    gbt_df = normalize_gbt_jepa_trades(Path(args.gbt_jepa_trades), args.base_balance, args.notional)
    option_df = normalize_option_trades(
        Path(args.option_value_trades),
        args.base_balance,
        Path(args.candidate_labels) if args.candidate_labels else None,
    )

    gbt_path = output_dir / f"gbt_only_{safe_label}_base_jepa_180m_{ts}.csv"
    option_path = output_dir / f"gbt_rl_{safe_label}_option_value_jepa_{ts}.csv"
    manifest_path = output_dir / f"manifest_{safe_label}_{ts}.json"
    latest_manifest_path = output_dir / "latest_manifest.json"

    gbt_df.to_csv(gbt_path, index=False)
    option_df.to_csv(option_path, index=False)
    manifest = {
        "gbt_file": str(gbt_path),
        "rl_file": str(option_path),
        "gbt_rows": int(len(gbt_df)),
        "rl_rows": int(len(option_df)),
        "source_gbt_jepa_trades": str(Path(args.gbt_jepa_trades)),
        "source_option_value_trades": str(Path(args.option_value_trades)),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    latest_manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
