import json

d = json.load(open("gem_data.json"))
for u in d["globem_users"]:
    stresses = [day["stress_score"] for day in u["daily"]]
    rmssds = [day["daily_rmssd"] for day in u["daily"]]
    at_100 = sum(1 for s in stresses if s >= 99)
    at_floor = sum(1 for r in rmssds if r <= 5)
    pid = u["pid"]
    bl = u["baseline_rmssd"]
    print(f"  {pid}: baseline={bl}ms, stress@100={at_100}/{len(stresses)}, "
          f"rmssd_at_floor={at_floor}, rmssd=[{min(rmssds):.1f}, {max(rmssds):.1f}]")
