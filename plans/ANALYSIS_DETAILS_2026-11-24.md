# Analysis details fixed before estimation (24 November 2026)

These details make the plan (`PLAN_2026-11-24.md`) exact where it left room for choice. They were written before counts and weather were joined.

## Model

- **Fixed-effect groups:** one group per counter device and calendar month. A group with zero bikes on all its days is dropped.
- **Other terms:**
  - one dummy per location and weekday (Monday is the reference)
  - public holiday, school holiday, Sechseläuten and Knabenschiessen.
- **Weather terms,** each estimated separately for every year from 2011 to 2026:
  - light rain (0.1 to under 2 mm) and wet day (2 mm or more), with dry days as the reference
  - temperature as four slopes: below 5 °C, 5 to 15 °C, 15 to 25 °C and above 25 °C, using the daily highest temperature
  - sunshine in hours (6:00 to 20:00).
- **Estimation:** Poisson maximum likelihood with the group effects concentrated out.
- **Standard errors:**
  - clustered by calendar week (ISO year and week), with the usual G/(G−1) correction
  - the code is checked against statsmodels with explicit dummies on a small subset.

## The three effects

- **Rain effect:** the wet-day coefficient. In percent: exp(b) − 1.
- **Cold effect:** the average change per degree between 0 °C and 15 °C. That is (5 × slope below 5 °C + 10 × slope from 5 to 15 °C) / 15. A positive value means traffic rises as it gets warmer.
- **Heat effect:** the slope above 25 °C.

## Tests of the predictions

- **Sample:**
  - the 9 period-comparison locations
  - years 2011–2014 (early) and 2022–2026 (late) only
  - weather terms estimated once per period instead of once per year.
- **Prediction 1:**
  - the change is the late rain effect minus the early rain effect
  - it is supported if the change is positive (a smaller drop) and the 95% interval excludes zero.
- **Prediction 2:**
  - the shrinkage of each effect is 1 − late / early
  - it is supported if both the cold and the heat shrinkage are larger than the rain shrinkage
  - intervals come from the delta method
  - if an early effect has a 95% interval that includes zero, its shrinkage is not interpreted.
- **Prediction 3:**
  - same as prediction 1, but the outcome is the bikes counted from 7:00 to 9:00 plus 16:00 to 19:00
  - only weekdays that are not public holidays are used
  - it is supported if the rush-hour change has the same sign as in prediction 1 and its 95% interval excludes zero.
- **Cleaning:** days flagged by the cleaning rule are excluded in the main results and included in the checks.
