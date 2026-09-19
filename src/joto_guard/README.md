# src/joto_guard/ (application layer)

Hourly heat-stress guidance for Juja, built on the Conduit Sentinel outputs (decision 0003). It reads `obs_hourly.csv` and `report.json` from Sentinel, never the raw CSVs.

| Module | Does | Status |
|---|---|---|
| `solar.py` | Sun position: cosine of the solar zenith angle, its hourly means, and the Earth-Sun distance | done |
| `solar_calibration.py` | Light-sensor counts to GHI in W/m², fitted against ERA5 (decision 0006) | done |
| `wbgt.py` | Standards-grade WBGT (Liljegren et al. 2008) from air temperature, humidity, pressure, wind and GHI; checked against Liljegren's original program (decision 0007) | done |
| `station_wbgt.py` | The station's hourly WBGT from the Sentinel outputs, and the firmware column compared by hour of day | done |
| `forecast.py` | The same WBGT from an ECMWF IFS forecast through Open-Meteo (decision 0009) | done |
| `bias.py` | Forecast correction towards the station by local hour, with an uncertainty band judged on days left out (decision 0010) | done |
| `bands.py` | Heat limits and advice by type of work (NIOSH) | next |

```bash
python scripts/fetch_solar_reference.py --start 2026-08-28 --end 2026-09-15
python -m joto_guard calibrate-light --reference data/reference/open_meteo_era5_2026-08-28_2026-09-15.json
python -m joto_guard wbgt
python -m joto_guard forecast
python scripts/fetch_past_forecasts.py --start 2026-08-28 --end 2026-09-15
python -m joto_guard fit-correction --past-forecasts data/reference/open_meteo_ecmwf_ifs_past_forecasts_2026-08-28_2026-09-15.json
```

The second command writes `config/solar_calibration.json` (tracked) and `data/processed/ghi_hourly.csv`. The third needs only the Sentinel outputs and that tracked calibration; it writes `data/processed/wbgt_hourly.csv` and `data/processed/wbgt_firmware_by_hour.csv`. Pass `--wind-height` once the anemometer height is known. `forecast` fetches the next three days, saves the response in `data/reference/` and writes `data/processed/wbgt_forecast.csv` with the corrected WBGT and its band. `fit-correction` refits `config/forecast_correction.json` (tracked) from the past forecasts the script saves.

`wbgt.py` adapts Liljegren's WBGT version 1.1 (Copyright © 2008, UChicago Argonne, LLC); its licence is in `THIRD_PARTY_NOTICES.md`.
