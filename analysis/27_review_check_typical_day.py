"""Follow-up to check C: change in the total effect of the SAME typical wet day (early-period mean rain hours
and early-period share with commute rain), compared with a dry day, in both periods.

Usage: python 27_review_check_typical_day.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np

root = Path(sys.argv[1])
# reuse the data preparation from script 26 without rerunning all its checks
src = (Path(__file__).parent / "26_review_checks.py").read_text(encoding="utf-8")
src = src.split("# ---------- A. did wet days change? ----------")[0]
ns = {"__name__": "rc", "__file__": str(Path(__file__).parent / "26_review_checks.py")}
sys.argv = [sys.argv[0], str(root)]
exec(compile(src, "26_review_checks.py (data part)", "exec"), ns)
P9, period_fit, lin = ns["P9"], ns["period_fit"], ns["lin"]
BASE = ["light", "wet"] + ns["TEMP"] + ["sun_h"]

wd = P9.drop_duplicates("date")
early_wet = wd[(wd["wet"] == 1) & (wd["period"] == "early")]
h = float(early_wet["rain_hours"].mean())
cshare = float(early_wet["commute_wet"].mean())
r = period_fit(P9, BASE + ["rain_hours", "commute_wet"])
w = {}
for p, sign in (("late", 1), ("early", -1)):
    w[f"wet:{p}"] = sign
    w[f"rain_hours:{p}"] = sign * h
    w[f"commute_wet:{p}"] = sign * cshare
change = lin(r, w)
early_total = lin(r, {"wet:early": 1, "rain_hours:early": h, "commute_wet:early": cshare})
late_total = lin(r, {"wet:late": 1, "rain_hours:late": h, "commute_wet:late": cshare})
res = {"typical_wet_day": {"rain_hours": h, "commute_rain_share": cshare},
       "early_total_effect": early_total, "late_total_effect": late_total, "change": change}
print(f"typical early wet day: {h:.2f} rain hours, {cshare:.2f} with commute rain")
for k in ("early_total_effect", "late_total_effect", "change"):
    x = res[k]
    print(f"{k:20s} {x['est']:+.4f} [{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}]  ({100 * (np.exp(x['est']) - 1):+.1f}%)" if k != "change" else
          f"{k:20s} {x['est']:+.4f} [{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}]")
out = root / "results" / "review_checks" / "review_checks.json"
R = json.loads(out.read_text())
R["C_typical_wet_day"] = res
out.write_text(json.dumps(R, indent=2, default=float))
