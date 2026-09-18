# 0006. Calibrating the light sensor against ERA5

Date: 18 Sep 2026. Status: accepted.

**Context.** Joto Guard's WBGT needs solar irradiance in W/m². The station's SI1145 light sensor reports raw counts. The build plan named NASA POWER hourly irradiance as the reference.

**What the data showed.**

- NASA POWER had no hourly solar values for 28 Aug to 15 Sep 2026 when checked on 18 Sep (every hour was the fill value −999). ERA5 through the Open-Meteo archive covers 28 Aug to 12 Sep, about five days behind real time, at grid point −1.0, 37.0, 1526 m (the station is at 1523 m). The archive's default blend fills the latest days from other models, so the reference is requested as `models=era5` to stay one known product. The overlap with the station is 10 days.
- Open-Meteo gives an hour's radiation as the mean of the *preceding* hour. Shifting it back one hour lifts the correlation with the station's counts from 0.919 to 0.946, confirming the convention.
- The sensor under-responds when the sun is low: counts per W/m² rise from about 3.7 at 07:00 EAT to 7.3 at noon. The visible channel is about 9 % of the infrared one at every hour, so it carries no extra information.
- Some mornings read far darker than their afternoons. That is not the sensor's geometry: on 29 Aug, a clear day, morning and afternoon counts at mirrored sun positions match (ratio 0.99). On 2 and 3 Sep the dark mornings came with a slow warm-up (3.5 to 4.1 °C from 06:00 to 10:00) and 80 to 97 % ERA5 cloud, which is real cloud. On 4 Sep the morning was as dark but the air warmed as fast as on a clear day, after a humid (89 %), windless night. That points to dew on the sensor window. It is suspected, not confirmed.

**Decision.** `GHI = (IR counts − 253) × (a + b × (1 − μ))`, where μ is the hour's mean cosine of the solar zenith angle and 253 is the night-time median of the infrared counts. a = 0.13525 and b = 0.09867, fitted by least squares on the daylight hours of all 10 days. The result lives in `config/solar_calibration.json`. Fitting only on hours after noon, to avoid dew, changed the afternoon error by 3 W/m², so no cutoff is applied.

**How good it is.** Every figure comes from leaving each day out of the fit and predicting it:

| Hours | n | RMSE (W/m²) | Bias (W/m²) | R² |
|---|---|---|---|---|
| All daylight | 110 | 155 | −41 | 0.67 |
| Sun above 30° | 73 | 176 | −49 | 0.30 |
| ERA5 reports under 25 % cloud | 14 | 79 | −39 | 0.91 |

The station sees its own clouds and ERA5 sees the average over a grid cell about 25 km across. Under a clear reference sky the error halves; the larger figures mostly measure that difference, not the calibration. On the five clearest days the estimated peak is 963 to 1064 W/m², inside the 800 to 1100 W/m² expected for a September noon at this altitude, and every night hour is exactly zero.

**Consequences.**

- WBGT inherits this uncertainty and should carry it into any figure or claim.
- The station reads about 40 W/m² below ERA5 on average, even under a clear reference sky. Whether ERA5 or the sensor is off cannot be settled with this data.
- On a dew morning the estimate reads low until the window clears. Before 10:00 EAT the air in this record stayed below 24.2 °C (below 21.5 °C 99 % of the time), so that rarely matters for the heat bands, but those mornings should not go into any figure about the sensor.
- To refit when more data arrives: `python scripts/fetch_solar_reference.py --start … --end …`, then `python -m joto_guard calibrate-light --reference data/reference/<file>`.
