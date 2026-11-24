# Results of the extended plan (24 November 2026)

All definitions are those locked in `docs/EXTENDED_PLAN_2026-11-24.md` before any weather effect on pedestrians, cars or canton counters was estimated. Code: `code/19` to `code/22`. Full output: `results/extended/extended_run.log` and `extended_results.json`.

The estimator for this larger data (`code/blockpois.py`) was first checked against the validated estimator. Coefficients agreed to about 1e-15 and standard errors to about 1e-13 (`code/21_validate_blockpois.py`).

## Short answer

- Cycling in Zurich has become **less sensitive to rain**, and this is **specific to cycling**. Walking did not become less sensitive to rain.
- The change is **not larger in the suburbs**, which does not fit the idea that e-bikes on longer trips are the main driver.
- **Rainy days do not push people into cars.** Car traffic is slightly lower on wet days, and this has not changed since 2012.

## Results

Effects are in log points. A wet-day effect of −0.40 means about 33% fewer trips than on a dry day. A trend of +0.06 per decade means the drop on wet days shrinks by about 4 percentage points every ten years.

| Question | Result | Prediction supported? |
|---|---|---|
| 1. Has cycling become less sensitive to weather? (33 city locations, 2011–2026, not a blind test) | Wet-day effect weakens by **+0.060 per decade** (95% interval +0.022 to +0.098). No clear trend for cold (−0.002) or heat (−0.005) | **Yes** (rain) |
| 2. Is the change specific to cycling? (city bikes and 18 pedestrian-only sites, 2014–2022) | Cycling +0.072 per decade, walking −0.057 per decade. **Difference +0.129** (interval +0.049 to +0.208) | **Yes** |
| 3. Is the change larger in the suburbs? (101 canton stations and city bikes, 2017–2025, exploratory) | Canton −0.095, city +0.016 per decade. Difference −0.111 (interval −0.226 to +0.004). The suburbs show, if anything, less weakening | **No** (exploratory) |
| 4a. Is car traffic higher on wet days? (134 car measuring points) | Wet-day effect on cars in 2012–2014: **−0.015** (interval −0.028 to −0.002). Car traffic is about 1.5% *lower* on wet days | **No** |
| 4b. Did the wet-day rise in car traffic become smaller? | 2022–2026: −0.014. Change +0.001 (interval −0.014 to +0.016). No change | **No** |

## Checks

| Check | Question 1 (rain trend) | Question 2 (difference) | Question 3 (difference) | Question 4 (change) |
|---|---|---|---|---|
| Main | +0.060 [+0.022, +0.098] | +0.129 [+0.049, +0.208] | −0.111 [−0.226, +0.004] | +0.001 [−0.014, +0.016] |
| Weather from Affoltern | +0.079 [+0.041, +0.118] | +0.134 [+0.050, +0.218] | (not run, canton uses local stations) | −0.011 [−0.025, +0.004] |
| No cleaning rule | +0.062 [+0.024, +0.101] | +0.136 [+0.058, +0.215] | −0.119 [−0.235, −0.003] | +0.001 [−0.014, +0.016] |
| All 224 car points, trend per decade | | | | −0.001 [−0.012, +0.011] |

Every check agrees with the main result. With Affoltern weather, the early wet-day effect on cars is smaller and no longer clearly below zero (−0.004, interval −0.016 to +0.009), but it is still not positive.

## Data notes

- **Canton weather:** the nearest station below 650 m with complete weather that day. On 86% of canton days this is the nearest station. Pfäffikon ZH has 10-minute data only from December 2022. Cham, Lachen and Schmerikon lack sunshine or temperature, so the next station is used.
- **Pedestrians:** 18 pedestrian-only sites. Most stopped in 2022 or 2023, so question 2 covers 2014–2022 (without 2020 and 2021).
- **Cars:** only measured hours. Imputed and missing hours were left out.

## What the results mean together

- **Q1 and Q2:** the weakening of the rain effect is real and specific to cycling.
- **Q3:** the weakening does not concentrate in the suburbs, where e-bikes matter most for longer trips. Together with the earlier result that cold and heat did not change more than rain, the evidence does not point to e-bikes as the main driver.
- **Other explanations:** better city bike infrastructure, more committed everyday cyclists, or better rain clothing remain possible. They cannot be separated with these data.
- **Q4:** on rainy days, people who do not cycle are not visible as extra car traffic. They probably use public transport or skip the trip. This did not change over 15 years. For a cycling city such as E-Bike City, this suggests that rainy days are mainly a public-transport question, not a car question.
