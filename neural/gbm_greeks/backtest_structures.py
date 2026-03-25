"""
backtest_structures.py
──────────────────────────────────────────────────────────────────────────────
Backtests ALL market structures defined in market_structure.js against the
training dataset.
Greek mapping (JS field → parquet column):
    IV      → derived from atm_iv vs. session median  (High / Low)
    Gamma   → net_gamma
    Zomma   → net_zomma
    Delta   → net_delta
    Vex     → net_dgex          (Delta-adjusted GEX proxy)
    Vega    → net_vega
    Vomma   → net_vomma
    Speed   → gamma_speed
IV state replicates the JS getIVState() rule-set:
    vix_current < vix_open      → Low
    vix_current > vix_prev_close → High
    else                        → Low  (conservative fallback)
When VIX columns are absent the script falls back to comparing atm_iv against
its session median (same as the legacy code).
Expected direction:
    actionDirection           → target encoding
    BUY / BUY (Transition) / BUY / PIN / BUY / SELL*  →  +1  (bullish)
    SELL / SELL LEAN / SELL / PIN / CHOP->SELL          →  -1  (bearish)
    CHOP / SIDEWAYS GRIND / BINARY / Trade in dir / N/A →   0  (neutral)
    *BUY / SELL and SELL / BUY are ambiguous → excluded from hit-rate calc
     (they still appear in the report with Expected_Dir = 0).
──────────────────────────────────────────────────────────────────────────────
"""
import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path
from datetime import datetime

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parents[2]
sys.path.append(str(PROJECT_ROOT))

# ── Paths ─────────────────────────────────────────────────────────────────────
POSSIBLE_PATHS = [
    PROJECT_ROOT / "training_data" / "training_data_spx_qqq.parquet",
    PROJECT_ROOT / "neural" / "training_data_derived.parquet",
]
DATA_PATH = next((p for p in POSSIBLE_PATHS if p.exists()), POSSIBLE_PATHS[-1])
OUTPUT_DIR = PROJECT_ROOT / "neural" / "gbm_greeks"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Greek column mapping: JS name → parquet column ────────────────────────────
GREEK_MAP = {
    "Gamma":  "net_gamma",
    "Zomma":  "net_zomma",
    "Delta":  "net_delta",
    "Vex":    "net_dgex",
    "Vega":   "net_vega",
    "Vomma":  "net_vomma",
    "Speed":  "gamma_speed",
}

# ── actionDirection → expected target ─────────────────────────────────────────
DIR_TO_TARGET = {
    "BUY":                          +1,
    "BUY (Transition)":             +1,
    "BUY / PIN":                    +1,
    "SELL":                         -1,
    "SELL LEAN":                    -1,
    "SELL / PIN":                   -1,
    "CHOP -> SELL":                 -1,
    "CHOP":                          0,
    "SIDEWAYS GRIND":                0,
    "BINARY":                        0,
    "Trade in direction of the move": 0,
    "N/A":                           0,
    "BUY / SELL":                    0,
    "SELL / BUY":                    0,
}

# ═══════════════════════════════════════════════════════════════════════════════
#  ALL STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════
MARKET_STRUCTURES = [
    {
        "id": 1,  "name": "The Waterfall",
        "condition": {"IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos",
                      "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg"},
        "regime": "Trend Day", "actionDirection": "SELL",
    },
    {
        "id": 2,  "name": "Mean Reversion",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": None,  "Speed": None},
        "regime": "Compression", "actionDirection": "SELL",
    },
    {
        "id": 3,  "name": "The Melt Up (High IV)",
        "condition": {"IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Neg", "Vomma": None,  "Speed": None},
        "regime": "Trend Day", "actionDirection": "BUY",
    },
    {
        "id": 4,  "name": "The Drag",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": None,  "Speed": None},
        "regime": "Compression", "actionDirection": "SELL",
    },
    {
        "id": 5,  "name": "Vol of Vol / Fragile Long Vol",
        "condition": {"IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos"},
        "regime": "Trend Day (Not clean)", "actionDirection": "SELL",
    },
    {
        "id": 6,  "name": "Liquidation",
        "condition": {"IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg",
                      "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": None},
        "regime": "Trend Day", "actionDirection": "SELL",
    },
    {
        "id": 7,  "name": "Pinned Long Vol",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg"},
        "regime": "Transitional", "actionDirection": "BINARY",
    },
    {
        "id": 8,  "name": "Vol-Expansion Pre-Trend",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg"},
        "regime": "Compression", "actionDirection": "SELL",
    },
    {
        "id": 9,  "name": "Directionless Chop - Slight Bid",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg"},
        "regime": "Compression", "actionDirection": "CHOP",
    },
    {
        "id": 10, "name": "Short Bearish Gamma Squeeze",
        "condition": {"IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg",
                      "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg"},
        "regime": "Trend Day", "actionDirection": "SELL",
    },
    {
        "id": 11, "name": "Negative Convexity Vol Unwind (Compression Type)",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg"},
        "regime": "Compression", "actionDirection": "SELL",
    },
    {
        "id": 12, "name": "Short Gamma Squeeze / Negative Convexity Feedback Loop",
        "condition": {"IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg"},
        "regime": "Trend Day (Violent)", "actionDirection": "SELL",
    },
    {
        "id": 13, "name": "The Gamma Trap / Crash-to-Melt Vanna (High Vol Pin)",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos"},
        "regime": "Transitional / Expansion", "actionDirection": "BINARY",
    },
    {
        "id": 14, "name": "The Melt Up (Low IV)",
        "condition": {"IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": None},
        "regime": "Trend Day", "actionDirection": "BUY",
    },
    {
        "id": 15, "name": "The Fade",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Neg", "Vega": "Neg", "Vomma": None,  "Speed": None},
        "regime": "Compression", "actionDirection": "SELL",
    },
    {
        "id": 16, "name": "V Bottom",
        "condition": {"IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos",
                      "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": None},
        "regime": "Trend Day", "actionDirection": "BUY",
    },
    {
        "id": 17, "name": "The Bleed",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos",
                      "Vex": "Neg", "Vega": "Neg", "Vomma": None,  "Speed": None},
        "regime": "Compression", "actionDirection": "SELL",
    },
    {
        "id": 18, "name": "Volatility Mean Reversion Sideways Grind",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": None},
        "regime": "Compression", "actionDirection": "SIDEWAYS GRIND",
    },
    {
        "id": 19, "name": "Volatility Mean Reversion Crush",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": None},
        "regime": "Compression", "actionDirection": "BUY",
    },
    {
        "id": 20, "name": "The Ceiling / The Call Pin",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos",
                      "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg"},
        "regime": "Compression", "actionDirection": "SELL / PIN",
    },
    {
        "id": 21, "name": "High Confidence Grind / PIN",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg"},
        "regime": "Compression", "actionDirection": "BUY / PIN",
    },
    {
        "id": 22, "name": "Vanna-Fueled Melt Up",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg"},
        "regime": "Trend Day", "actionDirection": "BUY",
    },
    {
        "id": 23, "name": "Pre-Breakout Convexity Pocket / Gamma Squeeze",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": None},
        "regime": "Compression", "actionDirection": "BUY",
    },
    {
        "id": 24, "name": "Bear Trend Coiled in a Gamma Pin / Pre-Breakdown Structure",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg"},
        "regime": "Compression", "actionDirection": "CHOP -> SELL",
    },
    {
        "id": 25, "name": "Short Bearish Gamma Squeeze (Extended)",
        "condition": {"IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg",
                      "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg"},
        "regime": "Trend Day", "actionDirection": "SELL",
    },
    {
        "id": 26, "name": "Low IV Positive Gamma Grind (Mean-Reverting Compression)",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Neg", "Vega": "Pos", "Vomma": "Neg", "Speed": "Neg"},
        "regime": "Compression", "actionDirection": "SELL LEAN",
    },
    {
        "id": 27, "name": "Compression Regime with Asymmetric Vol Expansion Payoff",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Neg", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg"},
        "regime": "Compression", "actionDirection": "BUY",
    },
    {
        "id": 28, "name": "Short Gamma Trap / Melt Up",
        "condition": {"IV": "Low", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos"},
        "regime": "Trend Day", "actionDirection": "BUY",
    },
    {
        "id": 29, "name": "Positive Convexity Vanna-Fueled Melt Up / Pre Gamma Squeeze",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos"},
        "regime": "Transition to Expansion", "actionDirection": "BUY (Transition)",
    },
    {
        "id": 30, "name": "The Waterfall Sell Off",
        "condition": {"IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Pos",
                      "Vex": "Neg", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg"},
        "regime": "Trend Day", "actionDirection": "SELL",
    },
    {
        "id": 31, "name": "The Mean Reversion Anchor",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Pos",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos"},
        "regime": "Compression", "actionDirection": "SELL / BUY",
    },
    {
        "id": 32, "name": "Short-Vol Capitulation / The Melt Up",
        "condition": {"IV": "High", "Gamma": "Neg", "Zomma": "Pos", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Neg", "Vomma": "Neg", "Speed": "Neg"},
        "regime": "Trend Day", "actionDirection": "BUY",
    },
    {
        "id": 33, "name": "Orderly Sell Off / Hedged Bear Market",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos"},
        "regime": "Compression", "actionDirection": "SELL",
    },
    {
        "id": 34, "name": "Fragile Vanna-Hollow Melt-Up / Fragile Drift",
        "condition": {"IV": "Low", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos"},
        "regime": "Transitional", "actionDirection": "BUY",
    },
    {
        "id": 35, "name": "Volatility-Capped Slide / The Gamma Trap (in Reverse)",
        "condition": {"IV": "High", "Gamma": "Neg", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos"},
        "regime": "Trend Day (Fading)", "actionDirection": "Trade in direction of the move",
    },
    {
        "id": 36, "name": "Possible Volatility Expansion Engine (If IV Wakes Up)",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Neg"},
        "regime": "Compression", "actionDirection": "BUY / SELL",
    },
    {
        "id": 37, "name": "Orderly Bear Drift / Mean-Reverting Slide",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos"},
        "regime": "Compression", "actionDirection": "BUY / SELL",
    },
    {
        "id": 38, "name": "Vanna-Fueled Melt Up / Expansion",
        "condition": {"IV": "Low", "Gamma": "Pos", "Zomma": "Pos", "Delta": "Pos",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": "Pos"},
        "regime": "Trend Day", "actionDirection": "BUY",
    },
    {
        "id": 39, "name": "Vol Spike with Spot Resilience",
        "condition": {"IV": "High", "Gamma": "Pos", "Zomma": "Neg", "Delta": "Neg",
                      "Vex": "Pos", "Vega": "Pos", "Vomma": "Pos", "Speed": None},
        "regime": "Trend Day", "actionDirection": "BUY",
    },
]

# ── IV state helper ────────────────────────────────────────────────────────────
def build_iv_state(df: pd.DataFrame) -> pd.Series:
    if {"vix_spot", "vix_open", "vix_prev_close"}.issubset(df.columns):
        iv = np.where(
            df["vix_spot"] < df["vix_open"], "Low",
            np.where(df["vix_spot"] > df["vix_prev_close"], "High", "Low")
        )
        return pd.Series(iv, index=df.index)
    if "atm_iv" in df.columns:
        if "date" in df.columns:
            medians = df.groupby("date")["atm_iv"].transform("median")
        else:
            medians = df["atm_iv"].median()
        return pd.Series(
            np.where(df["atm_iv"] > medians, "High", "Low"), index=df.index
        )
    col = next((c for c in df.columns if "iv" in c.lower()), None)
    if col:
        return pd.Series(
            np.where(df[col] > df[col].median(), "High", "Low"), index=df.index
        )
    return pd.Series("Low", index=df.index)


# ── Column availability checker ───────────────────────────────────────────────
def check_available_columns(df: pd.DataFrame) -> dict:
    available = {}
    for js_name, col in GREEK_MAP.items():
        available[js_name] = col if col in df.columns else None
    return available


# ── Single structure backtest ─────────────────────────────────────────────────
def backtest_structure(
    df: pd.DataFrame,
    structure: dict,
    iv_series: pd.Series,
    col_avail: dict,
    min_samples: int = 30,
) -> dict | None:
    cond = structure["condition"]
    mask = pd.Series(True, index=df.index)

    iv_wanted = cond["IV"]
    mask &= iv_series == iv_wanted

    for js_name, wanted in cond.items():
        if js_name == "IV" or wanted is None:
            continue
        col = col_avail.get(js_name)
        if col is None:
            continue
        if wanted == "Pos":
            mask &= df[col] >= 0
        else:
            mask &= df[col] < 0

    sub = df[mask]
    n = len(sub)
    if n < min_samples:
        return None

    expected = DIR_TO_TARGET.get(structure["actionDirection"], 0)
    target = sub["target"]

    hit_rate = (target == expected).mean() if expected != 0 else np.nan
    avg_edge = target.mean()

    pos_sum = target[target > 0].sum()
    neg_sum = abs(target[target < 0].sum())
    pf = pos_sum / neg_sum if neg_sum > 0 else np.inf

    bull_rate = (target == 1).mean()
    bear_rate = (target == -1).mean()
    neut_rate = (target == 0).mean()

    std = target.std()
    edge_ratio = avg_edge / std if std > 0 else np.nan

    return {
        "ID":           structure["id"],
        "Structure":    structure["name"],
        "Regime":       structure["regime"],
        "Direction":    structure["actionDirection"],
        "IV_State":     cond["IV"],
        "Samples":      n,
        "Expected_Dir": expected,
        "Hit_Rate":     round(hit_rate, 4) if not np.isnan(hit_rate) else "N/A",
        "Avg_Edge":     round(avg_edge, 4),
        "Edge_Ratio":   round(edge_ratio, 4) if not np.isnan(edge_ratio) else "N/A",
        "Bull_Rate":    round(bull_rate, 3),
        "Bear_Rate":    round(bear_rate, 3),
        "Neut_Rate":    round(neut_rate, 3),
        "Profit_Factor": round(pf, 2) if pf != np.inf else "∞",
    }


# ── Discovered pattern helpers ────────────────────────────────────────────────
_SIGN_MAP = {"+": "Pos", "-": "Neg"}

def parse_combo(combo_str: str) -> tuple:
    """
    Parse a combo string like:
        'IV=High | Gamma+ | Zomma- | Delta+ | Vex- | Vega+ | Vomma+ | Speed+'
    Returns:
        cond     – dict mapping JS greek name → "Pos"/"Neg"
        iv_state – "High", "Low", or None (wildcard)
    """
    cond = {}
    iv_state = None
    for part in combo_str.split(" | "):
        part = part.strip()
        if part.startswith("IV="):
            val = part[3:].strip()
            iv_state = val if val in ("High", "Low") else None
        elif len(part) >= 2 and part[-1] in _SIGN_MAP:
            js_name = part[:-1].strip()
            if js_name in GREEK_MAP:
                cond[js_name] = _SIGN_MAP[part[-1]]
    return cond, iv_state


def apply_greek_mask(
    df: pd.DataFrame,
    cond: dict,
    iv_state,
    iv_series: pd.Series,
    col_avail: dict,
) -> pd.Series:
    """Build a boolean mask for rows matching cond + iv_state."""
    mask = pd.Series(True, index=df.index)
    if iv_state in ("High", "Low"):
        mask &= iv_series == iv_state
    for js_name, wanted in cond.items():
        col = col_avail.get(js_name)
        if col is None:
            continue
        if wanted == "Pos":
            mask &= df[col] >= 0
        else:
            mask &= df[col] < 0
    return mask


# ── Main ──────────────────────────────────────────────────────────────────────
def run_backtest(min_samples: int = 30) -> None:
    if not DATA_PATH.exists():
        print(f"[!] Data not found at {DATA_PATH}. "
              "Run collect_training_data_spx_qqq.py first.")
        return

    print(f"[*] Loading data from {DATA_PATH} ...")
    df = pd.read_parquet(DATA_PATH)
    if "target" not in df.columns:
        print("[!] 'target' column missing. Aborting.")
        return

    df = df.dropna(subset=["target"])
    df["target"] = df["target"].astype(int)
    print(f"[*] {len(df):,} samples after dropping NaN targets.")

    col_avail = check_available_columns(df)
    print("\n[*] Greek column mapping:")
    for js, col in col_avail.items():
        status = f"✓  {col}" if col else "✗  NOT FOUND (wildcard)"
        print(f"    {js:8s} → {status}")

    missing = [js for js, col in col_avail.items() if col is None]
    if missing:
        print(f"\n    [!] Missing columns treated as wildcards: {missing}\n")

    iv_series = build_iv_state(df)
    print(f"\n[*] IV state distribution:\n{iv_series.value_counts().to_string()}\n")

    # ── Backtest named structures ─────────────────────────────────────────────
    results = []
    no_data = []
    for struct in MARKET_STRUCTURES:
        res = backtest_structure(df, struct, iv_series, col_avail, min_samples)
        if res:
            results.append(res)
        else:
            no_data.append(f"  [id={struct['id']:>2}] {struct['name']} "
                           f"— < {min_samples} samples")

    # ── Discovered patterns from interaction_matrix.csv ──────────────────────
    matrix_path = OUTPUT_DIR / "interaction_matrix.csv"
    if matrix_path.exists():
        print("[*] Appending top/bottom patterns from interaction_matrix.csv ...")
        mat = pd.read_csv(matrix_path)

        # Top-3 bullish (highest Avg_Edge)
        for rank, row in enumerate(mat.head(3).itertuples(), 1):
            cond, iv_state = parse_combo(row.Combination)
            mask = apply_greek_mask(df, cond, iv_state, iv_series, col_avail)
            sub  = df[mask]

            if len(sub) < min_samples:
                print(f"    [!] D-BUL-{rank}: only {len(sub)} samples "
                      f"after IV filter (IV={iv_state}) — skipped")
                continue

            target     = sub["target"]
            hit_rate   = (target == 1).mean()
            avg_edge   = target.mean()
            pos_sum    = target[target > 0].sum()
            neg_sum    = abs(target[target < 0].sum())
            pf         = pos_sum / neg_sum if neg_sum > 0 else np.inf
            std        = target.std()
            edge_ratio = avg_edge / std if std > 0 else np.nan

            results.append({
                "ID":           f"D-BUL-{rank}",
                "Structure":    f"Discovered Bullish #{rank}: {row.Combination[:55]}",
                "Regime":       "Discovered",
                "Direction":    "BUY",
                "IV_State":     iv_state if iv_state else "Any",
                "Samples":      len(sub),
                "Expected_Dir": 1,
                "Hit_Rate":     round(hit_rate, 4),
                "Avg_Edge":     round(avg_edge, 4),
                "Edge_Ratio":   round(edge_ratio, 4) if not np.isnan(edge_ratio) else "N/A",
                "Bull_Rate":    round((target == 1).mean(), 3),
                "Bear_Rate":    round((target == -1).mean(), 3),
                "Neut_Rate":    round((target == 0).mean(), 3),
                "Profit_Factor": round(pf, 2) if pf != np.inf else "∞",
            })

        # Top-3 bearish (lowest Avg_Edge) — sort ascending so rank 1 = most bearish
        for rank, row in enumerate(
            mat.tail(3).sort_values("Avg_Edge").itertuples(), 1
        ):
            cond, iv_state = parse_combo(row.Combination)
            mask = apply_greek_mask(df, cond, iv_state, iv_series, col_avail)
            sub  = df[mask]

            if len(sub) < min_samples:
                print(f"    [!] D-BEA-{rank}: only {len(sub)} samples "
                      f"after IV filter (IV={iv_state}) — skipped")
                continue

            target     = sub["target"]
            hit_rate   = (target == -1).mean()
            avg_edge   = target.mean()
            pos_sum    = target[target > 0].sum()
            neg_sum    = abs(target[target < 0].sum())
            pf         = pos_sum / neg_sum if neg_sum > 0 else np.inf
            std        = target.std()
            edge_ratio = avg_edge / std if std > 0 else np.nan

            results.append({
                "ID":           f"D-BEA-{rank}",
                "Structure":    f"Discovered Bearish #{rank}: {row.Combination[:55]}",
                "Regime":       "Discovered",
                "Direction":    "SELL",
                "IV_State":     iv_state if iv_state else "Any",
                "Samples":      len(sub),
                "Expected_Dir": -1,
                "Hit_Rate":     round(hit_rate, 4),
                "Avg_Edge":     round(avg_edge, 4),
                "Edge_Ratio":   round(edge_ratio, 4) if not np.isnan(edge_ratio) else "N/A",
                "Bull_Rate":    round((target == 1).mean(), 3),
                "Bear_Rate":    round((target == -1).mean(), 3),
                "Neut_Rate":    round((target == 0).mean(), 3),
                "Profit_Factor": round(pf, 2) if pf != np.inf else "∞",
            })

    # ── Report ────────────────────────────────────────────────────────────────
    if not results:
        print("[!] No structures had enough samples. Check min_samples or data columns.")
        return

    report = pd.DataFrame(results).sort_values("Avg_Edge", ascending=False)

    print("\n" + "=" * 110)
    print("MARKET STRUCTURE BACKTEST REPORT — ALL 39 STRUCTURES")
    print("=" * 110)
    print(report.to_string(index=False))

    if no_data:
        print(f"\n[!] {len(no_data)} structures below {min_samples}-sample threshold:")
        print("\n".join(no_data))

    out_csv = OUTPUT_DIR / "backtest_report.csv"
    report.to_csv(out_csv, index=False)
    print(f"\n[*] Full report saved → {out_csv}")

    # ── Summary by regime ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY BY REGIME")
    print("=" * 60)
    regime_groups = {
        "Trend Day":    report[report["Regime"].str.contains("Trend",        na=False)],
        "Compression":  report[report["Regime"].str.contains("Compression",  na=False)],
        "Transitional": report[report["Regime"].str.contains("Transitional", na=False)],
        "Expansion":    report[report["Regime"].str.contains("Expansion",    na=False)],
    }
    for regime, grp in regime_groups.items():
        if grp.empty:
            continue
        hit_num  = pd.to_numeric(grp["Hit_Rate"], errors="coerce")
        edge_num = pd.to_numeric(grp["Avg_Edge"], errors="coerce")
        print(f"\n  {regime} ({len(grp)} structures):")
        print(f"    Avg Edge:     {edge_num.mean():.4f}")
        print(f"    Avg Hit Rate: {hit_num.mean():.3f}")
        print(f"    Top:          {grp.iloc[0]['Structure'][:55]}")

    # ── Summary by IV state ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY BY IV STATE")
    print("=" * 60)
    for iv_state in ["High", "Low", "Any"]:
        grp = report[report["IV_State"] == iv_state]
        if grp.empty:
            continue
        edge_num = pd.to_numeric(grp["Avg_Edge"], errors="coerce")
        print(f"\n  IV={iv_state} ({len(grp)} structures):")
        print(f"    Avg Edge:     {edge_num.mean():.4f}")
        best = grp.loc[edge_num.idxmax()]
        print(f"    Best:         [{best['ID']}] {best['Structure'][:50]}")

    print(f"\n[*] Backtest complete.  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backtest all market structures")
    parser.add_argument("--min-samples", type=int, default=30,
                        help="Minimum samples required per structure (default: 30)")
    args = parser.parse_args()
    run_backtest(min_samples=args.min_samples)