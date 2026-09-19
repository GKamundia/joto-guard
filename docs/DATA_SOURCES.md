# Data sources and provenance

Record every dataset the app uses: where it came from, when it was obtained, its terms, and where it lives in this repo. Update this file whenever a new source is added.

## Conduit@Empathy1 (mandatory core data)

| Item | Detail |
|---|---|
| Instrument | "Kenya Kiambu JKUAT IOT AWS - Conduti@Empathy1", CHORDS sensor_id 61 |
| Portal | UCAR 3D-PAWS FEWS NET CHORDS portal, `3d-fewsnet.icdp.ucar.edu/instruments/61` |
| Attribution | `3d-fewsnet.icdp.ucar.edu`, as requested in every export header |
| Platform citation | Daniels, M., Kerkez, B., Chandrasekar, V., Graves, S., Stamps, D. S., Martin, C., Botnick, A., Dye, M., Gooch, R., Jones, J., Keiser, K., Bartos, M., Nguyen, T., Collins, R., Chen, S., & Yang, T. (2014). *Cloud-Hosted Real-time Data Services for the Geosciences (CHORDS) software* (Version 0.9). University Corporation for Atmospheric Research. https://doi.org/10.5065/D6V1236Q |
| DOI caution | The `doi` line in every export (10.5065/d6v1236q) is the CHORDS software DOI above, the same for any CHORDS portal. It is not a DOI for the Conduit@Empathy1 data, and we know of no dataset DOI for this station. Cite the software as the platform and attribute the data to the portal and instrument 61. |
| Location | lat -1.099736, lon 37.014528, elevation 1523.0 m (JKUAT, Juja) |
| Organiser sample | Three GeoCSV files from the Hack The Weather Resources page (Google Drive folder "HackTheWeather2026-Data", https://drive.google.com/drive/folders/1KDoCh8vss7nv_B6SuVBlQQssjSh1yaBg, owner info.jhub@jkuat.ac.ke). Stored in `data/raw/organiser/`. No file covers 5 to 10 Sep 2026. |
| Portal history | 30 May 2025 onward (15,949,704 measurements on 17 Sep 2026). New portal accounts start as "guest"; downloading needs the "Registered User" and "Data Downloader" permissions, granted by a portal admin. Account registered 17 Sep 2026; download permission not granted as of that date. Stored in `data/raw/portal/` (git-ignored) if obtained. |
| Header units | The `field_unit` header line labels SHT Humidity as degC and Heat Index as #. The values are % and °C. Sentinel takes units from `docs/SENTINEL_SPEC.md` section 3, not from the header. |

| File | Obtained | Rows | Span (UTC) |
|---|---|---|---|
| `3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy1.csv` | 17 Sep 2026 | 7,060 | 2026-08-28T00:00:25Z to 2026-09-01T23:58:31Z |
| `3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy1(31-4).csv` | 17 Sep 2026 | 7,067 | 2026-08-31T00:00:24Z to 2026-09-04T23:58:18Z |
| `3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy11-15.csv` | 17 Sep 2026 | 7,062 | 2026-09-11T00:00:01Z to 2026-09-15T23:58:29Z |

## Derived files

| File | Made from | How |
|---|---|---|
| `data/interim/conduit_combined_minute.csv` | The two organiser files | Merged, 2,825 duplicate timestamps removed, 11,302 rows. Made during planning on 15 Sep 2026, before the build started; regenerate it with `conduit_sentinel` and treat the pipeline output as authoritative. |
| `data/processed/` (`obs_qc.csv`, `obs_hourly.csv`, `gaps.csv`, `rule_hits.csv`, `health_daily.csv`, `channel_status_daily.csv`, `audit_results.csv`, `report.json`) | The GeoCSV files passed to Sentinel | `python -m conduit_sentinel data/raw/organiser --out data/processed`. Not tracked; rerun to regenerate. |
| `config/solar_calibration.json` | `obs_hourly.csv` and the ERA5 reference below | `python -m joto_guard calibrate-light --reference data/reference/open_meteo_era5_2026-08-28_2026-09-15.json`. Tracked, so the calibration applies without the network. Method and skill in `decisions/0006-light-sensor-calibration.md`. |
| `data/processed/ghi_hourly.csv` | `obs_hourly.csv` and `config/solar_calibration.json` | Written by the same command. Not tracked. |
| `data/processed/wbgt_hourly.csv`, `wbgt_firmware_by_hour.csv` | `obs_hourly.csv`, `report.json` and `config/solar_calibration.json` | `python -m joto_guard wbgt`. Method in `decisions/0007-liljegren-wbgt.md`. Not tracked. |
| `data/processed/wbgt_forecast.csv` | An Open-Meteo forecast response (below), `report.json` and `config/forecast_correction.json` | `python -m joto_guard forecast`, which also saves the response in `data/reference/`. Raw and corrected WBGT with the uncertainty band. Not tracked. |
| `data/processed/heat_guidance.json` | `wbgt_forecast.csv` and `config/heat_guidance.yaml` | Written by `python -m joto_guard forecast`. Levels and allowed work minutes per hour for each type of work (decision 0011). Not tracked. |
| `config/forecast_correction.json` | `wbgt_hourly.csv` and the past forecasts below | `python -m joto_guard fit-correction --past-forecasts data/reference/open_meteo_ecmwf_ifs_past_forecasts_2026-08-28_2026-09-15.json`. Tracked, so the correction applies without the past forecasts. Method and skill in `decisions/0010-forecast-correction.md`. |

## External sources (add as used)

| Source | Use | Access | Terms | Obtained | Repo location |
|---|---|---|---|---|---|
| ERA5 hourly shortwave radiation and cloud cover, through the Open-Meteo archive API (`models=era5`), grid point −1.0, 37.0, 1526 m | Reference for calibrating the light sensor to W/m² | `https://archive-api.open-meteo.com/v1/archive`, no key; `scripts/fetch_solar_reference.py`. About five days behind real time: 28 Aug to 12 Sep 2026 had values | Open-Meteo data CC BY 4.0; contains modified Copernicus Climate Change Service information | 18 Sep 2026 | `data/reference/open_meteo_era5_2026-08-28_2026-09-15.json` (not tracked) |
| ECMWF IFS HRES 9 km forecast (`models=ecmwf_ifs`) through the Open-Meteo forecast API: 2 m temperature and humidity, surface pressure, 10 m wind, shortwave radiation, downscaled to 1523 m; grid point −1.090, 37.021 | Hourly WBGT forecast for the station | `https://api.open-meteo.com/v1/forecast`, no key; `python -m joto_guard forecast`. Hourly to 90 h ahead | Open-Meteo data CC BY 4.0, "Weather data by Open-Meteo.com"; ECMWF open data CC BY 4.0 | Each run of the command | `data/reference/open_meteo_ecmwf_ifs_forecast_<fetched UTC>.json` (not tracked); a 48-hour cut in `tests/fixtures/` |
| The same model's past forecasts, 0 to 3 days before each hour, through the Open-Meteo Previous Runs API | Forecast error at each lead time and hour of day, for the forecast correction | `https://previous-runs-api.open-meteo.com/v1/forecast`, no key; `scripts/fetch_past_forecasts.py`. Archives from January 2024 | As above | 19 Sep 2026, for 28 Aug to 15 Sep 2026 | `data/reference/open_meteo_ecmwf_ifs_past_forecasts_2026-08-28_2026-09-15.json` (not tracked) |
| NASA POWER hourly (`ALLSKY_SFC_SW_DWN`) | Planned calibration reference; **not used** | `https://power.larc.nasa.gov/api/temporal/hourly/point`, no key | NASA open data | Checked 18 Sep 2026: every hour from 28 Aug to 15 Sep 2026 was the fill value −999 | none |
