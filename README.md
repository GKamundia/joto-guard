# conduit-app (working name)

> Hack The Weather 2026 entry built on the Conduit@Empathy1 weather station at JKUAT, Juja, Kenya. Rename this repository and title once the team chooses the application (Shamba Twin or Joto Guard).

All development for this submission took place from 17 to 21 September 2026. The commit history is the record.

<!--
The 15 sections below are required by the Hack The Weather rules. Replace each placeholder line.
Keep "Known limitations" and "Reproducibility" as well: judges reward honesty and one-command reruns.
-->

## 1. Project name

_TBD: final name and one-line tagline._

## 2. Problem statement

_TBD: the problem, who has it, where, with citations the team has read. Name the evidence limits._

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

_TBD_

## 15. Licence

MIT. See `LICENSE`.

---

## Known limitations

_TBD: for example, 8-day data sample, suspected (not confirmed) sensor faults, light-sensor calibration, validation scope._

## Reproducibility

_TBD: one command that regenerates every figure and number in this README._
