import json

d = json.load(open("gem_data.json"))
print(f"Users in output: {len(d['globem_users'])}")
for u in d["globem_users"]:
    seds = [day.get("real_sedentary", -1) for day in u["daily"][:3]]
    acts = [day.get("active_min_allday", -1) for day in u["daily"][:3]]
    print(f"  {u['pid']}: avg_sed={u['avg_sedentary']}, real_sed_sample={seds}, active_sample={acts}")
