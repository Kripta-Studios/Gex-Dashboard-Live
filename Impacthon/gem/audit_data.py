"""Audit current gem_data.json to understand classification + IS inconsistencies"""
import json

d = json.load(open("gem_data.json"))

for i, u in enumerate(d["globem_users"]):
    daily = u["daily"]
    ent_total = 0
    prod_total = 0
    is_above_75 = 0
    for day in daily:
        sc = day.get("session_class", {})
        for seg in ["morning", "afternoon", "evening", "night"]:
            c = sc.get(seg, "none")
            if c == "entertainment":
                ent_total += 1
            if c == "productive":
                prod_total += 1
        if day["IS"] >= 75:
            is_above_75 += 1

    pid = u["pid"]
    print(f"Usuario {i+1} ({pid}): IS_avg={u['avg_IS']:.1f}%, screen={u['avg_screen']:.0f}min, steps={u['avg_steps']}, days={u['days']}")
    print(f"  Productive segments: {prod_total}, Entertainment: {ent_total}, IS>75: {is_above_75}/{u['days']}")

    # Show worst day (highest IS)
    worst = max(daily, key=lambda x: x["IS"])
    print(f"  Worst day: screen={worst.get('screen_min_allday',0):.0f}, steps={worst.get('steps_allday',0):.0f}, "
          f"IS={worst['IS']}, stress={worst['stress_score']}, behavior={worst['behavior_score']}")
    print(f"    class: {worst.get('session_class',{})}")
    
    # Show best day (lowest IS)
    best = min(daily, key=lambda x: x["IS"])
    print(f"  Best day:  screen={best.get('screen_min_allday',0):.0f}, steps={best.get('steps_allday',0):.0f}, "
          f"IS={best['IS']}, stress={best['stress_score']}, behavior={best['behavior_score']}")
    print(f"    class: {best.get('session_class',{})}")
    print()

# Detailed look at last user
print("=" * 60)
print("DETAILED: Last user (Usuario 8)")
u = d["globem_users"][-1]
for day in u["daily"]:
    sc = day.get("session_class", {})
    ent = sum(1 for s in sc.values() if s == "entertainment")
    prod = sum(1 for s in sc.values() if s == "productive")
    print(f"  {day['date']}: IS={day['IS']:5.1f}, stress={day['stress_score']:5.1f}, behav={day['behavior_score']:5.1f}, "
          f"screen={day.get('screen_min_allday',0):6.0f}min, steps={day.get('steps_allday',0):6.0f}, "
          f"ent={ent}, prod={prod}, class={sc}")
