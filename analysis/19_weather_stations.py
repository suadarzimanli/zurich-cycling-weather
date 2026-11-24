"""Daily weather for every station used in the extended plan (same rules as 04_build_weather.py).

Output: data/derived/weather_stations_daily.parquet (station, date, rain_day, tmax, sun_day)
Usage: python 19_weather_stations.py <project_dir>
"""
import sys
from pathlib import Path

import pandas as pd

root = Path(sys.argv[1])
raw = root / "data" / "raw" / "meteoswiss"
out = []
for st in ("sma", "reh", "chz", "klo", "lac", "pfa", "scm", "sha", "tae", "wae"):
    files = [f for f in (raw / f"ogd-smn_{st}_t_{s}.csv" for s in ("historical_2010-2019", "historical_2020-2029", "recent")) if f.exists()]
    w = pd.concat([pd.read_csv(f, sep=";", usecols=["reference_timestamp", "tre200s0", "rre150z0", "sre000z0"]) for f in files])
    w["utc_end"] = pd.to_datetime(w["reference_timestamp"], format="%d.%m.%Y %H:%M")
    w = w.drop_duplicates("utc_end")
    w["start"] = (w["utc_end"] - pd.Timedelta(minutes=10)).dt.tz_localize("UTC").dt.tz_convert("Europe/Zurich").dt.tz_localize(None)
    w["date"] = w["start"].dt.normalize()
    h = w["start"].dt.hour
    day = w[(h >= 6) & (h < 20)].groupby("date")
    t = pd.DataFrame({"rain_day": day["rre150z0"].sum(min_count=1).where(day["rre150z0"].count() == 84),
                      "sun_day": day["sre000z0"].sum(min_count=1).where(day["sre000z0"].count() == 84)})
    g = w.groupby("date")["tre200s0"]
    t["tmax"] = g.max().where(g.count() >= 130)
    t = t[(t.index >= "2010-01-01") & (t.index <= "2026-11-22")].reset_index()
    t["station"] = st.upper()
    out.append(t)
    print(st.upper(), "files", len(files), "| days", len(t), "| first", t["date"].min().date(),
          "| complete days", int(t[["rain_day", "tmax", "sun_day"]].notna().all(axis=1).sum()))
pd.concat(out, ignore_index=True).to_parquet(root / "data" / "derived" / "weather_stations_daily.parquet", index=False)
