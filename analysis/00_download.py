"""Download every raw data file used in this study from the official open-data sources.

The sources are updated daily, so a new download will differ slightly from the version
analysed (24 November 2026). Checksums of that version are in docs/SHA256SUMS*.txt.

Usage: python 00_download.py <project_dir> [--list]
  --list  only print the URLs and check that each one answers (first byte only)
"""
import json
import sys
import urllib.request
from pathlib import Path

root = Path(sys.argv[1])
LIST = "--list" in sys.argv
raw = root / "data" / "raw"
UA = {"User-Agent": "zurich-cycling-weather/1.0 (research download script)"}
SMN = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn"
ZH = "https://data.stadt-zuerich.ch/dataset"

files = {
    "zurich_counts/verkehrszaehlungen_werte_fussgaenger_velo_alle_jahre.parquet":
        f"{ZH}/ted_taz_verkehrszaehlungen_werte_fussgaenger_velo/download/verkehrszaehlungen_werte_fussgaenger_velo_alle_jahre.parquet",
    "zurich_counts/2026_verkehrszaehlungen_werte_fussgaenger_velo.csv":
        f"{ZH}/ted_taz_verkehrszaehlungen_werte_fussgaenger_velo/download/2026_verkehrszaehlungen_werte_fussgaenger_velo.csv",
    "zurich_stations/standorte.geojson":
        "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Standorte_der_automatischen_Fuss__und_Velozaehlungen"
        "?SERVICE=WFS&REQUEST=GetFeature&VERSION=1.1.0&TYPENAME=view_eco_standorte&OUTPUTFORMAT=application/vnd.geo%2Bjson&SRSNAME=EPSG:2056",
    "zurich_holidays/schulferien.csv": f"{ZH}/ssd_schulferien/download/schulferien.csv",
    "zurich_cars/sid_dav_verkehrszaehlung_miv_od2031_alle_jahre.parquet":
        f"{ZH}/sid_dav_verkehrszaehlung_miv_od2031/download/sid_dav_verkehrszaehlung_miv_od2031_alle_jahre.parquet",
    "meteoswiss/ogd-smn_meta_stations.csv": f"{SMN}/ogd-smn_meta_stations.csv",
    "meteoswiss/ogd-smn_meta_parameters.csv": f"{SMN}/ogd-smn_meta_parameters.csv",
    "boundaries/stadtkreise.geojson":
        "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Stadtkreise?SERVICE=WFS&REQUEST=GetFeature&VERSION=1.1.0"
        "&TYPENAME=adm_stadtkreise_a&OUTPUTFORMAT=application/vnd.geo%2Bjson&SRSNAME=EPSG:2056",
    "boundaries/kanton_zh.json":
        "https://api3.geo.admin.ch/rest/services/api/MapServer/find?layer=ch.swisstopo.swissboundaries3d-kanton-flaeche.fill"
        "&searchText=Z%C3%BCrich&searchField=name&returnGeometry=true&geometryFormat=geojson&sr=2056&contains=false",
    "boundaries/zurichsee.json":
        "https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometry=2688000,1238000&geometryType=esriGeometryPoint"
        "&layers=all:ch.bafu.vec25-seen&tolerance=0&mapExtent=2680000,1230000,2700000,1250000&imageDisplay=1000,1000,96"
        "&sr=2056&returnGeometry=true&geometryFormat=geojson",
}
# passenger counts at the VBZ stop Hardbrücke (check added after the results, code/28_pt_hardbruecke.py)
for y in (2024, 2025, 2026):
    files[f"vbz_hardbruecke/frequenzen_hardbruecke_{y}.parquet"] = (
        f"{ZH}/vbz_frequenzen_hardbruecke/download/frequenzen_hardbruecke_{y}.parquet")
for st in ("sma", "reh", "chz", "klo", "lac", "pfa", "scm", "sha", "tae", "wae"):
    parts = ["t_historical_2020-2029", "t_recent"] + ([] if st == "pfa" else ["t_historical_2010-2019"])
    for part in parts:
        files[f"meteoswiss/ogd-smn_{st}_{part}.csv"] = f"{SMN}/{st}/ogd-smn_{st}_{part}.csv"
    if st in ("sma", "reh"):
        for part in ("d_historical", "d_recent"):
            files[f"meteoswiss/ogd-smn_{st}_{part}.csv"] = f"{SMN}/{st}/ogd-smn_{st}_{part}.csv"

# canton bike counts: file links come from the canton's data catalogue (dataset 3062)
cat = json.loads(urllib.request.urlopen(urllib.request.Request("https://www.web.statistik.zh.ch/ogd/daten/zhweb.json", headers=UA), timeout=120).read())
items = cat.get("dataset", cat) if isinstance(cat, dict) else cat
for d in items:
    if d.get("identifier", "").startswith("3062@"):
        for r in d.get("distribution", []):
            url = r.get("downloadUrl")
            if url:
                files[f"canton_counts/{url.rsplit('/', 1)[-1]}"] = url

for rel, url in files.items():
    if LIST:
        try:
            req = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-0"})
            status = urllib.request.urlopen(req, timeout=60).status
        except Exception as e:
            status = f"ERROR {e}"
        print(status, rel)
        continue
    dest = raw / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    print("downloading", rel, flush=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
print(len(files), "files")
