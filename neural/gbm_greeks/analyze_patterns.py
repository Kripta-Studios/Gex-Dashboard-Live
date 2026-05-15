"""
analyze_patterns.py
──────────────────────────────────────────────────────────────────────────────
Trains a LightGBM model on the training dataset, then:
  1. Ranks all features by GAIN and by SHAP value (if shap is installed).
  2. Highlights the 8 Greeks used by the Market Structure Engine (JS-aligned).
  3. Builds a Greek Interaction Matrix — the same 8 binary axes as the JS
     conditions, producing an automated rule-table equivalent to the 39
     MARKET_STRUCTURES in market_structure.js.
  4. Compares the LightGBM-discovered combinations against the 39 named
     structures, highlighting new patterns not yet in the JS matrix.

Greek column mapping (JS → parquet):
    Gamma  → net_gamma
    Zomma  → net_zomma
    Delta  → net_delta
    Vex    → net_dgex
    Vega   → net_vega
    Vomma  → net_vomma
    Speed  → gamma_speed
    IV     → derived (see backtest_structures.py)
──────────────────────────────────────────────────────────────────────────────
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
import os
import sys
import pickle
import itertools
from datetime import datetime
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parents[2]
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(PROJECT_ROOT / "modules"))

try:
    from market_structures_data import MARKET_STRUCTURES, match_market_structure
except ImportError:
    MARKET_STRUCTURES = []
    def match_market_structure(iv, combo): return []

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False
    print("[!] SHAP not installed — using native feature importance.")

# ── Paths ─────────────────────────────────────────────────────────────────────
POSSIBLE_PATHS = [
    PROJECT_ROOT / "training_data" / "training_data_spx_qqq.parquet",
    PROJECT_ROOT / "neural" / "training_data_derived.parquet",
]
DATA_PATH = next((p for p in POSSIBLE_PATHS if p.exists()), POSSIBLE_PATHS[-1])
OUTPUT_DIR = PROJECT_ROOT / "neural" / "gbm_greeks"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Greek features aligned with market_structure.js ──────────────────────────
# JS name   → parquet column
GREEK_MAP = {
    "Gamma": "net_gamma",
    "Zomma": "net_zomma",
    "Delta": "net_delta",
    "Vex":   "net_dgex",      # Delta-adjusted GEX
    "Vega":  "net_vega",
    "Vomma": "net_vomma",
    "Speed": "gamma_speed",
    # Extra greeks in training data (not in JS conditions but informative)
    "Vanna":   "net_vanna",
    "Charm":   "net_charm",
    "VixGamma": "vix_gamma",
}

# The 8 greeks that appear in JS conditions (in order)
JS_CONDITION_GREEKS = ["Gamma", "Zomma", "Delta", "Vex", "Vega", "Vomma", "Speed"]

# Market structures are now loaded from modules/market_structures_data.py


# ── LGB training configuration ────────────────────────────────────────────────
LGB_PARAMS = {
    "objective":        "multiclass",
    "num_class":        3,
    "metric":           "multi_logloss",
    "verbosity":        -1,
    "boosting_type":    "gbdt",
    "seed":             42,
    "max_depth":        5,
    "num_leaves":       31,
    "learning_rate":    0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq":     5,
}
LGB_ROUNDS    = 1000
EARLY_STOP    = 100
TEST_SIZE     = 0.20
SHAP_SAMPLES  = 1000
MIN_COMBO_N   = 200   # minimum samples per interaction-matrix combo


# ── Data loading ─────────────────────────────────────────────────────────────

def load_and_preprocess():
    print(f"[*] Loading data from {DATA_PATH} ...")
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Training data not found at {DATA_PATH}. "
            "Run collect_training_data_spx_qqq.py first."
        )
    df = pd.read_parquet(DATA_PATH)
    print(f"[*] Raw rows: {len(df):,}")

    if "target" not in df.columns:
        raise ValueError("'target' column missing in dataset.")

    df = df.dropna(subset=["target"])

    try:
        from neural.hybrid_model import FEATURE_COLUMNS
    except ImportError:
        # Fallback: use all numeric columns except target and metadata
        meta_cols = {"target", "date", "time", "ticker", "datetime"}
        FEATURE_COLUMNS = [
            c for c in df.columns
            if c not in meta_cols and pd.api.types.is_numeric_dtype(df[c])
        ]
        print(f"[!] neural.hybrid_model not found — using {len(FEATURE_COLUMNS)} numeric cols.")

    # Keep only available feature columns
    avail = [c for c in FEATURE_COLUMNS if c in df.columns]
    missing_fc = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing_fc:
        print(f"[!] {len(missing_fc)} feature columns absent from parquet (skipped): "
              f"{missing_fc[:8]}{'...' if len(missing_fc) > 8 else ''}")

    X = df[avail].copy()
    y = df["target"].astype(int) + 1  # [-1,0,1] → [0,1,2]

    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    print(f"[*] Features: {len(avail)} | Samples: {len(X):,}")
    print(f"    Target distribution: {dict(df['target'].value_counts().sort_index())}")
    return X, y, avail, df


# ── Model training ────────────────────────────────────────────────────────────

def train_analysis_model(X, y, feature_names):
    print("\n[*] Training LightGBM analysis model ...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=42, stratify=y
    )

    train_ds = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)
    test_ds  = lgb.Dataset(X_test,  label=y_test,  feature_name=feature_names,
                           reference=train_ds)

    model = lgb.train(
        LGB_PARAMS,
        train_ds,
        num_boost_round=LGB_ROUNDS,
        valid_sets=[train_ds, test_ds],
        callbacks=[lgb.early_stopping(stopping_rounds=EARLY_STOP)],
    )

    y_pred = np.argmax(model.predict(X_test), axis=1)
    print("\n" + "=" * 50)
    print("CLASSIFICATION REPORT")
    print("=" * 50)
    print(classification_report(
        y_test, y_pred,
        target_names=["Bearish (-1)", "Neutral (0)", "Bullish (+1)"]
    ))
    return model


# ── Feature importance ────────────────────────────────────────────────────────

def discover_greek_relationships(model, X, feature_names):
    print("[*] Analysing Greek feature importance ...")

    # Native GAIN importance
    gain_imp = pd.DataFrame({
        "feature":    feature_names,
        "gain":       model.feature_importance(importance_type="gain"),
        "split":      model.feature_importance(importance_type="split"),
    }).sort_values("gain", ascending=False)

    print("\nTop 20 Features by GAIN:")
    print(gain_imp.head(20).to_string(index=False))
    gain_imp.to_excel(OUTPUT_DIR / "feature_importance_gain.xlsx", index=False)

    # Highlight JS-aligned Greeks
    js_cols = [v for v in GREEK_MAP.values() if v in gain_imp["feature"].values]
    greek_imp = gain_imp[gain_imp["feature"].isin(js_cols)].copy()
    greek_imp["JS_Name"] = greek_imp["feature"].map(
        {v: k for k, v in GREEK_MAP.items()}
    )
    print("\nJS Greek Feature Importance (GAIN):")
    print(greek_imp[["JS_Name", "feature", "gain", "split"]].to_string(index=False))
    greek_imp.to_excel(OUTPUT_DIR / "greek_importance.xlsx", index=False)

    # SHAP analysis
    if HAS_SHAP:
        print(f"\n[*] Computing SHAP values on {SHAP_SAMPLES} samples ...")
        X_sample = X.sample(min(SHAP_SAMPLES, len(X)), random_state=42)
        explainer  = shap.TreeExplainer(model)
        shap_vals  = explainer.shap_values(X_sample)

        # Normalise output shape across shap versions:
        #   Old API  → list of 3 arrays, each (samples, features)
        #   New API  → single array (samples, features, classes)
        if isinstance(shap_vals, np.ndarray) and shap_vals.ndim == 3:
            # shape: (samples, features, classes)  → transpose to (classes, samples, features)
            shap_vals = [shap_vals[:, :, c] for c in range(shap_vals.shape[2])]
        elif isinstance(shap_vals, np.ndarray) and shap_vals.ndim == 2:
            # Binary fallback — wrap in list
            shap_vals = [shap_vals]

        n_feat = len(feature_names)
        for i, label in enumerate(["Bearish", "Neutral", "Bullish"]):
            if i >= len(shap_vals):
                break
            arr = shap_vals[i]               # (samples, features)
            # Guard: skip if feature dimension doesn't match
            if arr.shape[1] != n_feat:
                print(f"[!] SHAP shape mismatch for {label}: "
                      f"got {arr.shape[1]} features, expected {n_feat}. Skipping.")
                continue
            vals = np.abs(arr).mean(0)       # mean |SHAP| per feature
            shap_imp = pd.DataFrame(
                {"feature": feature_names, "shap_value": vals}
            ).sort_values("shap_value", ascending=False)
            print(f"\nTop 10 SHAP features for {label}:")
            print(shap_imp.head(10).to_string(index=False))
            shap_imp.to_excel(OUTPUT_DIR / f"shap_features_{label.lower()}.xlsx", index=False)
    else:
        print("[!] SHAP unavailable. Install with: pip install shap")


# ── Greek Interaction Matrix (JS-condition space) ─────────────────────────────

def analyze_interaction_matrix(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Iterates over all 2^7 = 128 binary sign-combinations of the 7 JS condition
    Greeks (IV excluded — handled separately as High/Low split).
    Returns a DataFrame ranked by Avg_Edge.
    """
    print("\n[*] Building Greek Interaction Matrix (JS condition space) ...")

    # Resolve available columns
    available_greeks = [
        js for js in JS_CONDITION_GREEKS
        if GREEK_MAP.get(js) in df_raw.columns
    ]
    missing = [js for js in JS_CONDITION_GREEKS if js not in available_greeks]
    if missing:
        print(f"    [!] Missing columns for: {missing} — excluded from matrix axes")

    cols = [GREEK_MAP[js] for js in available_greeks]
    target_col = df_raw["target"].astype(int)

    results = []
    for iv_state in ["High", "Low"]:
        # IV filter
        if "atm_iv" in df_raw.columns:
            if "date" in df_raw.columns:
                med = df_raw.groupby("date")["atm_iv"].transform("median")
            else:
                med = df_raw["atm_iv"].median()
            iv_mask = (df_raw["atm_iv"] > med) if iv_state == "High" \
                      else (df_raw["atm_iv"] <= med)
        else:
            iv_mask = pd.Series(True, index=df_raw.index)

        df_iv = df_raw[iv_mask].copy()
        if len(df_iv) < MIN_COMBO_N:
            continue

        for combo in itertools.product(["Pos", "Neg"], repeat=len(available_greeks)):
            mask = pd.Series(True, index=df_iv.index)
            desc_parts = [f"IV={iv_state}"]
            for js_name, sign, col in zip(available_greeks, combo, cols):
                if sign == "Pos":
                    mask &= df_iv[col] >= 0
                    desc_parts.append(f"{js_name}+")
                else:
                    mask &= df_iv[col] < 0
                    desc_parts.append(f"{js_name}-")

            sub = df_iv[mask]
            n = len(sub)
            if n < MIN_COMBO_N:
                continue

            t = target_col.loc[sub.index]
            avg_edge  = t.mean()
            bull_prob = (t == 1).mean()
            bear_prob = (t == -1).mean()
            neut_prob = (t == 0).mean()
            std       = t.std()
            edge_ratio = avg_edge / std if std > 0 else np.nan

            # Check if this combo matches a known JS structure
            combo_dict = {js: sign for js, sign in zip(available_greeks, combo)}
            matched_id = _match_js_structure(iv_state, combo_dict)

            results.append({
                "Combination":  " | ".join(desc_parts),
                "IV_State":     iv_state,
                "Samples":      n,
                "Avg_Edge":     round(avg_edge, 4),
                "Edge_Ratio":   round(edge_ratio, 4) if not np.isnan(edge_ratio) else np.nan,
                "Bull_Prob":    round(bull_prob, 3),
                "Bear_Prob":    round(bear_prob, 3),
                "Neut_Prob":    round(neut_prob, 3),
                "JS_Structure": matched_id,
            })

    matrix_df = pd.DataFrame(results).sort_values("Avg_Edge", ascending=False)
    out_path = OUTPUT_DIR / "interaction_matrix.xlsx"
    matrix_df.to_excel(out_path, index=False)
    print(f"\n[*] Interaction matrix saved → {out_path}")
    print(f"    {len(matrix_df)} combinations with ≥ {MIN_COMBO_N} samples\n")

    print("TOP 10 BULLISH COMBINATIONS:")
    print(matrix_df.head(10)[
        ["Combination", "Samples", "Avg_Edge", "Bull_Prob", "Bear_Prob", "JS_Structure"]
    ].to_string(index=False))

    print("\nTOP 10 BEARISH COMBINATIONS:")
    print(matrix_df.tail(10)[
        ["Combination", "Samples", "Avg_Edge", "Bull_Prob", "Bear_Prob", "JS_Structure"]
    ].sort_values("Avg_Edge").to_string(index=False))

    # New patterns (not in any JS structure)
    new = matrix_df[matrix_df["JS_Structure"] == "—"]
    print(f"\n[*] {len(new)} combinations NOT present in the {len(MARKET_STRUCTURES)} JS structures.")
    if not new.empty:
        print("    Top 5 new bullish patterns:")
        print(new.head(5)[["Combination", "Samples", "Avg_Edge", "Bull_Prob"]].to_string(index=False))
        print("    Top 5 new bearish patterns:")
        print(new.tail(5)[["Combination", "Samples", "Avg_Edge", "Bear_Prob"]].sort_values("Avg_Edge").to_string(index=False))
        new.to_excel(OUTPUT_DIR / "new_patterns.xlsx", index=False)

    return matrix_df


def _match_js_structure(iv_state: str, combo: dict) -> str:
    """
    Match a greek sign-combo against the JS structures using shared module.
    """
    matches = match_market_structure(iv_state, combo)
    if not matches:
        return "—"
    return " / ".join([f"#{s['id']}" for s in matches])


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        X, y, feature_names, df_raw = load_and_preprocess()

        model = train_analysis_model(X, y, feature_names)

        # Persist model
        model_path = OUTPUT_DIR / "analysis_model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        print(f"\n[*] Model saved → {model_path}")

        discover_greek_relationships(model, X, feature_names)

        analyze_interaction_matrix(df_raw)

        print(f"\n[*] Analysis complete.  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Results directory: {OUTPUT_DIR}")

    except Exception as exc:
        import traceback
        print(f"\n[!] Analysis failed: {exc}")
        traceback.print_exc()