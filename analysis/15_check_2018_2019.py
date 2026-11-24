"""Follow-up to check 1: is the stronger rain effect after the 2018-2019 swaps a year effect?

Uses only locations whose counter was NOT replaced between 2018 and 2019 (the same device
has at least 180 usable days in each year), and compares 2018 with 2019.

Usage: python 15_check_2018_2019.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import fit
from design import effects, load

root = Path(sys.argv[1])
d = load(root)
d = d[d["year"].isin([2018, 2019])]
n = d.groupby(["loc", "device", "year"]).size().unstack(fill_value=0)
same = n[(n.get(2018, 0) >= 180) & (n.get(2019, 0) >= 180)].reset_index()
print("locations with the same device in 2018 and 2019:", same[["loc", "device"]].to_records(index=False).tolist())
s = d.merge(same[["loc", "device"]], on=["loc", "device"])
s["side"] = s["year"].astype(str)
r = fit(s, "side")
e18, e19 = effects(r["beta"], r["vcov"], "2018"), effects(r["beta"], r["vcov"], "2019")
a = e19["rain"][2] - e18["rain"][2]
ch = e19["rain"][0] - e18["rain"][0]
se = float(np.sqrt(a @ r["vcov"] @ a))
out = {"locations": same["loc"].tolist(), "location_days": int(r["n"]),
       "rain_2018": e18["rain"][0], "rain_2019": e19["rain"][0], "change": ch, "ci95": [ch - 1.96 * se, ch + 1.96 * se]}
print(f"rain 2018 {out['rain_2018']:+.4f}  2019 {out['rain_2019']:+.4f}  change {ch:+.4f} [{ch - 1.96 * se:+.4f}, {ch + 1.96 * se:+.4f}]")
print("compare: jump at the swaps, key locations -0.1300 [-0.2103, -0.0497], all swapped locations -0.0491 [-0.0870, -0.0112]")
(root / "results" / "check_2018_2019.json").write_text(json.dumps(out, indent=2, default=float))
