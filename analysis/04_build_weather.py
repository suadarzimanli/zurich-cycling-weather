"""Build the daily weather table (weather only, no counts).

Source: MeteoSwiss 10-minute values. Time stamps are UTC and mark the END of each
10-minute interval. Each interval is assigned to local Zurich time by its START.
Daytime = 6:00 to 20:00 local time (84 intervals).

Usage: python 04_build_weather.py <project_dir>
"""
import sys
from pathlib import Path

import pandas as pd

root = Path(sys.argv[1])
raw = root / "data" / "raw" / "meteoswiss"
der = root / "data" / "derived"
der.mkdir(parents=True, exist_ok=True)

out = []
for st in ("sma", "reh"):
    files = [raw / f"ogd-smn_{st}_t_{s}.csv" for s in ("historical_2010-2019", "historical_2020-2029", "recent")]
    w = pd.concat([pd.read_csv(f, sep=";", usecols=["reference_timestamp", "tre200s0", "rre150z0", "sre000z0"]) for f in files])
    w["utc_end"] = pd.to_datetime(w["reference_timestamp"], format="%d.%m.%Y %H:%M")
    w = w.drop_duplicates("utc_end").sort_values("utc_end")
    w["start"] = (w["utc_end"] - pd.Timedelta(minutes=10)).dt.tz_localize("UTC").dt.tz_convert("Europe/Zurich").dt.tz_localize(None)
    w["date"] = w["start"].dt.normalize()
    w["hour"] = w["start"].dt.hour
    day = w[(w["hour"] >= 6) & (w["hour"] < 20)]
    g = day.groupby("date")
    t = pd.DataFrame({
        "rain_n": g["rre150z0"].count(),
        "rain_day": g["rre150z0"].sum(min_count=1),
        "sun_n": g["sre000z0"].count(),
        "sun_day": g["sre000z0"].sum(min_count=1),
    })
    am = day[day["hour"].between(7, 8)].groupby("date")["rre150z0"].agg(["sum", "count"])
    pm = day[day["hour"].between(16, 18)].groupby("date")["rre150z0"].agg(["sum", "count"])
    t["rain_am"] = am["sum"].where(am["count"] == 12)
    t["rain_pm"] = pm["sum"].where(pm["count"] == 18)
    gd = w.groupby("date")["tre200s0"]
    t["tmax"] = gd.max().where(gd.count() >= 130)  # at least 130 of 144 values (90%)
    t["rain_day"] = t["rain_day"].where(t["rain_n"] == 84)
    t["sun_day"] = t["sun_day"].where(t["sun_n"] == 84)
    t = t.drop(columns=["rain_n", "sun_n"])

    dd = pd.concat([pd.read_csv(raw / f"ogd-smn_{st}_d_{s}.csv", sep=";", usecols=["reference_timestamp", "rre150d0", "tre200dx"])
                    for s in ("historical", "recent")])
    dd["date"] = pd.to_datetime(dd["reference_timestamp"], format="%d.%m.%Y %H:%M")
    dd = dd.drop_duplicates("date").set_index("date")
    t = t.join(dd[["rre150d0"]].rename(columns={"rre150d0": "rain_daily_6utc"}), how="left")
    t = t[(t.index >= "2010-01-01") & (t.index <= "2026-11-22")]
    t.columns = [f"{st}_{c}" for c in t.columns]
    out.append(t)
    print(st, "days", len(t), "| missing: rain", int(t[f"{st}_rain_day"].isna().sum()),
          "tmax", int(t[f"{st}_tmax"].isna().sum()), "sun", int(t[f"{st}_sun_day"].isna().sum()))

wd = pd.concat(out, axis=1)
wd.index.name = "date"
wd.reset_index().to_parquet(der / "weather_daily.parquet", index=False)
print("corr Fluntern vs Affoltern: rain", round(wd["sma_rain_day"].corr(wd["reh_rain_day"]), 3),
      "| tmax", round(wd["sma_tmax"].corr(wd["reh_tmax"]), 3))
print(wd.describe().T[["count", "mean", "min", "max"]].round(2).to_string())
