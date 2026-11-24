"""Check 1: does a counter replacement by itself change the measured rain effect?

For each location, take its device change with the most data on both sides:
the old device's last 365 days and the new device's first 365 days (at least
180 usable days on each side). Weather effects are estimated separately before
and after the change, with the same model as the main analysis.
If new devices react differently to rain, the wet-day effect should jump at the change.

Usage: python 13_check_devices.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import fit
from design import effects, load

root = Path(sys.argv[1])
core = json.loads((root / "data" / "derived" / "sample_definitions.json").read_text())["period_comparison_locations"]
d = load(root)

# Short-lived temporary devices (under 180 usable days) are skipped, so each event compares
# a long-lived device with the next long-lived device at the same location. The earliest
# such event per location is used: it is the replacement of the original counter.
events = []
for loc, g in d.groupby("loc"):
    span = g.groupby("device")["date"].agg(["min", "max", "size"]).sort_values("min")
    span = span[span["size"] >= 180]
    devs = list(span.index)
    for old, new in zip(devs[:-1], devs[1:]):
        last_old, switch = span.loc[old, "max"], span.loc[new, "min"]
        if (switch - last_old).days > 365:
            continue
        b = g[(g["device"] == old) & (g["date"] > last_old - pd.Timedelta(days=365))]
        a = g[(g["device"] == new) & (g["date"] < switch + pd.Timedelta(days=365))]
        if len(b) >= 180 and len(a) >= 180:
            events.append({"loc": loc, "old": old, "new": new, "old_last": last_old, "switch": switch,
                           "n_before": len(b), "n_after": len(a),
                           "rows": pd.concat([b.assign(side="before"), a.assign(side="after")])})
ev = pd.DataFrame(events).sort_values("switch").drop_duplicates("loc")  # earliest replacement per location
print(ev[["loc", "old", "new", "old_last", "switch", "n_before", "n_after"]].sort_values("switch").to_string(index=False))

out = {}
for name, sel in (("all_locations", ev), ("core_9", ev[ev["loc"].isin(core)])):
    s = pd.concat(list(sel["rows"]), ignore_index=True)
    r = fit(s, "side")
    eb, ea = effects(r["beta"], r["vcov"], "before"), effects(r["beta"], r["vcov"], "after")
    res = {"locations": int(s["loc"].nunique()), "location_days": int(r["n"]),
           "switch_years": sorted(set(sel["switch"].dt.year.tolist()))}
    for k in ("rain", "cold", "heat"):
        a = ea[k][2] - eb[k][2]
        ch = ea[k][0] - eb[k][0]
        se = float(np.sqrt(a @ r["vcov"] @ a))
        res[k] = {"before": eb[k][0], "after": ea[k][0], "change": ch, "ci95": [ch - 1.96 * se, ch + 1.96 * se]}
    out[name] = res
    print(f"\n{name}: {res['locations']} locations, {res['location_days']} location-days, switches in {res['switch_years']}")
    for k in ("rain", "cold", "heat"):
        x = res[k]
        print(f"  {k:5s} before {x['before']:+.4f}  after {x['after']:+.4f}  change {x['change']:+.4f} "
              f"[{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}]")
print("\nFor comparison, the main result (prediction 1): change in the rain effect +0.0680 [+0.0206, +0.1153]")
(root / "results" / "check_devices.json").write_text(json.dumps(out, indent=2, default=float))
