# src/joto_guard/ (application layer)

Hourly heat-stress guidance for Juja, built on the Conduit Sentinel outputs (decision 0003). It reads `obs_hourly.csv` and `report.json` from Sentinel, never the raw CSVs.

| Module | Does | Status |
|---|---|---|
| `solar.py` | Sun position: cosine of the solar zenith angle, and its hourly mean | done |
| `solar_calibration.py` | Light-sensor counts to GHI in W/m², fitted against ERA5 (decision 0006) | done |
| `wbgt.py` | Standards-grade WBGT (Liljegren et al. 2008) from air temperature, humidity, pressure, wind and GHI | next |
| `forecast.py` | The same WBGT from Open-Meteo forecast inputs | planned |
| `bias.py` | Forecast correction by hour of day against the station series | planned |
| `bands.py` | Heat bands and advice by type of work | planned |

```bash
python scripts/fetch_solar_reference.py --start 2026-08-28 --end 2026-09-15
python -m joto_guard calibrate-light --reference data/reference/open_meteo_era5_2026-08-28_2026-09-15.json
```

The second command writes `config/solar_calibration.json` (tracked) and `data/processed/ghi_hourly.csv`.
