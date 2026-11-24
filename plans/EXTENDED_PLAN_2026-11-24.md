# Is cycling in Zurich becoming weather-proof? Extended plan (version 2, 24 November 2026)

This plan extends the first plan (`PLAN_2026-11-24.md`) and its details (`ANALYSIS_DETAILS_2026-11-24.md`). Everything not changed here stays as fixed there.

## What is already known, and what is not

- **Already estimated and seen:**
  - the three original predictions on the 9 city locations
  - the weather effects by year for all city bike counters
  - the forecasting results.
- **Not yet estimated:** any weather effect on pedestrians, cars or canton bike counters. For these, only coverage and data quality were checked (scripts `16_inventory_new.py` and `18_inventory_canton.py`).
- **Geometry only:** street slopes were measured at the bike counters (script `17_slopes.py`). No counts or weather were used.

## Questions

1. **Has cycling become less sensitive to weather?** All 33 city bike locations, each compared with itself over time. This makes the first result more precise. It is not a new blind test, because the yearly effects for all locations have already been seen.
2. **Is the change specific to cycling?** Cycling is compared with walking at the city's pedestrian counters. If walking did not change in the same way, the cause lies in cycling itself (e-bikes, bike lanes), not in general habits (home office, weather apps).
3. **Is the change larger in the suburbs?** E-bikes help most on longer trips, which are more common outside the city. Canton counters (outside the city of Zurich) are compared with city counters. This question is **exploratory**, because only 9 canton stations have data before 2020.
4. **Do fewer people switch to the car on rainy days than before?** The same analysis is run on the city's car counts.

## Dropped, and why

- **Hills test:** almost all city bike counters are on flat streets along the lake, the rivers and the valley floor. Only one location (Scheuchzerstrasse, about 3.5%) is clearly on a slope. Near railway embankments and underpasses the terrain model also gives false slopes. The test cannot be done with these counters.
- **Speed data:** this would need a data request to the city.

## Data

| Data | Coverage | Used for |
|---|---|---|
| City bike counts | 33 locations, 2011 to 22 Nov 2026 | Questions 1 to 3 |
| City pedestrian counts | Pedestrian-only sites, about 10 to 16 per year, 2014 to 2022. Most were switched off in 2022 and 2023 | Question 2 |
| Canton bike counts (Tiefbauamt Kanton Zürich, hourly) | 101 stations, 2016 to 2025. Only 9 have good data both in 2016–2019 and in 2022–2025 | Question 3 |
| City car counts (hourly, by measuring point) | 224 points, 2012 to 2026. 134 points have good data both in 2012–2014 and in 2022–2025 | Question 4 |
| Weather (MeteoSwiss, 10-minute values) | Fluntern for all city data. For each canton station: the nearest station below 650 m altitude (Cham, Hallau, Kloten, Lachen, Pfäffikon ZH, Affoltern, Schmerikon, Schaffhausen, Fluntern, Steckborn, Tänikon or Wädenswil) | All questions |

**Pedestrian sites used:** only sites without a bike counter at the same place, because pedestrian sensors there may also count cyclists. The excluded sites are Langstrasse Unterführung Nord and Süd, Mythenquai Unterführung, Militärbrücke, Limmatquai and Kloster-Fahr-Weg (Europabrücke).

**Car counts:** only hours marked as measured are used. Hours that are missing or imputed (filled in from past averages, so they carry no weather information) are left out. A day is used only if all 14 hours from 6:00 to 20:00 were measured.

## Model

The model is the same as in the first plan for every data source:
- Poisson regression on daytime counts (6:00 to 20:00)
- one fixed effect per counter and calendar month
- one level per counter and weekday
- public holidays, school holidays and the two local half-days
- the same weather terms (light rain, wet day, temperature slopes, sunshine)
- the same cleaning rule
- standard errors clustered by week.

Where two data sources are compared, they are **estimated together in one model** (each with its own terms), so that the comparison accounts for sharing the same weather days.

**The change over time is measured as a straight-line trend per decade.** Each counter keeps its own weather effect, and a common trend tells how much the effect changed per 10 years. The pandemic years 2020 and 2021 are left out.

## Tests

| Question | Data and years | What is estimated | Prediction | Supported if |
|---|---|---|---|---|
| 1 | All city bike locations, 2011–2026 | Trend per decade in the wet-day, cold and heat effects | The wet-day effect weakens (positive trend) | Trend > 0 and its 95% interval excludes zero |
| 2 | City bikes and pedestrian-only sites, 2014–2022 | Cycling trend minus walking trend in the wet-day effect | Cycling's rain effect weakened more than walking's | Difference > 0 and its 95% interval excludes zero |
| 3 (exploratory) | Canton and city bikes, 2017–2025 | Canton trend minus city trend in the wet-day effect | The weakening is larger in the canton | Reported as exploratory in any case |
| 4a | 134 car measuring points, 2012–2014 against 2022–2026 | Wet-day effect on car traffic in each period | Car traffic is higher on wet days than dry days in 2012–2014 | Early effect > 0 and its 95% interval excludes zero |
| 4b | Same | Late minus early wet-day effect on cars | The rise in car traffic on wet days became smaller | Change < 0 and its 95% interval excludes zero |

**Checks:**
- weather from Affoltern instead of Fluntern for the city data
- no cleaning rule
- for question 4, all car measuring points with a trend per decade instead of the two periods.

**What this can and cannot show:**
- The questions together describe the change and test where it comes from. They still cannot prove the cause.
- Question 2 has limited data, because most pedestrian counters stopped in 2022 or 2023.
- Question 3 has limited early data.
- All results are reported, including results that do not support the predictions.

## Outputs and timeline

- **Main paper:** a full journal paper (questions 1 to 4).
- **Short separate paper:** the forecasting results, for Cesare Alippi.
- **Order:** this plan is locked now. The analysis runs after the JPR submission on 15 December, unless you decide otherwise.

## Sources (new in this version)

- City of Zurich car counts (hourly, since 2012): https://data.stadt-zuerich.ch/dataset/sid_dav_verkehrszaehlung_miv_od2031
- Canton of Zurich bike counts (Tiefbauamt, hourly, since 2016), dataset 3062 in the canton's data catalogue: https://www.zh.ch/de/politik-staat/statistik-daten/datenkatalog.html#/datasets/3062@tiefbauamt-kanton-zuerich
- Canton page on bike count data: https://www.zh.ch/de/mobilitaet/veloverkehr/veloverkehrsplanung/datenrundlagen-veloverkehr.html
- swisstopo swissTLM3D roads and swissALTI3D elevation profiles (geo.admin.ch services): https://api3.geo.admin.ch/
