# 0009. Forecasting WBGT from ECMWF IFS through Open-Meteo

Date: 19 Sep 2026. Status: accepted.

**Context.** Joto Guard's guidance needs WBGT for the hours ahead, and the station measures only the present. A weather model forecasts the same inputs the station measures (temperature, humidity, pressure, wind and solar radiation), so the forecast can go through the same WBGT model (decision 0007).

**Decision.**

- **Model.** ECMWF IFS HRES at 9 km (`models=ecmwf_ifs` in Open-Meteo). It has been open data (CC BY 4.0) since 1 October 2025. It gives hourly values for the first 90 hours, then 3-hourly, so the command's default horizon is 3 days.
- **Place.** The request is for the station's coordinates. Open-Meteo downscales it to the station's 1523 m; its grid point is −1.090, 37.021. Times are UTC and wind is in m/s.
- **Same hours as the station.**
  - Shortwave radiation is stamped at the end of the hour it averages, so it moves back one hour.
  - Temperature, humidity, pressure and wind are values at the stamp, so each hour takes the mean of its start and end values.
- **Same WBGT.** The inputs go through `wbgt_for_hours`, with the sun at the station's coordinates. The 10 m wind is brought down to 2 m with the model's stability-dependent power law.
- **Reproducible.** `python -m joto_guard forecast` saves each response it fetches in `data/reference/`, and `--payload` recomputes a saved one.

**How the raw forecast compares with the station.** Open-Meteo's Previous Runs API keeps what the model forecast 0, 1, 2 and 3 days before each hour. Those forecasts for 28 Aug to 15 Sep 2026 were run through `forecast_wbgt` and compared with the station's WBGT on the 311 hours both have (`scripts/fetch_past_forecasts.py` downloads them):

| Forecast made | Bias (°C) | Mean absolute error (°C) | Bias, 10:00 to 15:59 EAT | Error, 10:00 to 15:59 EAT |
|---|---|---|---|---|
| Same day | −1.29 | 1.49 | −2.10 | 2.47 |
| 1 day before | −0.95 | 1.37 | −2.06 | 2.58 |
| 2 days before | −0.88 | 1.45 | −1.85 | 2.56 |
| 3 days before | −0.90 | 1.52 | −1.99 | 2.69 |

- **The error is mostly systematic.** It barely grows with lead time, and it follows the clock. One day ahead, the bias is within 0.8 °C of zero at night and between −0.9 and −2.8 °C from 08:00 to 16:00 EAT.
- **Wind is the main cause.** At midday the model's 2 m wind averages 2.3 m/s, against 0.7 m/s at the station, and more wind cools the globe.
- **The other inputs differ too.** The model's GHI runs 40 to 115 W/m² above the station's calibrated estimate, which partly offsets the wind. Its air temperature is 0.2 to 0.9 °C lower.

On 19 Sep 2026 the raw forecast gave daily maxima of 22.8 to 24.5 °C for 19 to 22 Sep.

**Consequences.**

- **Not guidance yet.** The raw forecast reads about 2 °C low at midday. The next step (`bias.py`) corrects it by hour of day and lead time, fitted on the past forecasts and judged by leaving each day out. That step also turns the comparison above into a command.
- **What the correction targets.** It aims at the station series, so the corrected forecast says what the station's own inputs would give. It inherits the station's uncertainty (decision 0007), mainly the light calibration and the very light measured wind.
- **Sheltered wind.** If the anemometer turns out to be sheltered or to under-read, the correction would carry that into the forecast. The uncertainty range should therefore stay visible in the guidance.
