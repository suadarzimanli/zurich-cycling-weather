"""Street slope at each bike counter location (geometry only, no counts or weather).

1. Street direction: the nearest road or path line within 25 m in swisstopo's swissTLM3D
   road dataset (geo.admin.ch identify service).
2. Elevation profile along that direction, 100 m each side of the counter, from swisstopo's
   profile service (swissALTI3D 2 m terrain model).
3. Grade = |elevation difference between the two ends| / 200 m.
Counters on bridges, in underpasses or in tunnels are flagged, because a terrain model does
not show the road surface there.
Raw responses are cached in data/raw/swisstlm3d_roads and data/raw/swisstopo_profiles.

Usage: python 17_slopes.py <project_dir>
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
raw = root / "data" / "raw"
osm_dir, prof_dir = raw / "swisstlm3d_roads", raw / "swisstopo_profiles"
osm_dir.mkdir(exist_ok=True)
prof_dir.mkdir(exist_ok=True)
UA = {"User-Agent": "research-script/1.0"}

c = pd.read_parquet(root / "data" / "derived" / "counts_daily.parquet")
first = c.groupby("device")["date"].min()
c["device_start"] = c["device"].map(first)
locs = c.sort_values("device_start").groupby("loc").agg(name=("name", "last"), E=("E", "last"), N=("N", "last"))


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


rows = []
for loc, r in locs.iterrows():
    f = osm_dir / f"{loc}.json"
    if not f.exists():
        q = {"geometry": f"{r['E']},{r['N']}", "geometryType": "esriGeometryPoint",
             "layers": "all:ch.swisstopo.swisstlm3d-strassen", "tolerance": 25,
             "mapExtent": f"{r['E'] - 100},{r['N'] - 100},{r['E'] + 100},{r['N'] + 100}",
             "imageDisplay": "200,200,96", "sr": 2056, "returnGeometry": "true", "geometryFormat": "geojson"}
        js = get("https://api3.geo.admin.ch/rest/services/api/MapServer/identify?" + urllib.parse.urlencode(q))
        f.write_text(json.dumps(js))
        time.sleep(0.5)
    feats = json.loads(f.read_text()).get("results", [])
    best = None
    for w in feats:
        g = w["geometry"]
        lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for line in lines:
            pts = np.array([xy[:2] for xy in line], dtype=float)
            for a, b in zip(pts[:-1], pts[1:]):
                ab = b - a
                L = np.hypot(*ab)
                if L == 0:
                    continue
                t = np.clip(((np.array([r["E"], r["N"]]) - a) @ ab) / L ** 2, 0, 1)
                dist = np.hypot(*(a + t * ab - np.array([r["E"], r["N"]])))
                if best is None or dist < best[0]:
                    pr = w["properties"]
                    best = (dist, ab / L, pr.get("objektart"), pr.get("strassenname"), None, None)
    if best is None:
        rows.append({"loc": loc, "name": r["name"], "note": "no street found"})
        continue
    dist, u, hw, wname, bridge, tunnel = best
    p1 = np.array([r["E"], r["N"]]) - 100 * u
    p2 = np.array([r["E"], r["N"]]) + 100 * u
    pf = prof_dir / f"{loc}.json"
    if not pf.exists():
        geom = json.dumps({"type": "LineString", "coordinates": [p1.round(1).tolist(), p2.round(1).tolist()]})
        url = "https://api3.geo.admin.ch/rest/services/profile.json?" + urllib.parse.urlencode(
            {"geom": geom, "sr": 2056, "nb_points": 41})
        pf.write_text(json.dumps(get(url)))
        time.sleep(0.5)
    prof = json.loads(pf.read_text())
    z = np.array([p["alts"].get("DTM2", p["alts"].get("COMB")) for p in prof])
    d = np.array([p["dist"] for p in prof])
    grade = abs(z[-1] - z[0]) / (d[-1] - d[0]) * 100
    max_local = np.max(np.abs(np.diff(z) / np.diff(d))) * 100
    structure = any(k in r["name"].lower() for k in ("brücke", "unterführung", "tunnel")) or bool(bridge) or bool(tunnel)
    rows.append({"loc": loc, "name": r["name"], "street_tlm": wname, "tlm_objektart": hw, "dist_to_street_m": round(dist, 1),
                 "grade_pct": round(grade, 2), "max_local_grade_pct": round(max_local, 1),
                 "elev_min": round(z.min(), 1), "elev_max": round(z.max(), 1), "structure": structure})

s = pd.DataFrame(rows).sort_values("grade_pct", ascending=False)
s.to_csv(root / "data" / "derived" / "counter_slopes.csv", index=False)
pd.set_option("display.width", 220)
print(s.to_string(index=False))
ok = s[~s["structure"].astype(bool)]
for th in (2, 3, 4, 5):
    print(f"non-structure locations with grade >= {th}%: {int((ok['grade_pct'] >= th).sum())} of {len(ok)}")
