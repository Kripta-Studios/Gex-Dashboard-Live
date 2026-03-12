# ThetaData Project Data Structure

This document describes the storage structure and data schemas for the options and underlying datasets used in the MLP (Multi-Layer Perceptron) training pipeline.

---

## Options Data (`data_options/`)

### Directory Structure

The data is partitioned by Ticker, Data Type, and Date (Year/Month) to optimize I/O performance and allow for partial dataset loading during training.

```text
data_options/
└── [TICKER]/                                # e.g., SPXW, VIX, QQQ, SPY
    └── [DATA_TYPE]/                         # ohlc, iv, greeks, or oi
        └── [YYYY]/                          # Year of the Trade Date
            └── [MM]/                        # Month of the Trade Date
                └── TICKER_EXP_TRADE_TYPE.parquet

```

### Data Schema

Sample file: `VIX_20260121_20260102_oi.parquet` (Open Interest for VIX expiring Jan 21, recorded on Jan 02).

| Column | Data Type | Description |
| --- | --- | --- |
| **symbol** | large_string | The underlying ticker symbol (e.g., VIX). |
| **expiration** | large_string | The date the option contract expires (ISO format). |
| **trade_date** | large_string | The date the market activity was recorded (ISO format). |
| **data_type** | large_string | Category of data: `ohlc`, `iv`, `greeks`, or `oi`. |
| **interval_used** | large_string | Time resolution: `1m` (minute bars) or `daily`. |
| **right** | large_string | Option type: `C` (Call) or `P` (Put). |
| **strike** | double | The exercise price of the option contract. |
| **open_interest** | int64 | Total number of outstanding active contracts. |
| **open/high/low/close** | double | (Only in `ohlc`) Price of the option contract. |
| **delta/gamma/theta...** | double | (Only in `greeks`) Risk sensitivity metrics. |
| **implied_vol** | double | (Only in `iv`) Market's forecast of a likely price change. |

---

## Derived Underlying Data (Spot Proxy) (`data_underlying_derived/`)

### Directory Structure

This dataset contains the price of the index or ETF itself, derived from 1-second option quotes to ensure perfect alignment with the options data.

```text
data_underlying_derived/
└── [TICKER]/                                # e.g., SPXW (derived from SPX options)
    └── [YYYY]/                              # Year of the Trade Date
        └── [MM]/                            # Month of the Trade Date
            └── TICKER_YYYYMMDD.parquet      # 1-minute OHLC bars of the underlying

```

### Data Schema

Sample file: `VIX_20260102.parquet` (VIX Index 1-minute bars for January 2, 2026).

| Column | Data Type | Description |
| --- | --- | --- |
| **symbol** | large_string | The underlying ticker symbol. |
| **date** | large_string | Trade date (YYYY-MM-DD). |
| **timestamp** | large_string | Minute start time (ISO format or HH:MM:SS). |
| **open** | double | Underlying price at the start of the minute. |
| **high** | double | Highest underlying price during the minute. |
| **low** | double | Lowest underlying price during the minute. |
| **close** | double | Underlying price at the end of the minute. |
| **tick_count** | int64 | Number of 1-second snapshots used to build the bar. |

---

## MLP Integration Notes

### 1. Feature Engineering (DTE)

To calculate **Days to Expiration (DTE)**, your collector script must subtract `trade_date` from `expiration`.

* **0DTE Strategy:** Filter rows where `trade_date == expiration`.

### 2. Time Alignment

When merging `Options Data` with `Derived Underlying Data`, use a **Left Join** on the `timestamp` column. This ensures that every option price/greek is matched with the exact price of the index at that specific minute.

### 3. Moneyness Calculation

The MLP should receive "Moneyness" as a feature instead of absolute strikes:


### 4. Categorical Encoding

Columns like `right` (C/P) and `symbol` must be One-Hot Encoded or mapped to integers (0, 1) before being fed into the Multi-Layer Perceptron.