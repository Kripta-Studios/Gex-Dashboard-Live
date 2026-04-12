"""
Proyecto GEM — ETL Pipeline (Hybrid v4)
Combines Fitbit RMSSD + GLOBEM screen/steps → gem_data.json

Hybrid architecture:
  - BehaviorScore: Logistic sigmoid over Composite Digital Load (CD)
  - StressScore: Linear percentage drop of RMSSD
  - IS = 0.55 × StressScore + 0.45 × BehaviorScore
  - Session classification: per-user percentile thresholds
"""
import pandas as pd
import numpy as np
import json
import math

# =================================================================
# HYPERPARAMETERS — Composite Digital Load (CD)
# =================================================================
HYPER = {
    # Normalizacion de Carga Digital (CD)
    "alpha":  1.0,     # peso de S_dur (min pantalla)
    "beta":   3.0,     # peso de U_freq (desbloqueos)
    "gamma_cd": 0.03,  # peso compensatorio de P_acc (pasos)
    # Curva Conductual (Sigmoide)
    "k":      0.012,   # pendiente de la sigmoide conductual
    "theta":  280,     # punto de inflexion (unidades CD)
    # Integration weights
    "w_stress": 0.55,
    "w_behavior": 0.45,
}

print(f"GEM ETL v4 (Hybrid) — CD Sigmoid + Linear Stress")
print(f"  CD: alpha={HYPER['alpha']}, beta={HYPER['beta']}, gamma={HYPER['gamma_cd']}")
print(f"  Sigmoid: k={HYPER['k']}, theta={HYPER['theta']}")
print(f"  Weights: stress={HYPER['w_stress']}, behavior={HYPER['w_behavior']}")


# =================================================================
# 1. LOAD FITBIT DATA
# =================================================================

print("\nLoading Fitbit data...")
fitbit_csv = "../dataset_final_pitch.csv"
fitbit_users = []
baseline_rmssd = 21.58

try:
    df_fitbit = pd.read_csv(fitbit_csv)
    print(f"  Fitbit users: {df_fitbit.Id.nunique()}, rows: {len(df_fitbit)}")
    for _, row in df_fitbit.iterrows():
        fitbit_users.append({
            "id": str(int(row["Id"])),
            "rmssd": round(row["RMSSD_ms"], 2),
            "sedentary_min": round(row["SedentaryMinutes"], 1),
            "risk": row["Perfil_Riesgo"],
        })
    baseline_rmssd = df_fitbit["RMSSD_ms"].mean()
except FileNotFoundError:
    print(f"  {fitbit_csv} not found - loading from gem_data.json cache")
    try:
        with open("gem_data.json") as f:
            _cache = json.load(f)
        fitbit_users = _cache.get("fitbit_users", [])
        baseline_rmssd = _cache.get("fitbit_baseline_rmssd", 21.58)
        print(f"  Loaded {len(fitbit_users)} Fitbit users from cache")
    except Exception:
        print("  WARNING: No Fitbit data available, using defaults")

print(f"  Population RMSSD baseline: {baseline_rmssd:.2f} ms")


# =================================================================
# 2. LOAD GLOBEM DATA
# =================================================================

print("\nLoading GLOBEM data...")
dfs_screen = []
dfs_steps = []

SCREEN_METRICS = [
    "sumdurationunlock", "countepisodeunlock", "avgdurationunlock",
    "maxdurationunlock", "mindurationunlock", "stddurationunlock",
]
STEPS_METRICS = ["sumsteps", "sumdurationsedentarybout", "sumdurationactivebout"]
TIME_SEGMENTS = ["morning", "afternoon", "evening", "night", "allday"]

for i in range(1, 5):
    base = f"../globem_temp/GLOBEM-main/data_raw/INS-W-sample_{i}"
    feat = f"{base}/FeatureData"
    try:
        scr = pd.read_csv(f"{feat}/screen.csv", low_memory=False)
        stp = pd.read_csv(f"{feat}/steps.csv", low_memory=False)

        scr_cols = ["pid", "date"]
        for seg in TIME_SEGMENTS:
            for m in SCREEN_METRICS:
                col = f"f_screen:phone_screen_rapids_{m}:{seg}"
                if col in scr.columns:
                    scr_cols.append(col)
        dfs_screen.append(scr[scr_cols])

        stp_cols = ["pid", "date"]
        for seg in TIME_SEGMENTS:
            for m in STEPS_METRICS:
                col = f"f_steps:fitbit_steps_intraday_rapids_{m}:{seg}"
                if col in stp.columns:
                    stp_cols.append(col)
        dfs_steps.append(stp[stp_cols])
        print(f"  Sample {i}: screen={len(scr)}, steps={len(stp)}")
    except Exception as e:
        print(f"  Sample {i} error: {e}")

df_screen = pd.concat(dfs_screen, ignore_index=True)
df_steps = pd.concat(dfs_steps, ignore_index=True)
df = df_screen.merge(df_steps, on=["pid", "date"], how="inner")

rename = {}
for seg in TIME_SEGMENTS:
    rename[f"f_screen:phone_screen_rapids_sumdurationunlock:{seg}"] = f"screen_min_{seg}"
    rename[f"f_screen:phone_screen_rapids_countepisodeunlock:{seg}"] = f"unlocks_{seg}"
    rename[f"f_screen:phone_screen_rapids_avgdurationunlock:{seg}"] = f"avg_session_{seg}"
    rename[f"f_screen:phone_screen_rapids_maxdurationunlock:{seg}"] = f"max_session_{seg}"
    rename[f"f_screen:phone_screen_rapids_mindurationunlock:{seg}"] = f"min_session_{seg}"
    rename[f"f_screen:phone_screen_rapids_stddurationunlock:{seg}"] = f"std_session_{seg}"
    rename[f"f_steps:fitbit_steps_intraday_rapids_sumsteps:{seg}"] = f"steps_{seg}"
    rename[f"f_steps:fitbit_steps_intraday_rapids_sumdurationsedentarybout:{seg}"] = f"sedentary_min_{seg}"
    rename[f"f_steps:fitbit_steps_intraday_rapids_sumdurationactivebout:{seg}"] = f"active_min_{seg}"

df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
df = df.dropna(subset=["screen_min_allday", "steps_allday"], how="any")
print(f"\nMerged GLOBEM: {len(df)} rows, {df.pid.nunique()} participants")


# =================================================================
# 3. COMPUTE IS PER DAY
#    Hybrid: CD sigmoid for Behavior + linear StressScore
# =================================================================

def safe(val):
    if val is None:
        return 0.0
    if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
        return 0.0
    return float(val)


def sigmoid(x):
    """Numerically stable logistic sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        ex = math.exp(x)
        return ex / (1.0 + ex)


# ─── Session Classification ─────────────────────────────────

def build_user_thresholds(user_df):
    """Compute per-user percentile thresholds for session classification."""
    th = {}
    for seg in ["morning", "afternoon", "evening", "night"]:
        scol = f"screen_min_{seg}"
        stcol = f"steps_{seg}"
        scr_vals = user_df[scol].dropna()
        stp_vals = user_df[stcol].dropna()
        th[seg] = {
            "screen_p50": float(scr_vals.quantile(0.50)) if len(scr_vals) > 3 else 30,
            "screen_p75": float(scr_vals.quantile(0.75)) if len(scr_vals) > 3 else 60,
            "steps_p25": float(stp_vals.quantile(0.25)) if len(stp_vals) > 3 else 500,
        }
    th["allday"] = {
        "screen_p50": float(user_df["screen_min_allday"].quantile(0.50)),
        "screen_p75": float(user_df["screen_min_allday"].quantile(0.75)),
        "steps_p25": float(user_df["steps_allday"].quantile(0.25)),
    }
    return th


def classify_segment(row, seg, th):
    """Classify segment as productive/entertainment/none."""
    seg_screen = safe(row.get(f"screen_min_{seg}", 0))
    seg_steps = safe(row.get(f"steps_{seg}", 0))
    unlocks = safe(row.get(f"unlocks_{seg}", 0))
    avg_session = safe(row.get(f"avg_session_{seg}", 0))
    max_session = safe(row.get(f"max_session_{seg}", 0))

    if seg_screen < 3:
        return "none"

    screen_high = seg_screen > th[seg]["screen_p50"]
    steps_low = seg_steps < th[seg]["steps_p25"]
    binge = (unlocks > 0 and unlocks <= 5 and avg_session > 15)
    long_dominant = (max_session > 30 and max_session > seg_screen * 0.6)

    if screen_high and (steps_low or binge or long_dominant):
        return "entertainment"
    return "productive"


# ─── IS Computation ──────────────────────────────────────────

def compute_daily_is(row, baseline, th):
    """
    Compute daily IS using hybrid approach:
    - StressScore: Linear RMSSD percentage drop (original)
    - BehaviorScore: CD sigmoid + entertainment penalty + night penalty (hybrid)
    - IS = 0.55 * StressScore + 0.45 * BehaviorScore + consistency guarantees
    """
    screen = safe(row.get("screen_min_allday", 0))
    steps = safe(row.get("steps_allday", 0))
    active = safe(row.get("active_min_allday", 0))
    unlocks = safe(row.get("unlocks_allday", 0))
    real_sed = max(960 - active, 0)

    # ─── StressScore (LINEAR — original) ─────────────────────
    screen_norm = min(screen / 600, 1)
    sed_norm = min(real_sed / 900, 1)
    activity_protection = min(steps / 12000, 1) * 0.40
    rmssd_drop = (screen_norm * 0.6 + sed_norm * 0.4) * 12 * (1 - activity_protection)
    daily_rmssd = max(baseline - rmssd_drop, 8)
    stress_score = ((baseline - daily_rmssd) / baseline) * 100

    # ─── BehaviorScore (CD SIGMOID — new) ────────────────────
    # Composite Digital Load
    CD = (HYPER["alpha"] * screen +
          HYPER["beta"] * unlocks -
          HYPER["gamma_cd"] * steps)
    B_base = sigmoid(HYPER["k"] * (CD - HYPER["theta"]))

    # Session classification
    segments_class = {}
    ent_count = 0
    for seg in ["morning", "afternoon", "evening", "night"]:
        c = classify_segment(row, seg, th)
        segments_class[seg] = c
        if c == "entertainment":
            ent_count += 1

    # Entertainment penalty (additive on top of sigmoid base)
    ent_penalty = ent_count * 15

    # Night penalty
    night_screen = safe(row.get("screen_min_night", 0))
    night_penalty = min(night_screen / 60, 1) * 10 if night_screen > 30 else 0

    behavior_score = min(B_base * 65 + ent_penalty + night_penalty, 100)

    # ─── IS = 0.55 × StressScore + 0.45 × BehaviorScore ─────
    IS = HYPER["w_stress"] * stress_score + HYPER["w_behavior"] * behavior_score

    # Consistency guarantees
    if ent_count >= 2:
        IS = max(IS, 50)
    if ent_count >= 3:
        IS = max(IS, 65)
    if ent_count >= 3 and screen > th["allday"]["screen_p75"]:
        IS = max(IS, 75)
    if ent_count == 4:
        IS = max(IS, 78)
    if screen > 500 and steps < 3000:
        IS = max(IS, 75)

    return {
        "daily_rmssd": round(daily_rmssd, 2),
        "stress_score": round(stress_score, 1),
        "behavior_score": round(behavior_score, 1),
        "IS": round(IS, 1),
        "CD": round(CD, 1),
        "B_base": round(B_base, 3),
        "session_class": segments_class,
        "real_sedentary": round(real_sed, 0),
    }


# =================================================================
# 4. USER BASELINES
# =================================================================

print("\nComputing user baselines...")

user_avgs = df.groupby("pid").agg({
    "screen_min_allday": "mean",
    "steps_allday": "mean",
    "active_min_allday": "mean",
}).dropna()

user_avgs["real_sedentary"] = 960 - user_avgs["active_min_allday"]
activity_ratio = user_avgs["active_min_allday"] / 960
user_avgs["synth_rmssd_baseline"] = 20 + activity_ratio * 20


# =================================================================
# 5. SELECT DIVERSE USERS & BUILD OUTPUT
# =================================================================

print("\nSelecting diverse profiles...")

selected = set()
selected.update(user_avgs.nlargest(2, "screen_min_allday").index.tolist())
selected.update(user_avgs.nsmallest(2, "screen_min_allday").index.tolist())
selected.update(user_avgs.nlargest(2, "steps_allday").index.tolist())
selected.update(user_avgs.nlargest(2, "real_sedentary").index.tolist())
remaining = [p for p in user_avgs.index if p not in selected]
while len(selected) < 8 and remaining:
    selected.add(remaining.pop(0))
selected = list(selected)[:8]

output_users = []

for pid in selected:
    user_df = df[df.pid == pid].sort_values("date")
    if len(user_df) < 5:
        continue

    baseline = float(user_avgs.loc[pid, "synth_rmssd_baseline"])
    th = build_user_thresholds(user_df)

    daily = []
    for _, row in user_df.iterrows():
        day = {"date": str(row["date"])}
        for col in row.index:
            if col in ["pid", "date"]:
                continue
            val = row[col]
            if pd.notna(val):
                val = float(val)
                day[col] = round(val, 1) if val != int(val) else int(val)

        is_result = compute_daily_is(row, baseline, th)
        day.update(is_result)
        daily.append(day)

    avg_screen = float(user_avgs.loc[pid, "screen_min_allday"])
    avg_steps = float(user_avgs.loc[pid, "steps_allday"])
    avg_active = float(user_avgs.loc[pid, "active_min_allday"])
    avg_sed = round(960 - avg_active, 0)
    avg_is = np.mean([d["IS"] for d in daily])

    total_ent = sum(
        sum(1 for v in d["session_class"].values() if v == "entertainment")
        for d in daily
    )
    is_critical = sum(1 for d in daily if d["IS"] >= 75)

    output_users.append({
        "pid": pid,
        "baseline_rmssd": round(baseline, 2),
        "avg_screen": round(avg_screen, 1),
        "avg_steps": int(avg_steps),
        "avg_sedentary": round(avg_sed, 1),
        "avg_IS": round(float(avg_is), 1),
        "days": len(daily),
        "daily": daily,
    })

    print(f"  {pid}: screen={round(avg_screen)}min, steps={int(avg_steps)}, "
          f"avg_IS={avg_is:.1f}%, IS>75={is_critical}/{len(daily)}, "
          f"ent={total_ent}")

output = {
    "engine": "Hybrid v4 (CD sigmoid + linear stress)",
    "hyperparameters": HYPER,
    "fitbit_baseline_rmssd": round(baseline_rmssd, 2),
    "fitbit_users": sorted(fitbit_users, key=lambda x: x["rmssd"], reverse=True),
    "globem_users": sorted(output_users, key=lambda x: x["avg_IS"], reverse=True),
}

with open("gem_data.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\n=== gem_data.json SAVED ===")
print(f"Fitbit users: {len(fitbit_users)}, GLOBEM users: {len(output_users)}")
