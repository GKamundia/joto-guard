# 0007. Computing the station's WBGT with the Liljegren model

Date: 18 Sep 2026. Status: accepted.

**Context.** Joto Guard needs a standards-grade WBGT, and the station's firmware column is not one (audit A03). WBGT = 0.7 × natural wet bulb + 0.2 × globe temperature + 0.1 × air temperature. The station measures neither the natural wet bulb nor the globe temperature. Liljegren et al. (2008) model both from air temperature, humidity, pressure, wind speed and solar irradiance. Each is the temperature at which the heat the wick or globe gains from the sun and sky balances the heat it loses to the air.

**Decision.**

- **Our own implementation** is `src/joto_guard/wbgt.py`, written in numpy. It follows the equations and constants of Liljegren's C program (WBGT v1.1, Argonne open-source licence; the notice is kept in the module and in `THIRD_PARTY_NOTICES.md`). The PyWBGT package is not used: its non-commercial licence does not fit this repository's MIT licence.
- **Inputs.** Air temperature and humidity both come from the SHT sensor. Its humidity is relative to its own temperature, so the pair gives the right vapour pressure, and it is the sensor the firmware's derived columns use. Pressure is the station's. Wind is the measured hourly mean, taken as the 2 m wind. GHI comes from the light calibration (decision 0006). All are Sentinel's quality-controlled hourly means, so an hour missing any of them has no WBGT.
- **Anemometer height.** It is unknown (a question for JHUB); `--wind-height` adjusts for it with the model's stability-dependent power law. Taking the anemometer to be at 3 m instead of 2 m changes WBGT by 0.1 °C at most.
- **Solver.** Each heat balance is solved by bisection instead of the original's relaxed fixed-point iteration: same equation, guaranteed to converge.
- **Hourly inputs.** The inputs are hourly means, so the sun is averaged over the hour as well:
  - GHI is compared with the hour's mean top-of-atmosphere sunlight, which sets how much of it counts as direct beam.
  - The beam arrives at the mean sun angle over the part of the hour the sun is up (Hogan and Hirahara 2016, as used for hourly WBGT by Kong and Huber 2022).
  - The original takes the angle at the middle of the averaging period. Near sunset that puts the sun on the horizon and makes the beam unrealistically strong: on this record, the midpoint angle raises single sunset hours by up to 4.1 °C.

**Checked against the original program.** Liljegren's C code was compiled unchanged and run on 20,000 random cases: 0 to 45 °C, 5 to 100 % humidity, 700 to 1030 hPa, 0 to 10 m/s, 0 to 1200 W/m², any hour, latitudes 40° S to 40° N.

- Given the same sun angle and irradiance, the two agree on globe temperature, both wet bulbs and WBGT within 0.019 °C. That is inside the original's own stopping tolerance of 0.02 K.
- On 39 cases the original fails to converge on at least one temperature and returns −9999. 38 are random draws with strong irradiance while the sun is below the horizon, which a real station would not report; one is dry air near freezing. Bisection returns a value for every case.
- The direct-beam share agrees within 0.00003 and the wind adjusted to 2 m within 0.0001 m/s.
- The sun angle agrees within 0.0011 in cos zenith with the sun above 15°. Near the horizon they differ by up to 0.015, because the original adds refraction.
- Seven of the reference cases are fixed in `tests/joto_guard/test_wbgt.py`.

**Station results.** 312 hours have every input, 28 Aug to 15 Sep 2026; the 144 hours from 5 to 10 Sep are in no export.

| | This model | Firmware column |
|---|---|---|
| Daily maximum, 11 full days | 21.9 to 28.5 °C | 16.0 to 22.0 °C |
| Hour of the daily maximum (EAT) | 12:00 to 14:00 | 14:00 to 16:00, with the air temperature |
| Hours at or above 26 °C, of 312 | 26 | 0 |

- **By hour of day,** the firmware reads 0.3 °C below the model at 19:00 EAT. The gap widens through the night to 2.5 °C by 05:00, and is 5.0 to 7.4 °C from 07:00 to 13:00. It closes to 0.2 °C by 18:00 (`wbgt_firmware_by_hour.csv`).
- **Across all hours,** the firmware is the lower of the two on 96 % of daylight hours and 94 % of night hours. On each day the model's peak is 5.0 to 7.4 °C above the firmware's.
- **Peak timing.** WBGT peaks 0 to 3 h before the air temperature does. The sun's share of the index peaks near solar noon (12:30 EAT), and humidity falls as the afternoon warms.

**Correction to an earlier claim.** Decision 0003 and the build plan say a real WBGT cannot fall below the wet bulb. It can, by a little. On a calm, clear night the globe and wick radiate to a sky colder than the air.

- **The model does it too.** It puts WBGT below the firmware's wet bulb on 34 % of the station's night hours, by at most 0.76 °C. Across 8 to 25 °C and 30 to 100 % humidity in still air, its lowest is 1.4 °C below.
- **The Stull formula adds to the effect.** It assumes sea-level pressure. At the station's 852 hPa the psychrometric wet bulb is 0.25 °C lower than at sea level, and 0.27 °C below Stull's, on average.
- **The firmware finding stands on its size.** Its WBGT is more than 1.5 °C below the wet bulb on 38.6 % of all rows, and up to 3.4 °C below.
- **Proposed:** rules R16 and A03 should count only rows more than 1.5 °C below the wet bulb. Accepted by the team on 19 Sep 2026 (decision 0008).

The build plan's acceptance checks change accordingly:

- "Night-time WBGT ≥ wet bulb" becomes "no more than 1.0 °C below".
- "Daytime WBGT above the firmware" holds on 96 % of daylight hours.
- "Peak lags the air temperature by 0 to 1 h" becomes "comes 0 to 4 h before it".

The first and third are tested on the real record in `tests/joto_guard/test_wbgt_on_station.py`.

**Uncertainty.** Measured by changing one input across the station hours:

| Change | Effect on WBGT, 10:00 to 15:59 EAT |
|---|---|
| GHI ± 155 W/m² (the calibration's daylight RMSE) | +1.1 / −1.3 °C |
| GHI + 79 W/m² (its RMSE under a clear reference sky) | +0.6 °C |
| Wind doubled; wind + 1 m/s | −1.5 °C; −1.9 °C |
| BMX or MCP thermometer instead of the SHT (vapour pressure kept) | −0.25 or −0.12 °C |
| Anemometer at 3 m instead of 2 m | +0.07 °C |

- **Light calibration and wind dominate.** The station's daytime hourly winds are 0.0 to 1.4 m/s (median 0.6), so how well the anemometer reads light air matters more than its height.
- **Cloudy nights.** The model treats the sky as clear for long-wave radiation, so on cloudy nights it can read slightly low (by no more than the 0.76 °C night dip above).

**Consequences.**

- `python -m joto_guard wbgt` writes `wbgt_hourly.csv` (inputs, globe, both wet bulbs, WBGT and the firmware's values for every station hour) and `wbgt_firmware_by_hour.csv`, which is audit A04's comparison by hour of day.
- The Station Health Report still shows A04 as pending. The comparison lives in the application layer, and Sentinel does not depend on it.
- Forecast inputs (Open-Meteo, 10 m wind) will go through the same `wbgt_for_hours`, so station and forecast WBGT are computed identically.

References: Liljegren, J. C. et al. (2008), *J. Occup. Environ. Hyg.* 5, 645–655, doi:10.1080/15459620802310770. Hogan, R. J. and Hirahara, S. (2016), *Geophys. Res. Lett.* 43, 482–488, doi:10.1002/2015GL066868. Kong, Q. and Huber, M. (2022), *Earth's Future* 10, e2021EF002334, doi:10.1029/2021EF002334.
