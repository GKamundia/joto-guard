# 0010. Correcting the WBGT forecast towards the station

Date: 19 Sep 2026. Status: accepted.

**Context.** The raw ECMWF forecast, run through the same WBGT model as the station, reads about 2 °C low at midday and is close at night. Its error barely changes between forecasts made on the day and three days ahead (decision 0009). An error that follows the clock can be removed by hour of day.

**Decision.**

- **Hourly offsets.** For each local hour, the offset is the mean of station WBGT minus forecast WBGT over the past forecasts for 28 Aug to 15 Sep 2026. That is 1,244 pairs, from forecasts made 0 to 3 days ahead. The corrected forecast is the raw value plus the offset for its hour. Offsets run from about 0 °C in the early morning to +2.8 °C at 15:00.
- **One set of offsets for every lead time.** Separate offsets for each lead day scored no better on days left out of the fit (mean absolute error 1.077 °C against 1.074 °C pooled).
- **No smoothing.** Smoothing the offsets over three or five hours changed the error by 0.01 °C at most.
- **Uncertainty band.** The band spans the 10th to 90th percentile of the corrected forecast's error on days left out, at that hour and its two neighbours. From 12:00 to 14:59 it runs from 3.0 to 3.9 °C below the corrected value to 2.1 to 2.4 °C above it.
- **Stored, not refitted per run.** `python -m joto_guard fit-correction` saves the offsets, band and skill in `config/forecast_correction.json` (tracked). `python -m joto_guard forecast` applies them.

**How good it is.** Every figure is on days left out of the fit, one local day at a time. The station's usual value for the hour (its mean on the other days) is the forecast to beat.

| Forecast made | Raw | Corrected | Station's usual value |
|---|---|---|---|
| Same day | 1.49 °C | 0.98 °C | 1.38 °C |
| 1 day before | 1.37 °C | 1.02 °C | 1.38 °C |
| 2 days before | 1.45 °C | 1.14 °C | 1.38 °C |
| 3 days before | 1.52 °C | 1.16 °C | 1.38 °C |
| All | 1.46 °C | 1.07 °C | 1.38 °C |
| 10:00 to 15:59 EAT | 2.58 °C | 1.62 °C | 2.11 °C |

The figures are mean absolute errors against the station's WBGT.

- **It beats the station's usual value at every lead time.** The forecast adds most on unusual days: on the cool, rainy 31 August and on 15 September. On a few ordinary days the usual value was closer.
- **The band is honest.** On days it was not fitted to, the 80 % band held the station value 78.9 % of the time.

**Consequences.**

- **Target.** The correction makes the forecast say what the station's own inputs would give. It carries the station's uncertainty with it: the light calibration and the very light wind the anemometer reports (decisions 0007 and 0009).
- **Few days, one season.** Thirteen dry-season days fit the offsets; the hot season may need different ones. Refit as data arrives with `python scripts/fetch_past_forecasts.py --start … --end …` and `python -m joto_guard fit-correction --past-forecasts data/reference/<file>`.
- **Wide band.** The band is 5 to 6 °C wide around midday, so heat guidance must say when the band reaches a limit, not only when the corrected value does.
