# Plan: forecasting cycling when the weather effect drifts (27 November 2026)

This plan is fixed, with checksums in `docs/FROZEN_SHA256.txt`, before any model in it is trained. It is a companion study to the paper on how the rain effect on cycling in Zurich changed (under review). That paper is cited for the change itself. This study asks what the change does to forecasting models.

## 1. What is already known before this plan

- The rain effect on daytime cycling weakened between 2011 and 2026, most of it by 2017 (main paper).
- Two forecasting results from the earlier forecasting work (`code/10_forecast_trees.py`, `code/14_check_drift_months.py`), on the test period 1 June 2025 to 22 November 2026 and the 11 long-running counters:
  - A LightGBM model trained only on 2011–2015 gave a wet-minus-dry relative error of −0.077 (95% interval −0.130 to −0.020). Compared within the same month and counter, it was −0.057 (−0.100 to +0.005).
  - The model trained on all data up to 31 May 2025 gave +0.014 (−0.035 to +0.070).
- Nothing else in this plan has been computed: no other training window, no other test year and no yearly retraining.

## 2. Question

When the way cyclists respond to rain changes, does a forecasting model that is not retrained go wrong on wet days? How quickly does this happen, and does retraining every year prevent it?

## 3. Data

- The forecasting panel of the earlier work (`data/forecast/panel.parquet`, built by `code/09_forecast_data.py`, unchanged): daily bicycle counts from 6:00 to 20:00, MeteoSwiss weather at Zurich Fluntern, calendar and holidays.
- **Counters:** the 11 long-running city counters (BUCH, HOFW, LANN, LIMC, LUXG, MILI, MUEH, MYTH, SCHE, SIHL, TOED). Each model is evaluated only on counters with at least 200 counted days in its training window.
- **Pandemic years:** 2020 and 2021 are used neither for training nor for testing.
- **Days evaluated:** days with a count and a count 7 days earlier. Light-rain days (0.1 to under 2 mm) are not used in the wet-minus-dry comparison.

## 4. Models

LightGBM exactly as in `code/10_forecast_trees.py`:
- the same settings (500 trees, learning rate 0.05, 31 leaves, at least 50 rows per leaf, seed 2026);
- the same inputs: counter, calendar, holidays, lags of 1, 7 and 14 days, mean of the last 7 counted days, and the observed weather of the day (light rain, wet, highest temperature, sunshine);
- the same target, log(1 + count).

Training strategies:

| Strategy | Training data |
|---|---|
| **Frozen W1** | 2011–2013 |
| **Frozen W2** | 2014–2016 |
| **Frozen W3** | 2017–2019 |
| **Frozen W4** | 2022–2024 |
| **Yearly retrained** | for each test year, all years before it except 2020–2021 |

Each frozen model is trained once and used for every later test year.

**Test years:** 2014–2019 and 2022–2026 (2026 up to 22 November). Each model is tested only on years after its training data.

## 5. Measure

- **Relative error** of a forecast: (forecast − count) / count.
- **Wet-day bias:** the wet-minus-dry difference in relative error, estimated by least squares with a wet-day indicator and fixed effects for calendar month (year and month) and for counter, as in `code/14_check_drift_months.py`. Negative values mean the model under-predicts wet days compared with dry days.
- **Intervals:** bootstrap of test weeks (ISO weeks; 2,000 draws; seed 2026). Differences between strategies are computed on the same resampled weeks.

## 6. Tests and predictions

| # | Test | Prediction |
|---|---|---|
| H1 | Wet-day bias of the frozen W1 and W2 models (pooled) in the test years 2022–2026 | Below zero: the 95% interval lies below 0. |
| H2 | The same frozen models minus the yearly-retrained model, in 2022–2026 | Below zero: the 95% interval lies below 0. |
| H3 | Placebo before the change: frozen W1 minus yearly retrained, in the test years 2014–2016 | No difference: the 95% interval includes 0. |
| H4 | Wet-day bias of the yearly-retrained model in 2022–2026 | No bias: the 95% interval includes 0. |

H1 and H2 are the main tests. H3 checks that being out of date only matters after the rain effect changed. H4 checks that yearly retraining is enough.

## 7. Described, without tests

- The wet-day bias for every pair of frozen window and test year (main figure: bias against the age of the model).
- The forecast error of every strategy relative to "same weekday last week", overall, on wet days and on dry days.
- For comparison, the wet-day bias in the earlier test period (June 2025 to November 2026) of the models already trained in the earlier work: Graph WaveNet, the recurrent network and LightGBM. These were trained on recent years (2022 to April 2025 for the neural networks), and no new neural network is trained.

## 8. Reporting

- All four tests are reported as they come out, whatever the result.
- Anything added after the results is marked as such.
- Output: `results/drift/` and a short working paper, released with the code in the public repository (new version of the Zenodo record).
