import pandas as pd
stp = pd.read_csv("../globem_temp/GLOBEM-main/data_raw/INS-W-sample_1/FeatureData/steps.csv", low_memory=False)

col_active = "f_steps:fitbit_steps_intraday_rapids_sumdurationactivebout:allday"
col_sed = "f_steps:fitbit_steps_intraday_rapids_sumdurationsedentarybout:allday"

v_act = stp[col_active].dropna()
v_sed = stp[col_sed].dropna()

print("Active bout allday (minutes):")
print(f"  min={v_act.min():.1f}, mean={v_act.mean():.1f}, max={v_act.max():.1f}")
print(f"  mean = {v_act.mean():.0f} min = {v_act.mean()/60:.1f} hours")
print()
print("Raw sedentary bout (includes sleep/idle):")
print(f"  min={v_sed.min():.1f}, mean={v_sed.mean():.1f}, max={v_sed.max():.1f}")
print()

# Real sedentary = waking hours (16h=960min) - active
merged = pd.DataFrame({"active": v_act, "sed_raw": v_sed}).dropna()
merged["waking_sed"] = 960 - merged["active"]
print("Corrected waking sedentary (960 - active):")
print(f"  min={merged['waking_sed'].min():.0f}, mean={merged['waking_sed'].mean():.0f}, max={merged['waking_sed'].max():.0f}")
print(f"  mean = {merged['waking_sed'].mean()/60:.1f} hours of the 16 waking hours")
print()

# Per segment
for seg in ["morning", "afternoon", "evening", "night"]:
    act_c = f"f_steps:fitbit_steps_intraday_rapids_sumdurationactivebout:{seg}"
    sed_c = f"f_steps:fitbit_steps_intraday_rapids_sumdurationsedentarybout:{seg}"
    if act_c in stp.columns:
        a = stp[act_c].dropna()
        s = stp[sed_c].dropna()
        print(f"  {seg}: active={a.mean():.0f}min, sed_raw={s.mean():.0f}min, sum={a.mean()+s.mean():.0f} (should be ~360)")
