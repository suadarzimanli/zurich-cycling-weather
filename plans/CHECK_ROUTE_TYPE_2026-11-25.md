# Check added after the results: commuter routes and leisure routes

Written on 25 November 2026, before the check was run. Its checksum is stored in `docs/FROZEN_SHA256.txt`.

## Question

Did the rain effect weaken on commuter-type routes, on leisure-type routes, or on both?

The paper offers a change in the mix of riders as one possible explanation, for example more regular riders who keep cycling in the rain. Earlier work finds that experienced riders respond less to rain, and that leisure routes respond more to weather than commuter routes. The check asks where the weakening happened. It cannot prove why.

## Classification of the 33 city locations (no weather used)

For each location we compute the **weekend ratio**:

- the mean daytime count (6:00 to 20:00) on Saturdays and Sundays
- divided by the mean daytime count on working days (Monday to Friday, not public holidays)
- using all complete days kept by the cleaning rule, without 2020 and 2021.

Locations with a ratio at or below the median of the 33 locations are **commuter-type**. Those above the median are **leisure-type**. The ratio uses counts and the calendar only.

## Model

This is the trend design of question 1, unchanged:

- each location has its own weather effects (local terms);
- device-by-month and location-by-weekday effects, holidays;
- weather from Fluntern;
- 2011 to 2026 without 2020 and 2021;
- standard errors clustered by week.

The only change is that the trend per decade in each weather term is estimated **separately for the two groups**, together with the holiday terms.

## Result to report

- The rain trend per decade for commuter-type and for leisure-type locations, with 95% intervals.
- The difference, commuter minus leisure, with its 95% interval.

## Reporting rule

The result is reported in the paper in any case, in one short paragraph marked as added after the results. Every outcome is informative:

- **Clearer weakening on commuter-type routes:** fits the explanation of more regular riders.
- **Clearer weakening on leisure-type routes:** fits leisure riders becoming less sensitive to rain.
- **No clear difference:** the change is broad and not tied to one type of route.

No other split is tried. Cutoffs other than the median, other indices (such as the morning peak share) and other designs are not tried.
