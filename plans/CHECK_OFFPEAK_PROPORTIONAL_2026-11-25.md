# Two checks added after the results: car traffic outside the peak, and the route-type gap in proportional terms

Written on 25 November 2026, before either check was run. Its checksum is stored in `docs/FROZEN_SHA256.txt`.

## Check A. Car traffic outside the peak hours

### Question

The paper finds that car traffic is not higher on wet days. A reviewer could object that many roads are full at peak times. Rain also slows traffic and lowers the number of cars a road can carry. On full roads, extra car trips would then show up as queues and not as higher counts. Outside the peak hours, most roads are not full, so extra car trips on wet days would be counted there.

### Data

- The same 134 car measuring points and the same years as the period design of question 4: 2012 to 2014 and 2022 to 2026.
- The same days as in question 4: all 14 daytime hours measured and kept by the cleaning rule.
- Two hour bands, built from the hourly counts of these days (the hour stamp is the start of the hour):
  - **off-peak:** 9:00 to 16:00 on every day of the week (7 hours);
  - **peak:** 7:00 to 9:00 and 16:00 to 19:00 on working days, that is Monday to Friday and not a public holiday (5 hours). These are the rush hours of the first plan.

### Model

The period model of question 4, unchanged: weather terms by period, device-by-month and location-by-weekday effects, holidays, weather from Fluntern, standard errors clustered by week. The two bands are estimated in one model as two data sources, each with its own weather terms by period and its own holiday terms, and each measuring point counts as a separate location in each band.

### Result to report

- The wet-day effect on car traffic in the off-peak band, early and late, with 95% intervals. This is the main result.
- The same for the peak band, for comparison.
- The difference, off-peak minus peak, in each period.

### Reporting rule

The result is reported in the paper in any case, marked as added after the results.

- **Off-peak effect negative, or interval includes zero:** the finding that car traffic does not rise on wet days stands, and full roads do not explain it.
- **Off-peak effect clearly positive (interval above zero) in either period:** the paper says that some trips may move to the car outside the peak hours, and the car claim in the abstract, the discussion and the conclusion is softened.

No other hour bands are tried.

## Check B. The route-type gap in proportional terms

### Question

On leisure-type routes the rain effect weakened by 0.108 log points per decade, on commuter-type routes by 0.038. Leisure routes may simply have started with a stronger rain effect. Then the same proportional weakening would give a larger change in log points. The check asks whether leisure-type routes weakened more even in proportional terms.

### Model

The model of `29_route_type.py`, unchanged: the same classification, data and terms. The estimator is extended so that it also returns the location-specific weather effects and the full covariance of all coefficients. The extension must reproduce the covariance of the trend terms of the original estimator.

### Quantities

For each group g:

- **start level:** the simple mean, over the locations of the group, of each location's own wet-day effect in the model. In this model that is the wet-day effect in 2011, the start of the trend.
- **proportional change per decade:** the trend per decade of the wet-day effect divided by the absolute value of the start level.

### Result to report

- The start level of each group, with 95% intervals.
- The proportional change per decade of each group, with 95% intervals (delta method).
- The difference, leisure minus commuter, with its 95% interval.

### Reporting rule

The result is reported in the paper in any case, in Section 5.8, marked as added after the results.

- **Difference clearly above zero:** leisure-type routes weakened more even in proportional terms.
- **Interval includes zero:** the gap in log points is consistent with the same proportional weakening on routes that started with a stronger rain effect. Section 5.8 and the discussion are rewritten to say this.
- **Difference clearly below zero:** reported as such.

No other definition of the start level is tried.
