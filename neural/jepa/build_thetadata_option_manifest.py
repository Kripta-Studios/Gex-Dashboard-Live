from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


FILE_RE = re.compile(r"^(?P<ticker>.+)_(?P<expiration>\d{8})_(?P<trade_date>\d{8})_(?P<kind>greeks|iv|ohlc|oi)\.parquet$")


def normalize_yyyymmdd(value: str | None) -> str:
    if value is None:
        return ""
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else ""


def parse_file(path: Path) -> dict | None:
    match = FILE_RE.match(path.name)
    if not match:
        return None
    values = match.groupdict()
    values["path"] = str(path)
    return values


def underlying_ticker_for(ticker: str) -> str:
    return "SPXW" if str(ticker).upper() == "SPX" else str(ticker).upper()


def classify_expiration(trade_date: str, expiration: str) -> tuple[int, str]:
    trade_dt = pd.to_datetime(trade_date, format="%Y%m%d")
    exp_dt = pd.to_datetime(expiration, format="%Y%m%d")
    dte = int((exp_dt - trade_dt).days)
    if dte == 0:
        return dte, "zero_dte"
    if 0 < dte <= 7:
        return dte, "front_weekly"
    if dte > 7:
        return dte, "longer_dated"
    return dte, "expired_or_invalid"


def build_for_ticker(theta_root: Path, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    ticker = str(ticker).upper()
    option_root = theta_root / "data_options" / ticker
    greeks_root = option_root / "greeks"
    if not greeks_root.exists():
        return pd.DataFrame()

    records: list[dict] = []
    for greeks_path in sorted(greeks_root.rglob("*_greeks.parquet")):
        parsed = parse_file(greeks_path)
        if parsed is None:
            continue
        trade_date = normalize_yyyymmdd(parsed["trade_date"])
        expiration = normalize_yyyymmdd(parsed["expiration"])
        if start_date and trade_date < start_date:
            continue
        if end_date and trade_date > end_date:
            continue
        dte_days, expiry_mode = classify_expiration(trade_date, expiration)
        year, month = trade_date[:4], trade_date[4:6]
        stem_prefix = f"{ticker}_{expiration}_{trade_date}"
        paths = {
            "greeks_path": greeks_path,
            "iv_path": option_root / "iv" / year / month / f"{stem_prefix}_iv.parquet",
            "ohlc_path": option_root / "ohlc" / year / month / f"{stem_prefix}_ohlc.parquet",
            "oi_path": option_root / "oi" / year / month / f"{stem_prefix}_oi.parquet",
        }
        und_ticker = underlying_ticker_for(ticker)
        underlying_path = theta_root / "data_underlying_derived" / und_ticker / year / month / f"{und_ticker}_{trade_date}.parquet"
        records.append(
            {
                "ticker": ticker,
                "underlying_ticker": und_ticker,
                "trade_date": trade_date,
                "expiration": expiration,
                "dte_days": dte_days,
                "expiry_mode": expiry_mode,
                "has_greeks": True,
                "has_iv": paths["iv_path"].exists(),
                "has_ohlc": paths["ohlc_path"].exists(),
                "has_oi": paths["oi_path"].exists(),
                "has_underlying": underlying_path.exists(),
                "greeks_path": str(paths["greeks_path"]),
                "iv_path": str(paths["iv_path"]),
                "ohlc_path": str(paths["ohlc_path"]),
                "oi_path": str(paths["oi_path"]),
                "underlying_path": str(underlying_path),
            }
        )
    return pd.DataFrame(records)


def summarize(manifest: pd.DataFrame) -> dict:
    if manifest.empty:
        return {"rows": 0}
    rows: dict = {
        "rows": int(len(manifest)),
        "tickers": sorted(manifest["ticker"].unique().tolist()),
        "date_min": str(manifest["trade_date"].min()),
        "date_max": str(manifest["trade_date"].max()),
        "by_expiry_mode": manifest["expiry_mode"].value_counts().sort_index().astype(int).to_dict(),
        "complete_rows": int(
            (
                manifest["has_greeks"]
                & manifest["has_iv"]
                & manifest["has_ohlc"]
                & manifest["has_oi"]
                & manifest["has_underlying"]
            ).sum()
        ),
    }
    by_ticker = {}
    for ticker, frame in manifest.groupby("ticker", sort=True):
        complete = frame["has_greeks"] & frame["has_iv"] & frame["has_ohlc"] & frame["has_oi"] & frame["has_underlying"]
        by_ticker[str(ticker)] = {
            "rows": int(len(frame)),
            "complete_rows": int(complete.sum()),
            "date_min": str(frame["trade_date"].min()),
            "date_max": str(frame["trade_date"].max()),
            "expiry_modes": frame["expiry_mode"].value_counts().sort_index().astype(int).to_dict(),
        }
    rows["by_ticker"] = by_ticker
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a ThetaData option/underlying file manifest for multi-ticker JEPA pretraining.")
    parser.add_argument("--theta-root", default=r"D:\ThetaData")
    parser.add_argument("--tickers", nargs="+", default=["SPXW", "SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL", "NFLX", "PLTR"])
    parser.add_argument("--start-date", default="20220101")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    theta_root = Path(args.theta_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    start_date = normalize_yyyymmdd(args.start_date)
    end_date = normalize_yyyymmdd(args.end_date)

    frames = []
    for ticker in [str(t).upper() for t in args.tickers]:
        frame = build_for_ticker(theta_root, ticker, start_date, end_date)
        if not frame.empty:
            frames.append(frame)
        print(f"[MANIFEST] {ticker}: {len(frame):,} rows", flush=True)

    manifest = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not manifest.empty:
        manifest = manifest.sort_values(["ticker", "trade_date", "expiration"]).reset_index(drop=True)
    summary = summarize(manifest)

    manifest_path = output_dir / "thetadata_option_manifest.csv"
    summary_path = output_dir / "SUMMARY.json"
    manifest.to_csv(manifest_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
