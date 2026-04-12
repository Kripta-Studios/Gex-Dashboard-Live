"""
Proyecto GEM — ETL Pipeline v4
Generates hourly intraday data for mobile app + admin panel.
IS = 0.55 × StressScore + 0.45 × BehaviorScore
Output: gem_data.json with hourly resolution per user/day.
"""
import pandas as pd
import numpy as np
import json
import math

# ═══════════════════════════════════════════════════════════════
# 1. LOAD FITBIT DATA
# ═══════════════════════════════════════════════════════════════
print("Loading Fitbit data...")
fitbit_csv = "../dataset_final_pitch.csv"
fitbit_users = []
baseline_rmssd = 21.58  # Default population baseline

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
    print(f"  {fitbit_csv} not found — loading from existing gem_data.json")
    try:
        with open("gem_data.json") as f:
            old = json.load(f)
        fitbit_users = old.get("fitbit_users", [])
        baseline_rmssd = old.get("fitbit_baseline_rmssd", 21.58)
        print(f"  Loaded {len(fitbit_users)} Fitbit users from cache")
    except:
        print("  WARNING: No Fitbit data available, using defaults")

print(f"  Population RMSSD baseline: {baseline_rmssd:.2f} ms")

# ═══════════════════════════════════════════════════════════════
# 2. LOAD GLOBEM DATA
# ═══════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════
# 3. USER BASELINES
# ═══════════════════════════════════════════════════════════════
print("\nComputing baselines...")

user_avgs = df.groupby("pid").agg({
    "screen_min_allday": "mean",
    "steps_allday": "mean",
    "active_min_allday": "mean",
}).dropna()

user_avgs["real_sedentary"] = 960 - user_avgs["active_min_allday"]
activity_ratio = user_avgs["active_min_allday"] / 960
user_avgs["synth_rmssd_baseline"] = 20 + activity_ratio * 20

# ═══════════════════════════════════════════════════════════════
# 4. HOURLY IS COMPUTATION
# ═══════════════════════════════════════════════════════════════

# Segment → hour mapping
SEG_HOURS = {
    "night":     list(range(0, 6)),    # 00-05
    "morning":   list(range(6, 12)),   # 06-11
    "afternoon": list(range(12, 18)),  # 12-17
    "evening":   list(range(18, 24)),  # 18-23
}

def compute_hourly(row, baseline):
    """Generate 24 hourly IS data points from segment-level data."""
    np.random.seed(hash(str(row.get("date", ""))) % 2**31)
    
    hourly = []
    for h in range(24):
        # Determine segment
        if h < 6:
            seg = "night"
        elif h < 12:
            seg = "morning"
        elif h < 18:
            seg = "afternoon"
        else:
            seg = "evening"
        
        def safe(val):
            """NaN-safe: return 0 for NaN/None."""
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return 0
            return float(val)
        
        seg_screen = safe(row.get(f"screen_min_{seg}", 0))
        seg_steps = safe(row.get(f"steps_{seg}", 0))
        seg_active = safe(row.get(f"active_min_{seg}", 0))
        
        # Distribute segment data across 6 hours with realistic patterns
        # Screen usage follows a pattern: low in early hours, peaks midday/evening
        hour_weights = {
            "night":     [0.05, 0.02, 0.01, 0.01, 0.02, 0.10],
            "morning":   [0.05, 0.12, 0.20, 0.25, 0.22, 0.16],
            "afternoon": [0.18, 0.20, 0.22, 0.18, 0.12, 0.10],
            "evening":   [0.10, 0.15, 0.22, 0.25, 0.20, 0.08],
        }
        idx = h % 6
        w = hour_weights[seg][idx]
        noise = 1 + np.random.normal(0, 0.15)
        w = max(w * noise, 0.01)
        
        h_screen = seg_screen * w
        h_steps = seg_steps * w * (1.2 if 8 <= h <= 18 else 0.5)
        h_active = seg_active * w
        h_sedentary = max(60 - h_active, 0)
        
        # Hourly IS calculation (more sensitive than daily)
        screen_norm = min(h_screen / 25, 1)       # 25 min/hr saturates
        sed_norm = min(h_sedentary / 50, 1)       # 50 min/hr sedentary
        act_prot = min(h_steps / 600, 1) * 0.35
        
        rmssd_drop = (screen_norm * 0.6 + sed_norm * 0.4) * 14 * (1 - act_prot)
        h_rmssd = max(baseline - rmssd_drop, 6)
        stress = min(((baseline - h_rmssd) / max(baseline, 1)) * 100, 100)
        
        # Behavior: CD sigmoid (hourly scale)
        # Hourly coefficients scaled down from daily (1 hour vs full day)
        h_unlocks = seg_screen / max(seg_steps / 200 + 1, 1) * w  # proxy: screen intensity
        h_cd = 1.0 * h_screen + 3.0 * h_unlocks - 0.03 * h_steps
        # Sigmoid with hourly inflection: ~15 CD units per hour

        h_cd_x = 0.08 * (h_cd - 15)
        if h_cd_x >= 0:
            b_base = 1.0 / (1.0 + math.exp(-h_cd_x))
        else:
            ex = math.exp(h_cd_x)
            b_base = ex / (1.0 + ex)
        
        screen_bonus = 20 if h_screen > 20 else (10 if h_screen > 10 else 0)
        behavior = min(b_base * 65 + screen_bonus, 100)
        
        is_val = 0.55 * stress + 0.45 * behavior
        
        # Clamp: sleeping hours (0-5) should be low IS unless screen is high
        if h < 6 and h_screen < 5:
            is_val = min(is_val, 15)
        
        hourly.append({
            "hour": h,
            "is": round(is_val, 1),
            "screen": round(h_screen, 1),
            "steps": round(h_steps, 0),
            "rmssd": round(h_rmssd, 1),
            "stress": round(stress, 1),
            "behavior": round(behavior, 1),
        })
    
    # Compute rest points: hours where IS > 50 AND IS is a local peak
    rest_points = []
    for i in range(1, 23):
        val = hourly[i]["is"]
        if val > 50 and val >= hourly[i-1]["is"] and val >= hourly[i+1]["is"]:
            rest_points.append(i)
    # Also flag any hour crossing 75%
    for i in range(24):
        if hourly[i]["is"] >= 75 and i not in rest_points:
            rest_points.append(i)
    rest_points.sort()
    
    daily_is = round(np.mean([h["is"] for h in hourly]), 1)
    
    return hourly, rest_points, daily_is


# ═══════════════════════════════════════════════════════════════
# 5. SELECT USERS & BUILD OUTPUT
# ═══════════════════════════════════════════════════════════════
print("\nSelecting users...")

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
user_num = 0

for pid in selected:
    user_df = df[df.pid == pid].sort_values("date")
    if len(user_df) < 5:
        continue
    
    user_num += 1
    baseline = float(user_avgs.loc[pid, "synth_rmssd_baseline"])
    
    days_out = []
    weekly_map = {}
    
    for _, row in user_df.iterrows():
        date_str = str(row["date"])
        hourly, rest_points, daily_is = compute_hourly(row, baseline)
        
        day_data = {
            "date": date_str,
            "daily_is": daily_is,
            "screen_total": round(row.get("screen_min_allday", 0), 0),
            "steps_total": round(row.get("steps_allday", 0), 0),
            "active_min": round(row.get("active_min_allday", 0), 0),
            "sedentary": round(max(960 - row.get("active_min_allday", 0), 0), 0),
            "rmssd_avg": round(np.mean([h["rmssd"] for h in hourly]), 1),
            "rest_points": rest_points,
            "alerts": len([h for h in hourly if h["is"] >= 75]),
            "hourly": hourly,
        }
        days_out.append(day_data)
        
        # Weekly aggregation
        try:
            dt = pd.to_datetime(date_str)
            wk = dt.strftime("%Y-W%V")
        except:
            wk = "unknown"
        if wk not in weekly_map:
            weekly_map[wk] = {"is": [], "screen": [], "steps": [], "alerts": 0}
        weekly_map[wk]["is"].append(daily_is)
        weekly_map[wk]["screen"].append(day_data["screen_total"])
        weekly_map[wk]["steps"].append(day_data["steps_total"])
        weekly_map[wk]["alerts"] += day_data["alerts"]
    
    # Build weekly summaries
    weekly_out = []
    prev_is = None
    for wk in sorted(weekly_map.keys()):
        w = weekly_map[wk]
        avg_is = round(np.mean(w["is"]), 1)
        trend = "stable"
        if prev_is is not None:
            diff = avg_is - prev_is
            if diff > 3:
                trend = "up"
            elif diff < -3:
                trend = "down"
        prev_is = avg_is
        weekly_out.append({
            "week": wk,
            "avg_is": avg_is,
            "avg_screen": round(np.mean(w["screen"]), 0),
            "avg_steps": round(np.mean(w["steps"]), 0),
            "alerts": w["alerts"],
            "days": len(w["is"]),
            "trend": trend,
        })
    
    avg_screen = float(user_avgs.loc[pid, "screen_min_allday"])
    avg_steps = float(user_avgs.loc[pid, "steps_allday"])
    avg_active = float(user_avgs.loc[pid, "active_min_allday"])
    avg_is = round(np.mean([d["daily_is"] for d in days_out]), 1)
    
    output_users.append({
        "id": f"Usuario {user_num}",
        "pid": pid,
        "baseline_rmssd": round(baseline, 1),
        "summary": {
            "avg_is": avg_is,
            "avg_screen": round(avg_screen, 0),
            "avg_steps": round(avg_steps, 0),
            "avg_active": round(avg_active, 0),
            "avg_sedentary": round(960 - avg_active, 0),
            "total_days": len(days_out),
            "critical_days": sum(1 for d in days_out if d["daily_is"] >= 75),
        },
        "days": days_out,
        "weekly": weekly_out,
    })
    
    crit = sum(1 for d in days_out if d["daily_is"] >= 75)
    print(f"  {pid} -> Usuario {user_num}: screen={round(avg_screen)}min, "
          f"steps={int(avg_steps)}, avg_IS={avg_is}%, critical={crit}/{len(days_out)}")

# Sort by avg IS descending
output_users.sort(key=lambda x: x["summary"]["avg_is"], reverse=True)

output = {
    "fitbit_baseline_rmssd": round(baseline_rmssd, 2),
    "fitbit_users": sorted(fitbit_users, key=lambda x: x["rmssd"], reverse=True),
    "users": output_users,
}

with open("gem_data.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\n=== gem_data.json SAVED ===")
print(f"Fitbit: {len(fitbit_users)}, GLOBEM users: {len(output_users)}")
total_hours = sum(len(d["days"]) * 24 for d in output_users)
print(f"Total hourly data points: {total_hours}")
