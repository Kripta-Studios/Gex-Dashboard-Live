"""Post-run failure attribution for WALL_INTERACTION_EXECQUOTE_V1.

This diagnostic never selects a policy. It reconstructs the chosen level and
measures whether the fixed event semantics actually occurred and persisted in
the underlying path. Future prices are labels only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_wall_interaction_execquote_v1 import (
    TICKER_CONFIG,
    add_contiguous_spot_lags,
    build_level_universe,
    join_inputs,
)


HORIZONS = (5, 15, 30, 60, 120)


def profit_factor(values: pd.Series) -> float:
    values = pd.to_numeric(values, errors="coerce").dropna()
    gains = float(values[values > 0.0].sum())
    losses = float(-values[values < 0.0].sum())
    return gains / losses if losses > 0.0 else float("inf")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--trades", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite {output_dir}")

    events = pd.read_parquet(args.events)
    feature_columns = [
        "ticker", "date", "time", "spot_price", "net_gamma", "net_dgex",
        "gamma_regime", "dgex_sticky",
        "dist_to_max_gamma", "dist_to_min_gamma", "dist_to_zero_gamma",
        "dist_to_max_dgex", "dist_to_min_dgex",
        *[name for day in range(1, 6) for name in (f"dist_ib_high_D{day}", f"dist_ib_low_D{day}")],
    ]
    features = pd.read_parquet(args.features, columns=feature_columns)
    joined = add_contiguous_spot_lags(join_inputs(events, features))
    regime = features[["ticker", "date", "time", "net_gamma", "net_dgex", "gamma_regime", "dgex_sticky"]].copy()
    regime["ticker"] = regime["ticker"].replace({"SPX": "SPXW"})
    regime["trade_date"] = regime["date"].astype(str).str.replace(r"\.0$", "", regex=True)
    regime["minute"] = regime["time"].astype(str).str[:2].astype(int) * 60 + regime["time"].astype(str).str[3:5].astype(int)
    joined = joined.merge(
        regime[["ticker", "trade_date", "minute", "net_gamma", "net_dgex", "gamma_regime", "dgex_sticky"]],
        on=["ticker", "trade_date", "minute"], how="left", validate="one_to_one",
    )
    levels = build_level_universe(joined)
    keys = ["ticker", "trade_date", "minute"]
    lookup = joined[keys + ["spot", "spot_lag_5m", "spot_lag_10m", "spot_lag_15m", "net_gamma", "net_dgex", "gamma_regime", "dgex_sticky"]].copy()
    for name, (values, _role) in levels.items():
        lookup[f"level__{name}"] = values.to_numpy(dtype=float)

    trades = pd.read_csv(args.trades, dtype={"trade_date": str})
    trades = trades[trades["arm"].eq("E1")].merge(lookup, on=keys, how="left", validate="one_to_one")
    trades["level_price"] = np.nan
    for name in levels:
        mask = trades["level_name"].eq(name)
        trades.loc[mask, "level_price"] = trades.loc[mask, f"level__{name}"]
    if trades["level_price"].isna().any():
        raise AssertionError("Failed to reconstruct every selected level")
    drop_levels = [column for column in trades if column.startswith("level__")]
    trades = trades.drop(columns=drop_levels)
    trades["distance_bps"] = (trades["spot"] - trades["level_price"]) / trades["spot"] * 10_000.0
    for lag in (5, 10, 15):
        trades[f"distance_lag_{lag}m_bps"] = (
            (trades[f"spot_lag_{lag}m"] - trades["level_price"]) / trades["spot"] * 10_000.0
        )
    trades["pierced_correct_side"] = np.where(
        trades["action"].eq("CALL"),
        trades[["distance_lag_5m_bps", "distance_lag_10m_bps", "distance_lag_15m_bps"]].min(axis=1) <= 0.0,
        trades[["distance_lag_5m_bps", "distance_lag_10m_bps", "distance_lag_15m_bps"]].max(axis=1) >= 0.0,
    )

    path = features[["ticker", "date", "time", "spot_price"]].copy()
    path["ticker"] = path["ticker"].replace({"SPX": "SPXW"})
    path["trade_date"] = path["date"].astype(str).str.replace(r"\.0$", "", regex=True)
    path["minute"] = path["time"].astype(str).str[:2].astype(int) * 60 + path["time"].astype(str).str[3:5].astype(int)
    path = path.sort_values(keys, kind="stable")
    grouped = path.groupby(["ticker", "trade_date"], sort=False, observed=True)
    for horizon in HORIZONS:
        steps = horizon // 5
        future_spot = grouped["spot_price"].shift(-steps)
        future_minute = grouped["minute"].shift(-steps)
        path[f"future_spot_{horizon}m"] = future_spot.where(future_minute.eq(path["minute"] + horizon))
    future_cols = [f"future_spot_{horizon}m" for horizon in HORIZONS]
    trades = trades.merge(path[keys + future_cols], on=keys, how="left", validate="one_to_one")
    direction = np.where(trades["action"].eq("CALL"), 1.0, -1.0)
    for horizon in HORIZONS:
        future = trades[f"future_spot_{horizon}m"]
        trades[f"directional_spot_ret_{horizon}m_bps"] = direction * (future / trades["spot"] - 1.0) * 10_000.0

    rows = []
    eval_trades = trades[trades["month"].astype(int).between(202401, 202512)].copy()
    for keys_value, group in eval_trades.groupby(["ticker", "event_type", "action"], observed=True):
        row = {"ticker": keys_value[0], "event_type": keys_value[1], "action": keys_value[2], "trades": int(len(group))}
        row["option_wr"] = float((group["realized_return"] > 0.0).mean())
        row["option_pf"] = float(profit_factor(group["realized_return"]))
        row["option_pnl"] = float(group["realized_return"].sum())
        row["pierced_rate"] = float(group["pierced_correct_side"].mean())
        for horizon in HORIZONS:
            values = group[f"directional_spot_ret_{horizon}m_bps"].dropna()
            row[f"spot_accuracy_{horizon}m"] = float((values > 0.0).mean()) if len(values) else float("nan")
            row[f"spot_mean_{horizon}m_bps"] = float(values.mean()) if len(values) else float("nan")
        rows.append(row)
    summary = pd.DataFrame(rows).sort_values(["ticker", "event_type", "action"])
    output_dir.mkdir(parents=True)
    summary.to_csv(output_dir / "failure_attribution.csv", index=False)
    trades[[
        "ticker", "trade_date", "minute", "month", "action", "event_type", "level_name",
        "realized_return", "exit_minutes", "distance_bps", "distance_lag_5m_bps",
        "distance_lag_10m_bps", "distance_lag_15m_bps", "pierced_correct_side",
        "gamma_regime", "dgex_sticky", *[f"directional_spot_ret_{horizon}m_bps" for horizon in HORIZONS],
    ]].to_csv(output_dir / "diagnostic_trades.csv", index=False)
    payload = {
        "rows": int(len(trades)),
        "evaluation_rows": int(len(eval_trades)),
        "contains_2026": bool(trades["trade_date"].str.startswith("2026").any()),
        "policy_selected": False,
        "production_modified": False,
    }
    (output_dir / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
