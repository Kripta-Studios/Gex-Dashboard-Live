"""
Trade Annotator — FastAPI Backend

Serves intraday OHLC, greek levels, IB/Fibonacci, and trade annotations
for the visual trade annotation GUI.

Usage:
    python tools/trade_annotator/server.py --parquet training_data/training_data_spx_qqq.parquet
    OR via: python neural/collect_training_data_spx_qqq.py --gui --output training_data_spx_qqq.parquet
"""

import os
import sys
import json
import argparse
import webbrowser
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, time as dt_time
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# ── Project paths ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "neural"))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass

def get_env_path(key: str, default: str) -> str:
    value = os.getenv(key, default)
    if value.startswith('"') and value.endswith('"'): value = value[1:-1]
    if value.startswith("'") and value.endswith("'"): value = value[1:-1]
    return value.strip()

THETADATA_DIR = get_env_path("THETADATA_DIR", r"D:\ThetaData")
OPTIONS_DIR = os.path.join(THETADATA_DIR, "data_options")
TRAINING_DATA_DIR = os.path.join(PROJECT_ROOT, "training_data")

# Import functions from collect_training_data
from collect_training_data_spx_qqq import (
    load_ohlc_data,
    calculate_fibonacci_levels,
    get_parquet_file,
    get_net_exposures_from_parquet,
    calculate_exact_t,
    R_RATE, Q_DIV,
)
from training_data.stats import calc_dp_cdf_pdf

# ═══════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════

def get_available_dates(ticker: str) -> list[str]:
    """List all dates with OHLC data for a ticker."""
    underlying = "SPXW" if ticker == "SPX" else ticker
    base = Path(THETADATA_DIR) / "data_underlying_derived" / underlying
    if not base.exists():
        return []
    dates = []
    for f in base.rglob(f"{underlying}_*.parquet"):
        try:
            date_str = f.stem.split("_")[1]
            # Validate date format
            datetime.strptime(date_str, "%Y%m%d")
            dates.append(date_str)
        except (ValueError, IndexError):
            continue
    return sorted(set(dates))


def load_greek_levels_for_day(ticker: str, date_str: str) -> dict:
    """
    Load per-minute greek levels (max/min strikes) for a single day.
    Returns dict of level_name -> list of {time, value} points.
    """
    greek_ticker = "SPXW" if ticker == "SPX" else ticker
    year, month = date_str[:4], date_str[4:6]

    daily_file = get_parquet_file(greek_ticker, date_str, is_0dte=True)
    if not daily_file:
        return {}

    oi_file = Path(OPTIONS_DIR) / greek_ticker / "oi" / year / month / daily_file.name.replace("greeks.parquet", "oi.parquet")

    try:
        df_daily = pd.read_parquet(daily_file)
        df_daily["dt"] = pd.to_datetime(df_daily["underlying_timestamp"])
        df_daily = df_daily[
            (df_daily["dt"].dt.time >= dt_time(8, 0)) &
            (df_daily["dt"].dt.time <= dt_time(17, 0))
        ]

        if oi_file.exists():
            df_oi = pd.read_parquet(oi_file)
            df_oi_agg = df_oi.groupby(["strike", "right"]).agg({"open_interest": "max"}).reset_index()
            df_pq_all = pd.merge(df_daily, df_oi_agg, on=["strike", "right"], how="inner")
        else:
            df_pq_all = df_daily.copy()
            df_pq_all["open_interest"] = 1000

        timestamps = sorted(df_pq_all["dt"].unique())
        groups = df_pq_all.groupby("dt")

        # Level name -> list of {time, value}
        level_names = [
            "max_gamma_strike", "min_gamma_strike",
            "max_vanna_strike", "min_vanna_strike",
            "max_dgex_strike", "min_dgex_strike",
            "zero_gamma",
            "max_vega_strike", "min_vega_strike",
            "max_vomma_strike", "min_vomma_strike",
        ]
        levels = {name: [] for name in level_names}

        for ts_np in timestamps:
            ts = pd.to_datetime(ts_np)
            time_key = ts.strftime("%H:%M")

            if ts not in groups.groups:
                continue

            df_pq = groups.get_group(ts).copy()
            if df_pq.empty:
                continue

            # Fix zero underlying prices
            non_zero = df_pq[df_pq["underlying_price"] > 0]["underlying_price"]
            if non_zero.empty:
                continue
            spot = float(non_zero.iloc[0])
            df_pq.loc[df_pq["underlying_price"] <= 0, "underlying_price"] = spot

            df_pq["T"] = calculate_exact_t(ts)

            if "implied_vol" not in df_pq.columns:
                if "implied_volatility" in df_pq.columns:
                    df_pq["implied_vol"] = df_pq["implied_volatility"]
                else:
                    continue

            required = ["strike", "right", "implied_vol", "open_interest", "underlying_price", "T"]
            for col in required:
                if col not in df_pq.columns:
                    break
            else:
                df_pq = df_pq.dropna(subset=required)
                if df_pq.empty:
                    continue

                try:
                    exp = get_net_exposures_from_parquet(df_pq)
                    if exp:
                        for name in level_names:
                            val = exp.get(name, 0)
                            if val and val > 0:
                                levels[name].append({"time": time_key, "value": round(float(val), 2)})
                except Exception:
                    continue

        return levels

    except Exception as e:
        print(f"Error loading greek levels for {ticker} {date_str}: {e}")
        return {}


def load_day_data(ticker: str, date_str: str) -> dict:
    """Load all chart data for one day: candles + IB + Fibonacci + greek levels."""
    # OHLC candles + IB
    ib_data = load_ohlc_data(ticker, date_str)
    if not ib_data:
        raise HTTPException(status_code=404, detail=f"No OHLC data for {ticker} {date_str}")

    ib_high = ib_data["ib_high"]
    ib_low = ib_data["ib_low"]
    series = ib_data["series"]

    # Build OHLC candles from the 1-min data
    # Load raw parquet for proper OHLC
    underlying = "SPXW" if ticker == "SPX" else ticker
    year, month = date_str[:4], date_str[4:6]
    ohlc_path = Path(THETADATA_DIR) / "data_underlying_derived" / underlying / year / month / f"{underlying}_{date_str}.parquet"

    candles = []
    if ohlc_path.exists():
        df = pd.read_parquet(ohlc_path)
        df["dt"] = pd.to_datetime(df["timestamp"])
        df = df[(df["dt"].dt.time >= dt_time(8, 0)) & (df["dt"].dt.time <= dt_time(17, 0))]
        df = df.sort_values("dt")
        for _, row in df.iterrows():
            candles.append({
                "time": row["dt"].strftime("%H:%M"),
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
            })
    else:
        # Fallback: use series prices as close-only candles
        for s in series:
            p = s.get("price", 0)
            candles.append({
                "time": s.get("time", ""),
                "open": p, "high": p, "low": p, "close": p,
            })

    # Fibonacci
    fib = calculate_fibonacci_levels(ib_high, ib_low)

    # Greek levels (time-varying)
    greek_levels = load_greek_levels_for_day(ticker, date_str)

    return {
        "ticker": ticker,
        "date": date_str,
        "candles": candles,
        "ib_high": round(ib_high, 2),
        "ib_low": round(ib_low, 2),
        "fibonacci": {k: round(v, 2) for k, v in fib.items()},
        "levels": greek_levels,
    }


# ═══════════════════════════════════════════════════════════════
# TRADE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

class TradeStore:
    """Manages trades: loads from training parquet, supports add/edit/delete."""

    def __init__(self, parquet_path: str):
        self.parquet_path = parquet_path
        self.df: Optional[pd.DataFrame] = None
        self.manual_trades: list[dict] = []  # Manually added trades
        self.deleted_indices: set[int] = set()  # Indices of deleted original trades
        self._manual_trades_path = parquet_path.replace(".parquet", "_manual_trades.json")
        self._deleted_path = parquet_path.replace(".parquet", "_deleted_indices.json")
        self._load()

    def _load(self):
        """Load training parquet and any saved manual edits."""
        if os.path.exists(self.parquet_path):
            self.df = pd.read_parquet(self.parquet_path)
            print(f"Loaded training data: {len(self.df)} samples from {self.parquet_path}")
        else:
            self.df = pd.DataFrame()
            print(f"Training parquet not found: {self.parquet_path}")

        # Load manual trades
        if os.path.exists(self._manual_trades_path):
            with open(self._manual_trades_path, "r") as f:
                self.manual_trades = json.load(f)
            print(f"Loaded {len(self.manual_trades)} manual trades")

        # Load deleted indices
        if os.path.exists(self._deleted_path):
            with open(self._deleted_path, "r") as f:
                self.deleted_indices = set(json.load(f))
            print(f"Loaded {len(self.deleted_indices)} deleted trade indices")

    def get_trades_for_day(self, ticker: str, date_str: str) -> list[dict]:
        """Get all trades (original + manual, minus deleted) for a specific day."""
        trades = []

        # Original trades from parquet
        if self.df is not None and not self.df.empty:
            mask = (self.df["ticker"] == ticker) & (self.df["date"] == date_str)
            day_df = self.df[mask]

            for idx, row in day_df.iterrows():
                if int(idx) in self.deleted_indices:
                    continue
                target = int(row.get("target", 0))
                if target == 0:
                    continue  # Skip HOLD samples — not trades

                trades.append({
                    "id": f"orig_{idx}",
                    "idx": int(idx),
                    "source": "auto",
                    "ticker": ticker,
                    "date": date_str,
                    "time": str(row.get("time", "")),
                    "spot_price": round(float(row.get("spot_price", 0)), 2),
                    "target": target,
                    "direction": "LONG" if target == 1 else "SHORT",
                    "time_to_target": int(row.get("time_to_target", 0)),
                    "time_to_stop": int(row.get("time_to_stop", 0)),
                    "max_move": round(float(row.get("max_move", 0)), 4),
                })

        # Manual trades
        for i, mt in enumerate(self.manual_trades):
            if mt.get("ticker") == ticker and mt.get("date") == date_str:
                trades.append({
                    "id": f"manual_{i}",
                    "idx": i,
                    "source": "manual",
                    **mt,
                })

        return trades

    def add_manual_trade(self, trade: dict) -> dict:
        """Add a manually annotated trade."""
        self.manual_trades.append(trade)
        self._save_manual()
        idx = len(self.manual_trades) - 1
        return {"id": f"manual_{idx}", "idx": idx, "source": "manual", **trade}

    def delete_trade(self, trade_id: str) -> bool:
        """Delete a trade by its ID."""
        if trade_id.startswith("orig_"):
            idx = int(trade_id.split("_")[1])
            self.deleted_indices.add(idx)
            self._save_deleted()
            return True
        elif trade_id.startswith("manual_"):
            idx = int(trade_id.split("_")[1])
            if 0 <= idx < len(self.manual_trades):
                self.manual_trades.pop(idx)
                self._save_manual()
                return True
        return False

    def update_trade(self, trade_id: str, updates: dict) -> bool:
        """Update a trade's target/direction."""
        if trade_id.startswith("orig_"):
            idx = int(trade_id.split("_")[1])
            if self.df is not None and idx in self.df.index:
                if "target" in updates:
                    self.df.at[idx, "target"] = updates["target"]
                return True
        elif trade_id.startswith("manual_"):
            idx = int(trade_id.split("_")[1])
            if 0 <= idx < len(self.manual_trades):
                self.manual_trades[idx].update(updates)
                self._save_manual()
                return True
        return False

    def save_to_parquet(self) -> str:
        """Save all changes back to the training parquet."""
        if self.df is None or self.df.empty:
            return "No data to save"

        # Remove deleted rows
        if self.deleted_indices:
            valid_deleted = [i for i in self.deleted_indices if i in self.df.index]
            df_clean = self.df.drop(index=valid_deleted)
        else:
            df_clean = self.df.copy()

        # Append manual trades as new rows (with feature columns set to 0)
        if self.manual_trades:
            manual_rows = []
            for mt in self.manual_trades:
                row = {col: 0 for col in df_clean.columns}
                row["ticker"] = mt.get("ticker", "SPX")
                row["date"] = mt.get("date", "")
                row["time"] = mt.get("entry_time", "")
                row["spot_price"] = mt.get("entry_price", 0)
                row["target"] = mt.get("target", 0)
                row["time_to_target"] = mt.get("time_to_target", 0)
                row["time_to_stop"] = mt.get("time_to_stop", 0)
                row["max_move"] = mt.get("max_move", 0)
                manual_rows.append(row)
            df_manual = pd.DataFrame(manual_rows)
            df_final = pd.concat([df_clean, df_manual], ignore_index=True)
        else:
            df_final = df_clean

        # Save
        backup_path = self.parquet_path.replace(".parquet", "_backup.parquet")
        if os.path.exists(self.parquet_path):
            import shutil
            shutil.copy2(self.parquet_path, backup_path)

        df_final.to_parquet(self.parquet_path, index=False)
        msg = f"Saved {len(df_final)} samples to {self.parquet_path} (backup: {backup_path})"
        print(msg)
        return msg

    def get_summary(self) -> dict:
        """Get dataset summary stats."""
        if self.df is None or self.df.empty:
            return {"total": 0, "tickers": [], "dates": 0}

        return {
            "total": len(self.df) - len(self.deleted_indices) + len(self.manual_trades),
            "original": len(self.df),
            "deleted": len(self.deleted_indices),
            "manual": len(self.manual_trades),
            "tickers": self.df["ticker"].unique().tolist() if "ticker" in self.df.columns else [],
            "dates": int(self.df["date"].nunique()) if "date" in self.df.columns else 0,
            "target_distribution": self.df["target"].value_counts().to_dict() if "target" in self.df.columns else {},
        }

    def _save_manual(self):
        with open(self._manual_trades_path, "w") as f:
            json.dump(self.manual_trades, f, indent=2)

    def _save_deleted(self):
        with open(self._deleted_path, "w") as f:
            json.dump(list(self.deleted_indices), f)


# ═══════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════

app = FastAPI(title="Trade Annotator", version="1.0")
trade_store: Optional[TradeStore] = None

# Pydantic models
class NewTrade(BaseModel):
    ticker: str
    date: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    target: int  # 1=LONG, -1=SHORT
    direction: str  # "LONG" or "SHORT"
    time_to_target: int = 0
    time_to_stop: int = 0
    max_move: float = 0

class TradeUpdate(BaseModel):
    target: int = None
    direction: str = None


@app.get("/")
async def index():
    return FileResponse(os.path.join(SCRIPT_DIR, "static", "index.html"))


@app.get("/api/dates/{ticker}")
async def get_dates(ticker: str):
    """List all available trading dates for a ticker."""
    dates = get_available_dates(ticker.upper())
    return {"ticker": ticker.upper(), "dates": dates, "count": len(dates)}


@app.get("/api/day/{ticker}/{date}")
async def get_day_data(ticker: str, date: str):
    """Get OHLC candles + levels for a specific day."""
    try:
        data = load_day_data(ticker.upper(), date)
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trades/{ticker}/{date}")
async def get_trades(ticker: str, date: str):
    """Get all trades for a specific day."""
    if trade_store is None:
        return {"trades": []}
    trades = trade_store.get_trades_for_day(ticker.upper(), date)
    return {"trades": trades}


@app.post("/api/trades")
async def add_trade(trade: NewTrade):
    """Add a new manual trade."""
    if trade_store is None:
        raise HTTPException(status_code=500, detail="Trade store not initialized")
    result = trade_store.add_manual_trade(trade.model_dump())
    return result


@app.delete("/api/trades/{trade_id}")
async def delete_trade(trade_id: str):
    """Delete a trade by ID."""
    if trade_store is None:
        raise HTTPException(status_code=500, detail="Trade store not initialized")
    success = trade_store.delete_trade(trade_id)
    if not success:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"status": "deleted", "id": trade_id}


@app.put("/api/trades/{trade_id}")
async def update_trade(trade_id: str, updates: TradeUpdate):
    """Update a trade's label/direction."""
    if trade_store is None:
        raise HTTPException(status_code=500, detail="Trade store not initialized")
    success = trade_store.update_trade(trade_id, updates.model_dump(exclude_none=True))
    if not success:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"status": "updated", "id": trade_id}


@app.post("/api/save")
async def save_data():
    """Persist all changes to the training parquet."""
    if trade_store is None:
        raise HTTPException(status_code=500, detail="Trade store not initialized")
    msg = trade_store.save_to_parquet()
    return {"status": "saved", "message": msg}


@app.get("/api/summary")
async def get_summary():
    """Get dataset summary stats."""
    if trade_store is None:
        return {"total": 0}
    return trade_store.get_summary()


# Mount static files AFTER API routes
app.mount("/static", StaticFiles(directory=os.path.join(SCRIPT_DIR, "static")), name="static")


# ═══════════════════════════════════════════════════════════════
# LAUNCH
# ═══════════════════════════════════════════════════════════════

def launch_gui(output_path: str = None, port: int = 8501):
    """Launch the trade annotator GUI server."""
    global trade_store

    if output_path is None:
        output_path = os.path.join(TRAINING_DATA_DIR, "training_data_spx_qqq.parquet")

    trade_store = TradeStore(output_path)
    summary = trade_store.get_summary()
    print(f"\n{'='*60}")
    print(f"Trade Annotator GUI")
    print(f"{'='*60}")
    print(f"Training data: {output_path}")
    print(f"Samples: {summary.get('total', 0)} | Tickers: {summary.get('tickers', [])} | Days: {summary.get('dates', 0)}")
    print(f"\nOpening http://localhost:{port} ...")
    print(f"{'='*60}\n")

    webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trade Annotator GUI Server")
    parser.add_argument("--parquet", default=None, help="Path to training parquet file")
    parser.add_argument("--port", type=int, default=8501, help="Server port")
    args = parser.parse_args()
    launch_gui(args.parquet, args.port)
