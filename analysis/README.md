# Analysis scripts

Every script takes the repository folder as its only argument, for example `python analysis/03_build_counts.py .`. Scripts 09 to 14 use LightGBM and PyTorch (see `requirements.txt`).

| Script | What it does |
|---|---|
| `00_download.py` | Downloads every raw file from its official source (`--list` only checks the links) |
| `01_inventory.py` | Coverage of the bicycle counts (no weather used) |
| `02_checks.py` | Data quality checks (no weather joined) |
| `03_build_counts.py` | Daily bicycle counts per counter, 6:00 to 20:00, with cleaning flags |
| `04_build_weather.py` | Daily weather from MeteoSwiss ten-minute values (Fluntern, Affoltern) |
| `05_build_calendar.py` | Public and school holidays and local half-days, checked against official dates |
| `fepois.py`, `design.py`, `analysis.py` | Poisson estimator, regressors and period tests |
| `06_validate_fepois.py` | Checks the estimator against statsmodels |
| `07_results.py` | Weather effects by year, the three predictions and the checks |
| `08_figure.py` | Figure of the weather effects by year |
| `09_forecast_data.py` | Panel for forecasting |
| `10_forecast_trees.py` | "Same weekday last week", LightGBM and the drift test |
| `11_forecast_gnn.py` | One Graph WaveNet or RNN run: `python analysis/11_forecast_gnn.py . gwn wx 1 2` |
| `12_forecast_scores.py` | Combines the runs and scores all forecasting models |
| `13_check_devices.py`, `15_check_2018_2019.py` | Checks added after the results: counter replacements and the year 2019 |
| `14_check_drift_months.py` | Check added after the results: drift test within month and location |
| `16_inventory_new.py`, `18_inventory_canton.py` | Coverage of pedestrian, car and canton counts (no weather used) |
| `17_slopes.py` | Street slope at each bicycle counter (geometry only) |
| `19_weather_stations.py` | Daily weather for all stations of the extended plan |
| `20_build_extended.py` | Daily pedestrian, car and canton tables |
| `blockpois.py`, `21_validate_blockpois.py` | Estimator for large panels and its check against `fepois.py` |
| `22_extended_results.py` | Questions 1 to 4 of the extended plan, with checks |
| `23_paper_figures.py` | Map and the three-mode figure |
| `25_export_app_data.py` | Data files for the web app in `docs/data` |
| `26_review_checks.py`, `27_review_check_typical_day.py` | Checks added after the results: did wet days get milder, rain intensity, rain hours and commute rain, wind, clustering by month |
| `28_pt_hardbruecke.py` | Check added after the results: public transport flows at the stop Hardbrücke on wet days, with the two Hardbrücke bicycle counters |
| `29_route_type.py` | Check added after the results, rule fixed in `plans/CHECK_ROUTE_TYPE_2026-11-25.md` before it was run: rain trend on commuter-type and leisure-type routes |
| `30_route_type_followup.py` | Diagnostics run after seeing the result of `29_route_type.py`: one location dropped at a time, weekend ratio by period |
| `31_route_type_proportional.py` | Check added after the results, rule fixed in `plans/CHECK_OFFPEAK_PROPORTIONAL_2026-11-25.md` before it was run: the route-type gap in proportional terms |
| `32_cars_offpeak.py` | Check added after the results, same rule file: car traffic on wet days outside the peak hours and in the rush hours |
| `33_descriptive_levels.py` | Descriptive table: cyclists per counter on all, dry and wet days, 2011–2014 and 2022–2026, at the nine locations of the period design |
