"""Build the daily bicycle count table (counts only, no weather).

One row per counter device and day. Daytime = 6:00 to 20:00 local time (56 slots of 15 minutes).
Cleaning flags follow the plan (section 4). Rows are flagged, not deleted, so the
"no cleaning" check can use the same table.

Usage: python 03_build_counts.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
raw = root / "data" / "raw"
der = root / "data" / "derived"
der.mkdir(parents=True, exist_ok=True)

cols = ["FK_STANDORT", "DATUM", "VELO_IN", "VELO_OUT"]
pq = pd.read_parquet(raw / "zurich_counts" / "verkehrszaehlungen_werte_fussgaenger_velo_alle_jahre.parquet", columns=cols)
c26 = pd.read_csv(raw / "zurich_counts" / "2026_verkehrszaehlungen_werte_fussgaenger_velo.csv", usecols=cols)
pq = pq[pq["DATUM"] < "2026-01-01"]  # ISO strings, so string order equals time order
v = pd.concat([pq, c26], ignore_index=True)
v = v.dropna(subset=["VELO_IN", "VELO_OUT"], how="all")
v["DATUM"] = pd.to_datetime(v["DATUM"], format="%Y-%m-%dT%H:%M")
# duplicates occur only at 2:00-3:59 on clock-change nights (checked in 02_checks.py)
v = v.drop_duplicates(["FK_STANDORT", "DATUM"], keep="first")

# which directions does each device normally report?
has_in = v.groupby("FK_STANDORT")["VELO_IN"].apply(lambda s: s.notna().mean() > 0.5)
has_out = v.groupby("FK_STANDORT")["VELO_OUT"].apply(lambda s: s.notna().mean() > 0.5)
v["ok"] = ((~v["FK_STANDORT"].map(has_in)) | v["VELO_IN"].notna()) & ((~v["FK_STANDORT"].map(has_out)) | v["VELO_OUT"].notna())
v["velo"] = v["VELO_IN"].fillna(0).astype("int64") + v["VELO_OUT"].fillna(0).astype("int64")
v["date"] = v["DATUM"].dt.normalize()
v["hour"] = v["DATUM"].dt.hour
v = v[(v["hour"] >= 6) & (v["hour"] < 20)]
v["am"] = v["hour"].between(7, 8)    # 7:00 to 8:59
v["pm"] = v["hour"].between(16, 18)  # 16:00 to 18:59

g = v.groupby(["FK_STANDORT", "date"])
d = pd.DataFrame({
    "n_slots_ok": g["ok"].sum(),
    "velo_day": g["velo"].sum(),
    "velo_am": v[v["am"]].groupby(["FK_STANDORT", "date"])["velo"].sum(),
    "velo_pm": v[v["pm"]].groupby(["FK_STANDORT", "date"])["velo"].sum(),
}).reset_index()
d["complete"] = d["n_slots_ok"] == 56

# station metadata
gj = json.loads((raw / "zurich_stations" / "standorte.geojson").read_text(encoding="utf-8"))
meta = pd.DataFrame([{**f["properties"], "E": f["geometry"]["coordinates"][0], "N": f["geometry"]["coordinates"][1]}
                     for f in gj["features"]])
meta = meta[meta["velo"] == 1].set_index("id1")
d["loc"] = d["FK_STANDORT"].map(meta["abkuerzung"])
d["name"] = d["FK_STANDORT"].map(meta["bezeichnung"])
d["E"] = d["FK_STANDORT"].map(meta["E"])
d["N"] = d["FK_STANDORT"].map(meta["N"])
assert d["loc"].notna().all(), "device without metadata"
d = d.rename(columns={"FK_STANDORT": "device"})

# cleaning flags, on complete days only
c = d["complete"]
d["ym"] = d["date"].dt.to_period("M").astype(str)
med = d[c].groupby(["loc", "ym"])["velo_day"].median().rename("loc_month_median")
d = d.merge(med, left_on=["loc", "ym"], right_index=True, how="left")
d["flag_zero"] = c & (d["velo_day"] == 0)
d["flag_low"] = c & (d["velo_day"] < 0.05 * d["loc_month_median"])
d["flag_high"] = c & (d["velo_day"] > 5 * d["loc_month_median"])
d = d.sort_values(["device", "date"]).reset_index(drop=True)
cd = d[c].copy()
new_run = (cd["device"] != cd["device"].shift()) | (cd["velo_day"] != cd["velo_day"].shift()) | \
          ((cd["date"] - cd["date"].shift()).dt.days != 1)
cd["run"] = new_run.cumsum()
run_len = cd.groupby("run")["run"].transform("size")
d["flag_stuck"] = False
d.loc[cd.index[run_len >= 3], "flag_stuck"] = True
d["flag_any"] = d[["flag_zero", "flag_low", "flag_high", "flag_stuck"]].any(axis=1)
d["keep"] = d["complete"] & ~d["flag_any"]
d["year"] = d["date"].dt.year

d.to_parquet(der / "counts_daily.parquet", index=False)

# sample for the period comparison, exactly as written in the plan:
# at least two calendar years with >= 300 complete days in 2011-2014 and in 2022-2025
cy = d[d["complete"]].groupby(["loc", "year"]).size().unstack(fill_value=0)
early = (cy.reindex(columns=range(2011, 2015), fill_value=0) >= 300).sum(axis=1)
late = (cy.reindex(columns=range(2022, 2026), fill_value=0) >= 300).sum(axis=1)
core = sorted(cy.index[(early >= 2) & (late >= 2)])
expected = ["VZS_ANDR", "VZS_BINZ", "VZS_HOFW", "VZS_LUXG", "VZS_MUEH", "VZS_MYTH", "VZS_SCHE", "VZS_SCHU", "VZS_SIHL"]
assert core == expected, core
(der / "sample_definitions.json").write_text(json.dumps({"period_comparison_locations": core}, indent=2), encoding="utf-8")

print("device-days", len(d), "| complete", int(d["complete"].sum()), "| kept after cleaning", int(d["keep"].sum()))
print("flags on complete days: zero", int(d["flag_zero"].sum()), "low", int(d["flag_low"].sum()),
      "high", int(d["flag_high"].sum()), "stuck", int(d["flag_stuck"].sum()), "any", int(d["flag_any"].sum()))
print("locations", d["loc"].nunique(), "| devices", d["device"].nunique())
print("kept location-days per year:\n", d[d["keep"]].groupby("year").size().to_string())
print("period-comparison locations:", core)
