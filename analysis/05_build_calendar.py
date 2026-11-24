"""Build the daily calendar: public holidays, school holidays, local half-days.

Rules (City of Zurich):
  School holidays: sports weeks 7-8, spring weeks 17-18 (16-17 if Easter Monday is in
  week 16), summer weeks 29-33, autumn weeks 41-42, Christmas two weeks from the first
  Monday on or after 20 December. Maundy Thursday and the Friday after Ascension are
  school-free days.
  Sechselaeuten: third Monday of April. Second Monday if the third is in Holy Week or
  inside the spring school holidays. Fourth Monday if the third is Easter Monday.
  Knabenschiessen: Monday after the second Sunday of September.
The rules are checked against the official school holiday file (2018 onwards) and,
for 2011-2018, against dates listed on schulferien.org.

Usage: python 05_build_calendar.py <project_dir>
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

root = Path(sys.argv[1])
raw = root / "data" / "raw" / "zurich_holidays"
der = root / "data" / "derived"
der.mkdir(parents=True, exist_ok=True)


def easter(y):
    a = y % 19; b = y // 100; c = y % 100; d = b // 4; e = b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3; h = (19 * a + b - d - g + 15) % 30
    i = c // 4; k = c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(y, month, day)


def iso_week_monday(y, w):
    return date.fromisocalendar(y, w, 1)


def weeks(y, w1, w2):
    s = iso_week_monday(y, w1)
    e = iso_week_monday(y, w2) + timedelta(days=4)  # Friday of the last week
    return {s + timedelta(days=i) for i in range((e - s).days + 1)}


def span(s, e):
    return {s + timedelta(days=i) for i in range((e - s).days + 1)}


def spring_weeks(y):
    em = easter(y) + timedelta(days=1)
    return (16, 17) if em.isocalendar()[1] == 16 else (17, 18)


pub, school, sechs, knab = set(), set(), set(), set()
school_parts = {}
for y in range(2009, 2028):
    e = easter(y)
    pub |= {date(y, 1, 1), date(y, 1, 2), e - timedelta(days=2), e + timedelta(days=1), date(y, 5, 1),
            e + timedelta(days=39), e + timedelta(days=50), date(y, 8, 1), date(y, 12, 25), date(y, 12, 26)}
    sp = spring_weeks(y)
    parts = {
        "Sport": weeks(y, 7, 8),
        "Fruehling": weeks(y, *sp),
        "Sommer": weeks(y, 29, 33),
        "Herbst": weeks(y, 41, 42),
    }
    xs = date(y, 12, 20)
    xs = xs + timedelta(days=(7 - xs.weekday()) % 7)  # first Monday on or after 20 Dec
    parts["Weihnacht"] = span(xs, xs + timedelta(days=11))  # Monday to Friday of the next week
    school_parts[y] = parts
    for p in parts.values():
        school |= p
    school |= {e - timedelta(days=3), e + timedelta(days=40)}  # Maundy Thursday, Friday after Ascension
    # Sechselaeuten
    aprm = [date(y, 4, d) for d in range(1, 31) if date(y, 4, d).weekday() == 0]
    third = aprm[2]
    holy_week = span(e - timedelta(days=6), e - timedelta(days=1))
    if third == e + timedelta(days=1):
        s6 = aprm[3]
    elif third in holy_week or third in parts["Fruehling"]:
        s6 = aprm[1]
    else:
        s6 = third
    sechs.add(s6)
    # Knabenschiessen: Monday after the second Sunday of September
    sun = [date(y, 9, d) for d in range(1, 31) if date(y, 9, d).weekday() == 6]
    knab.add(sun[1] + timedelta(days=1))

# ---- check against the official file (school years from August 2018) ----
h = pd.read_csv(raw / "schulferien.csv")
h["s"] = pd.to_datetime(h["start_date"].str[:10]).dt.date  # stored as local midnight with a 'Z' label
h["e"] = pd.to_datetime(h["end_date"].str[:10]).dt.date    # end is exclusive
problems = 0
key = {"Sportferien": "Sport", "Frühlingsferien": "Fruehling", "Sommerferien": "Sommer", "Herbstferien": "Herbst", "Weihnachtsferien": "Weihnacht"}
for _, r in h.iterrows():
    part = next((v for k, v in key.items() if k in r["summary"]), None)
    if part is None or r["s"].year > 2026:
        continue
    official = {d for d in span(r["s"], r["e"] - timedelta(days=1)) if d.weekday() < 5}
    official -= pub  # public holidays are coded separately
    y = r["s"].year
    rule = {d for d in school_parts[y][part] if d.weekday() < 5}
    if part == "Sommer" and r["s"] == date(2018, 8, 1):
        rule = {d for d in rule if d >= date(2018, 8, 1)}  # file starts in August 2018
    extra_official = official - rule - school
    missing = {d for d in rule if d not in official and not (r["s"] <= d < r["e"])}
    if part == "Fruehling":
        # spring entries in the file sometimes start on Maundy Thursday
        extra_official -= {easter(y) - timedelta(days=3)}
    if extra_official or missing:
        problems += 1
        print("MISMATCH", r["summary"], r["s"], r["e"], "| official not in rule:", sorted(extra_official), "| rule not in official:", sorted(missing))
print("school holiday periods checked against official file, mismatches:", problems)

for name, s, lab in (("Sechseläuten", sechs, "Sechseläuten"), ("Knabenschiessen", knab, "Knabenschiessen")):
    off = sorted({d for d, t in zip(h["s"], h["summary"]) if lab in t and d.year <= 2026})
    mine = sorted(d for d in s if 2018 <= d.year <= 2026 and d >= date(2018, 8, 1))
    off = [d for d in off if d >= date(2018, 8, 1)]
    print(name, "official", [str(d) for d in off], "| rule", [str(d) for d in mine], "| equal:", off == mine)

# Sechselaeuten: the "avoid the spring holidays" clause is optional. It was used in 2015
# (13 April, confirmed by SRF's broadcast) but not in 2026 (20 April, official file).
# So: rule dates up to 2018 (2014 and 2015 confirmed), official dates from 2019.
# 2020 was cancelled (pandemic) and is not in the official file, so it gets no date.
off_sechs = {d for d, t in zip(h["s"], h["summary"]) if "Sechseläuten" in t and 2019 <= d.year <= 2026}
sechs = {d for d in sechs if d.year <= 2018} | off_sechs
assert date(2014, 4, 28) in sechs and date(2015, 4, 13) in sechs and date(2026, 4, 20) in sechs
assert not any(d.year == 2020 for d in sechs)

# public holidays check against the official file
pub_names = ["Neujahrstag", "Berchtoldstag", "Karfreitag", "Ostermontag", "Tag der Arbeit", "Auffahrt",
             "Pfingstmontag", "Nationalfeiertag", "Weihnachten", "Stephanstag"]
offpub = {d for d, t in zip(h["s"], h["summary"]) if t in pub_names and d.year <= 2026}
print("official public holidays (2018-2026) not in rule:", sorted(offpub - pub))

# ---- check 2011-2018 against schulferien.org (third-party; ranges include weekends) ----
ext = {
    "Sport": {2011: ("2011-02-12", "2011-02-27"), 2012: ("2012-02-11", "2012-02-26"), 2013: ("2013-02-11", "2013-02-23"),
              2014: ("2014-02-10", "2014-02-23"), 2015: ("2015-02-07", "2015-02-22"), 2016: ("2016-02-13", "2016-02-28")},
    "Fruehling": {2011: ("2011-04-25", "2011-05-08"), 2012: ("2012-04-21", "2012-05-06"), 2013: ("2013-04-22", "2013-05-04"),
                  2014: ("2014-04-21", "2014-05-04"), 2015: ("2015-04-18", "2015-05-03"), 2016: ("2016-04-23", "2016-05-08"),
                  2017: ("2017-04-15", "2017-04-30"), 2018: ("2018-04-21", "2018-05-06")},
    "Sommer": {2011: ("2011-07-17", "2011-08-21"), 2012: ("2012-07-14", "2012-08-19"), 2013: ("2013-07-15", "2013-08-17"),
               2014: ("2014-07-14", "2014-08-17"), 2015: ("2015-07-11", "2015-08-16"), 2016: ("2016-07-16", "2016-08-21"),
               2017: ("2017-07-15", "2017-08-20"), 2018: ("2018-07-14", "2018-08-19")},
    "Herbst": {2011: ("2011-10-08", "2011-10-23"), 2012: ("2012-10-06", "2012-10-21"), 2013: ("2013-10-07", "2013-10-19"),
               2014: ("2014-10-06", "2014-10-18"), 2015: ("2015-10-03", "2015-10-18"), 2016: ("2016-10-08", "2016-10-23"),
               2017: ("2017-10-07", "2017-10-22"), 2018: ("2018-10-08", "2018-10-20")},
}
bad = 0
for part, yrs in ext.items():
    for y, (s, e) in yrs.items():
        other = {d for d in span(date.fromisoformat(s), date.fromisoformat(e)) if d.weekday() < 5} - pub
        rule = {d for d in school_parts[y][part] if d.weekday() < 5} - pub
        if other != rule:
            bad += 1
            print("THIRD-PARTY MISMATCH", part, y, "| other only:", sorted(other - rule), "| rule only:", sorted(rule - other))
print("2011-2018 periods checked against schulferien.org:", sum(len(v) for v in ext.values()), "| mismatches:", bad)

# ---- output ----
days = pd.date_range("2010-01-01", "2026-12-31", freq="D")
cal = pd.DataFrame({"date": days})
dd = cal["date"].dt.date
cal["public_holiday"] = dd.isin(pub)
cal["school_holiday"] = dd.isin(school) & ~cal["public_holiday"]
cal["sechselaeuten"] = dd.isin(sechs)
cal["knabenschiessen"] = dd.isin(knab)
cal["dow"] = cal["date"].dt.dayofweek
cal.to_parquet(der / "calendar_daily.parquet", index=False)
print("Sechseläuten used:", [str(d) for d in sorted(sechs) if 2011 <= d.year <= 2026])
print("calendar days", len(cal), "| public holidays", int(cal["public_holiday"].sum()), "| school-holiday days", int(cal["school_holiday"].sum()))
