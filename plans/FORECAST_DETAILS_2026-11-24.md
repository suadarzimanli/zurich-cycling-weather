# Forecasting details fixed before any forecast is made (24 November 2026)

These details make section 6 of the plan exact. They were written before any forecasting model was trained.

## Data

- **Series:** one series per location. The value is the cleaned daytime count (6:00 to 20:00) from `counts_daily.parquet`. Days that are missing or flagged stay missing.
- **Locations:** those with at least 300 usable days in the test period.
- **Test period:** 1 June 2025 to 22 November 2026.
- **Training:**
  - **Tree model:** all data up to 31 May 2025.
  - **Neural networks:** they train on 1 January 2022 to 30 April 2025, use May 2025 for early stopping, and see no test data.
- **Forecast:** made at the end of day t for day t+1.
- **Evaluation set:** target days where the actual value and the value seven days earlier both exist. All models are scored on the same set.

## Models

1. **Last week:** the value of the same location seven days earlier.
2. **LightGBM:** fixed settings with no tuning (500 trees, learning rate 0.05, 31 leaves, at least 50 rows per leaf). It is trained on log(1 + count).
   - **Features:** location, weekday, month, the four holiday terms, the counts 1, 7 and 14 days earlier, and the mean of the last 7 available days.
3. **Graph neural network:** Graph WaveNet from Torch Spatiotemporal.
   - **Graph:** locations are linked by straight-line distance, with a Gaussian kernel and the 5 nearest neighbours.
   - **Inputs:** 28 days of history, calendar and holiday inputs, and the weather inputs. Counts are scaled per location (log, then standardized on training data).
   - **Training:** absolute-error loss, Adam with learning rate 0.001, at most 200 epochs, and early stopping with patience 20.
4. **Same network without the graph:** a recurrent model (RNN) from Torch Spatiotemporal with the same inputs. Comparing 3 and 4 shows whether the graph itself helps.

Models 3 and 4 are trained with three seeds (1, 2, 3). Their reported forecast is the mean over the seeds.

## Weather versions

- **Best case:** the observed weather of the target day, four inputs: light rain, wet day, highest temperature and sunshine (6:00 to 20:00).
- **Worst case:** no weather of the target day.

Every model except "last week" is run in both versions.

## Scoring

- **Main score:** the mean absolute error of each model divided by that of "last week", pooled over all locations and days.
- **Statistical test:** a Diebold–Mariano test on the daily mean absolute error difference against "last week", with Newey–West standard errors (7 lags).
- **Graph test:** the same test for Graph WaveNet against the network without the graph.

## Drift test (link to the main question)

- **Two models:** LightGBM in the best-case weather version, trained once on 2011–2015 only and once on all data up to 31 May 2025.
- **Locations:** those present in both training periods and in the test period.
- **Prediction:** if rain now hurts traffic less, the old model under-predicts wet days more than dry days.
- **Measure:** the mean of (forecast − actual) / actual on wet days minus the same on dry days. Its interval comes from a bootstrap of test weeks (2,000 draws, seed 2026).

## Addendum (24 November 2026, before any neural network result)

Two settings were added after test runs that showed only training speed and a data problem, not any forecast result:

1. **Graph WaveNet size.** With the library defaults the model only sees the last 13 days, so most of the 28-day window is unused, and it trains very slowly on a CPU. We use 5 layers with gaps of 1, 2, 4, 8 and 16 days, which covers 32 days. The hidden size is 32 and the output layer size is 64. All other settings are library defaults. The RNN keeps the library defaults. Both use batches of 32.
2. **Scaling for a new counter.** Stadttunnel Süd started on 6 May 2025, so it has no data in the training period. For any location with fewer than 30 training days, the scaling uses all data before the test period (up to 31 May 2025). No test data is used.
