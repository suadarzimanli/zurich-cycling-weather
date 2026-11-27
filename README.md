# Is cycling in Zurich becoming weather-proof?

Fifteen years of open bicycle, pedestrian and car counts from Zurich, Switzerland, joined with ten-minute weather records. The study asks whether rain, cold and heat still keep people off their bicycles as much as they used to, whether the change is specific to cycling, and what happens to car traffic on rainy days.

**Web app:** https://suadarzimanli.github.io/zurich-cycling-weather/
**Paper:** preprint coming soon

## Key results

| Question | Result |
|---|---|
| Has cycling become less sensitive to rain? | Yes. At the 9 city counters observed in both periods, a wet day cut daytime cycling by **33%** in 2011–2014 and by **29%** in 2022–2026 (change +0.068 log points, 95% CI +0.021 to +0.115). Across all 33 counters the drop shrank by about **4 percentage points per decade** on average, most of it by 2017. |
| How much did cycling grow? | At the same 9 counters, daytime cycling grew by **81%** (613 to 1,110 cyclists per counter and day), and cycling on wet days roughly **doubled** (389 to 789). Simple averages, `analysis/33_descriptive_levels.py`. |
| Is the change specific to cycling? | Yes. Over 2014–2022, walking did not become less sensitive to rain (cycling minus walking +0.129 log points per decade, 95% CI +0.049 to +0.208). |
| Do e-bikes explain it? | Not on this evidence. Cold and heat effects did not shrink more than the rain effect, and the change is not larger at the canton counters outside the city. |
| Do rainy days bring more cars? | No. Car traffic is about **1.5% lower** on wet days, and this has not changed since 2012. It does not rise outside the peak hours either (check added after the results). |
| Where did the change happen? | Check added after the results: mostly on routes with much weekend traffic (rain effect weakening +0.108 log points per decade, against +0.038 on commuter-type routes, difference 95% CI -0.094 to -0.046). The gap also holds in proportional terms. |
| What happens to public transport on wet days? | Check added after the results, one stop (Hardbrücke, 2024–2026): tram and bus flows +1.2% (95% CI -0.3% to +2.6%) while cycling on the same bridge falls by 25%. |
| Can tomorrow's bike traffic be forecast? | A graph neural network (Graph WaveNet) has 59% less error than "same weekday last week" when tomorrow's weather is known, and 24% less error than the same network without the counter graph. |

Rain still removes almost a third of daytime cycling in Zurich. The decline in rain sensitivity is real and specific to cycling, but it is slow.

## Data

All data are open. Nothing is redistributed here except derived results. `analysis/00_download.py` fetches every raw file from its official source.

| Data | Source | Licence |
|---|---|---|
| Bicycle and pedestrian counts, 15-minute values, 2009–2026 | [City of Zurich, Tiefbauamt](https://data.stadt-zuerich.ch/dataset/ted_taz_verkehrszaehlungen_werte_fussgaenger_velo) | CC0 |
| Car counts, hourly, 2012–2026 | [City of Zurich, Dienstabteilung Verkehr](https://data.stadt-zuerich.ch/dataset/sid_dav_verkehrszaehlung_miv_od2031) | CC0 |
| Canton bicycle counts, hourly, 2016–2025 | [Tiefbauamt Kanton Zürich](https://www.zh.ch/de/politik-staat/statistik-daten/datenkatalog.html#/datasets/3062@tiefbauamt-kanton-zuerich) | Open government data |
| Weather, ten-minute values | [MeteoSwiss](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a1-automatic-weather-stations) | Open use, source: MeteoSwiss |
| Passenger counts at the stop Hardbrücke, 5-minute values, 2024–2026 | [City of Zurich, VBZ](https://data.stadt-zuerich.ch/dataset/vbz_frequenzen_hardbruecke) | CC0 |
| School holidays | [City of Zurich, Schulamt](https://data.stadt-zuerich.ch/dataset/ssd_schulferien) | CC0 |
| Boundaries, roads, elevation | [swisstopo](https://api3.geo.admin.ch/) and City of Zurich | Open use |

The data were downloaded on 24 November 2026, and the Hardbrücke passenger counts on 25 November 2026. The sources are updated daily, so a new download will differ slightly. Checksums of the analysed version are in `plans/SHA256SUMS.txt` and `plans/SHA256SUMS_extended.txt`.

## Method in short

Daily counts between 6:00 and 20:00 are modelled with Poisson regression. Each counter is compared with itself within the same calendar month, with separate levels for each weekday and for holidays, so the weather effect comes from day-to-day changes in weather. Standard errors are clustered by week. Change over time is measured in two ways: two periods (2011–2014 against 2022–2026) at the same 9 locations, and a linear trend per decade with each counter keeping its own weather effect.

**Plans fixed in advance.** The research plan, the predictions and the exact tests were written down and locked with SHA-256 checksums before the counts were joined with the weather (`plans/FROZEN_SHA256.txt`). This was done in two stages: the first plan before any weather effect was estimated, and an extended plan before any weather effect on pedestrians, cars or canton counters was estimated. The plans were not registered on a public platform, so the time stamps are self-recorded. Checks added after the results are labelled as such in `results/`.

## Repository layout

| Folder | Contents |
|---|---|
| `docs/` | The web app (served by GitHub Pages) |
| `analysis/` | Every script, in the order they were run (see `analysis/README.md`) |
| `plans/` | The locked plans, the exact test definitions and all checksums |
| `results/` | Results summaries, tables (JSON and CSV), figures and forecasts |
| `tests/` | Automated check of the web app in Microsoft Edge |

## Run the web app

No build step. Serve the `docs` folder over HTTP (browsers block `fetch` from `file://`):

```bash
cd docs
python -m http.server 8000        # then open http://localhost:8000
```

On Windows you can double-click `run_local.bat` (macOS and Linux: `./run_local.sh`).

## Reproduce the analysis

Python 3.12 or newer with the packages in `requirements.txt`. The forecasting networks need PyTorch 2.12 (CPU is enough) with `torch_scatter` and `torch_sparse`, plus Torch Spatiotemporal. All scripts take the repository folder as their only argument:

```bash
python analysis/00_download.py .
python analysis/03_build_counts.py .
python analysis/04_build_weather.py .
python analysis/05_build_calendar.py .
python analysis/07_results.py .
# ... see analysis/README.md for the full order
```

The six Graph WaveNet runs take 45 to 100 minutes each on a CPU. Their outputs are included in `results/forecast/runs/`, so the scoring script can be run without retraining.

## Licence and citation

Code: MIT licence (see `LICENSE`). Derived results: CC BY 4.0. The underlying data keep the licences of their sources listed above.

Please cite the repository as: Arzimanli, S. (2026). *Zurich cycling and weather: code, data and web app for a fifteen-year study of rain and bicycle, pedestrian and car counts*. Zenodo. https://doi.org/10.5281/zenodo.24589808 (this DOI always points to the latest version; details in `CITATION.cff`).

## Author

Suad Arzimanli, University of Łódź.
