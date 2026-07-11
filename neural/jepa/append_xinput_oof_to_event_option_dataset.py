from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def normalize_date(value) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else str(value)


def normalize_time(value) -> str:
    text = str(value)
    if len(text) >= 5 and text[2:3] == ":":
        return text[:5]
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text[:5]
    return f"{parsed.hour:02d}:{parsed.minute:02d}"


def mapped_ticker(row: pd.Series) -> str:
    underlying = str(row.get("underlying_ticker", "")).upper()
    ticker = str(row.get("ticker", "")).upper()
    if underlying in {"SPX", "SPY", "QQQ"}:
        return underlying
    if ticker == "SPXW":
        return "SPX"
    return ticker


def main() -> int:
    parser = argparse.ArgumentParser(description="Append causal OOF XInputJEPA features to an event-option dataset.")
    parser.add_argument("--event-data", required=True)
    parser.add_argument("--xinput-features", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-name", default="event_option_dataset.parquet")
    parser.add_argument("--feature-prefix", default="xjepa_", help="Prefix of the columns to extract from the feature parquet.")
    parser.add_argument(
        "--ticker-key-mode",
        choices=["mapped_underlying", "identity"],
        default="mapped_underlying",
        help="Use legacy SPX underlying keys or preserve event tickers such as SPXW for Phys-TD features.",
    )
    args = parser.parse_args()

    event_path = Path(args.event_data)
    xinput_path = Path(args.xinput_features)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    events = pd.read_parquet(event_path)
    xinput = pd.read_parquet(xinput_path)
    feature_cols = [c for c in xinput.columns if str(c).startswith(args.feature_prefix)]
    if not feature_cols:
        raise RuntimeError(f"No {args.feature_prefix}* columns found in {xinput_path}")

    date_col = "trade_date" if "trade_date" in xinput.columns else "date"
    x = xinput[["ticker", date_col, "time", *feature_cols]].copy()
    x["_xinput_ticker"] = x["ticker"].astype(str).str.upper()
    x["_xinput_date"] = x[date_col].map(normalize_date)
    x["_xinput_time"] = x["time"].map(normalize_time)
    x = (
        x.drop(columns=["ticker", date_col, "time"])
        .drop_duplicates(["_xinput_ticker", "_xinput_date", "_xinput_time"], keep="last")
        .reset_index(drop=True)
    )

    work = events.copy()
    if args.ticker_key_mode == "identity":
        work["_xinput_ticker"] = work["ticker"].astype(str).str.upper()
    else:
        work["_xinput_ticker"] = work.apply(mapped_ticker, axis=1)
    work["_xinput_date"] = work["trade_date"].map(normalize_date) if "trade_date" in work.columns else work["date"].map(normalize_date)
    work["_xinput_time"] = work["time"].map(normalize_time)

    merged = work.merge(x, on=["_xinput_ticker", "_xinput_date", "_xinput_time"], how="left", validate="many_to_one")
    matched = merged[feature_cols].notna().any(axis=1)
    for col in feature_cols:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0).astype("float32")
    merged = merged.drop(columns=["_xinput_ticker", "_xinput_date", "_xinput_time"])

    out_path = output_dir / str(args.output_name)
    merged.to_parquet(out_path, index=False)
    (output_dir / "xinput_feature_names.json").write_text(json.dumps(feature_cols, indent=2), encoding="utf-8")
    metadata = {
        "event_data": str(event_path),
        "xinput_features": str(xinput_path),
        "output": str(out_path),
        "rows": int(len(merged)),
        "columns": int(len(merged.columns)),
        "xinput_feature_count": int(len(feature_cols)),
        "feature_prefix": str(args.feature_prefix),
        "ticker_key_mode": str(args.ticker_key_mode),
        "matched_rows": int(matched.sum()),
        "matched_rate": float(matched.mean()) if len(matched) else 0.0,
        "matched_by_ticker": {
            str(ticker): {
                "rows": int(len(group)),
                "matched_rows": int(matched.loc[group.index].sum()),
                "matched_rate": float(matched.loc[group.index].mean()) if len(group) else 0.0,
            }
            for ticker, group in work.groupby(work["ticker"].astype(str).str.upper(), sort=True)
        },
    }
    (output_dir / "append_xinput_oof_metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=True), encoding="utf-8")
    print(json.dumps(metadata, indent=2, allow_nan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
