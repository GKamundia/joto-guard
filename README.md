# Joto Guard

> Hack The Weather 2026 entry built on the Conduit@Empathy1 weather station at JKUAT, Juja, Kenya.

All development for this submission took place from 17 to 21 September 2026. The commit history is the record.

<!--
The 15 sections below are required by the Hack The Weather rules. Replace each placeholder line.
Keep "Known limitations" and "Reproducibility" as well: judges reward honesty and one-command reruns.
-->

## 1. Project name

**Joto Guard** (*joto* is Kiswahili for heat): hourly heat-stress guidance for outdoor work in Juja, built on a quality-controlled Conduit@Empathy1 station. _TBD: final tagline._

## 2. Problem statement

Heat already costs Kenya's outdoor workers. In 2024, heat exposure cost the country 1.1 billion potential labour hours, a record 51 hours per person, and 74 % of the loss was in agriculture (Lancet Countdown 2025 data sheet for Kenya).

Around Juja, where the Conduit@Empathy1 station stands, much of the work is heavy and outdoors. Quarrying building stone is one of the municipality's most significant economic activities, fed by a construction boom, alongside farming (Juja Municipality Integrated Development Plan 2023–2028).

Kenya Met's heat advisories give temperatures for whole counties with general advice. They do not say when a given kind of work should slow down.

The station itself reports a wet bulb globe temperature (WBGT), the index occupational heat limits are written in. But its firmware value behaves as if the sun were not shining: at midday it reads about 6 °C below a standards-based estimate from the same sensors, so it could not be used to warn anyone.

The evidence, its sources and its limits (we found no published heat study for Juja itself, and our station record covers only three cool-season weeks) are in [`docs/PROBLEM_EVIDENCE.md`](docs/PROBLEM_EVIDENCE.md).

## 3. Solution

_TBD: what the app does and the decision it helps someone make._

## 4. How Conduit@Empathy data is used

_TBD: one table row per pipeline step (ingest, quality control, aggregation, application logic, outputs). Conduit data must drive the logic, not only the charts._

| Step | Conduit variables | What happens |
|---|---|---|
| Ingest | all 26 columns | _TBD_ |
| Quality control (Conduit Sentinel) | all | _TBD_ |
| Application logic | _TBD_ | _TBD_ |

## 5. Features

_TBD_

## 6. Technology stack

_TBD: Python (pandas, pytest), FastAPI, React + Vite + Leaflet, Telegram bot, and anything else used._

## 7. Architecture

_TBD: diagram in `docs/architecture/` plus three sentences._

## 8. Installation and setup

Prerequisites: Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Put the two organiser GeoCSV files in `data/raw/organiser/` (see its README). _TBD: `.env` from `.env.example` once the API and bot exist._

## 9. Usage

Run Conduit Sentinel on the organiser sample. It writes the quality-controlled tables and the Station Health Report to `data/processed/`:

```bash
python -m conduit_sentinel data/raw/organiser --out data/processed
```

| Output | Contents |
|---|---|
| `obs_qc.csv` | every observation with a flag per variable (0 good, 1 suspect, 2 bad, 3 missing) and the rules that fired |
| `obs_hourly.csv` | hourly values built only from good and suspect observations |
| `gaps.csv` | reporting gaps longer than 300 s |
| `health_daily.csv`, `channel_status_daily.csv` | daily station health score and the status of each sensor group |
| `audit_results.csv` | checks of the firmware wet bulb, heat index and WBGT, and thermometer agreement |
| `report.json` | the Station Health Report payload |

Serve the report and open the Station Health Report page:

```bash
uvicorn api.app:app --reload
```

```bash
cd web && npm install && npm run dev
```

The API is then on http://127.0.0.1:8000 (documentation at `/docs`) and the page on http://localhost:5173. The page reads `GET /v1/station-health` and holds no numbers of its own; `src/api/README.md` lists the other endpoints.

Calibrate the station's light sensor to W/m², which Joto Guard's WBGT needs. The first command fetches the ERA5 reference once; the second writes `config/solar_calibration.json` and `data/processed/ghi_hourly.csv` (method in `docs/decisions/0006-light-sensor-calibration.md`):

```bash
python scripts/fetch_solar_reference.py --start 2026-08-28 --end 2026-09-15
```

```bash
python -m joto_guard calibrate-light --reference data/reference/open_meteo_era5_2026-08-28_2026-09-15.json
```

Compute the station's hourly WBGT with the Liljegren et al. (2008) model. It needs only the Sentinel outputs and the tracked calibration (method and checks in `docs/decisions/0007-liljegren-wbgt.md`):

```bash
python -m joto_guard wbgt
```

It writes `data/processed/wbgt_hourly.csv`, which holds the inputs, globe temperature, natural and psychrometric wet bulb, WBGT and the firmware's own values for every hour. It also writes `data/processed/wbgt_firmware_by_hour.csv`, which compares the firmware's WBGT column with the model by hour of day.

Forecast WBGT for the next three days from ECMWF's IFS model, computed the same way (decision 0009). It fetches from Open-Meteo, saves the response in `data/reference/` and writes `data/processed/wbgt_forecast.csv`; `--payload <file>` recomputes a saved response:

```bash
python -m joto_guard forecast
```

The raw forecast reads about 2 °C below the station at midday, so it is not yet shown as guidance. The past forecasts the correction learns from are downloaded with:

```bash
python scripts/fetch_past_forecasts.py --start 2026-08-28 --end 2026-09-15
```

Tests and lint:

```bash
pytest
ruff check src tests && ruff format --check src tests
```

_TBD: Telegram bot._

## 10. Data sources

_TBD: see `docs/DATA_SOURCES.md`. Must include the Conduit@Empathy1 instrument (CHORDS instrument 61, attributed to `3d-fewsnet.icdp.ucar.edu`), the CHORDS software citation (DOI 10.5065/d6v1236q identifies the software, not the station data) and every external dataset with its licence or terms._

## 11. AI usage

_TBD: summarise `docs/AI_USAGE.md`: which AI tools were used, for what, and confirmation that every team member can explain the code._

## 12. Screenshots / demo

_TBD: images in `docs/figures/`; link to the demo video._

## 13. Team members

_TBD: names and roles._

## 14. Future development

- **Kisumu and Mombasa.** The 3D-PAWS FEWS NET portal lists a 3D-PAWS station at Kisumu Airport and stations at KALRO Mtwapa (Kilifi, just north of Mombasa) and KALRO Matuga (Kwale). Both cities are hotter and more humid than Juja, with different outdoor work: rice and sugarcane farming and fishing around Kisumu; the port, processing industries and fishing in Mombasa. Given download access, each station needs only its own light calibration and forecast correction (details in [`docs/PROBLEM_EVIDENCE.md`](docs/PROBLEM_EVIDENCE.md), section 5).
- **A live station feed.** With the portal's download permission, guidance could use the station's latest hour as well as the forecast.
- **The hot season.** January to March is not in the record we have; a full year of station data would show how often the heat limits are crossed then.
- **A measured globe temperature.** A black-globe thermometer beside the station would let WBGT be measured rather than modelled.

## 15. Licence

MIT. See `LICENSE`.

`src/joto_guard/wbgt.py` adapts WBGT version 1.1 by James C. Liljegren, Argonne National Laboratory; its licence is in `THIRD_PARTY_NOTICES.md`. This product includes software produced by UChicago Argonne, LLC under Contract No. DE-AC02-06CH11357 with the Department of Energy.

---

## Known limitations

_TBD: for example, 8-day data sample, suspected (not confirmed) sensor faults, light-sensor calibration, validation scope._

## Reproducibility

_TBD: one command that regenerates every figure and number in this README._
