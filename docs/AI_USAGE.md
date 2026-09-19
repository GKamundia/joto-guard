# AI usage log

The Hack The Weather rules allow AI tools with disclosure, and every team member must be able to explain the solution. Add a row for each substantial AI-assisted piece of work. The README's "AI usage" section is summarised from this file.

| Date | Tool | What it helped with | Files | Reviewed and understood by |
|---|---|---|---|---|
| 2026-09-15 to 17 | Claude (Cowork) | Research brief, idea evaluation, data profiling of the organiser sample, repository structure and the Sentinel spec | `docs/`, `README.md` skeleton | _names_ |
| 2026-09-17 | Claude Code | Conduit Sentinel implementation (GeoCSV ingest, QC rules R01 to R16, hourly aggregation, health score, derived-variable audits, report payload, command line), unit and acceptance tests, CI workflow, spec 0.2 corrections (decision 0004) | `src/conduit_sentinel/`, `tests/`, `config/qc_rules.yaml`, `.github/workflows/`, `docs/` | _names_ |
| 2026-09-17 | Claude Code | Coverage windows so days no export covers are not scored as an outage (decision 0005), CHORDS DOI correction, FastAPI service over the Sentinel outputs, Station Health Report page | `src/conduit_sentinel/`, `src/api/`, `web/`, `tests/`, `docs/` | _names_ |
| 2026-09-18 | Claude Code | Light-sensor calibration against ERA5: reference download, solar geometry, sun-angle model, leave-one-day-out evaluation, the dew and cloud analysis in decision 0006 | `src/joto_guard/`, `scripts/fetch_solar_reference.py`, `config/solar_calibration.json`, `tests/joto_guard/`, `docs/` | _names_ |
| 2026-09-18 | Claude Code | Liljegren WBGT: numpy implementation, checks against Liljegren's compiled C program, hourly sun averaging, station series and firmware comparison, sensitivity analysis and the below-wet-bulb correction in decision 0007 | `src/joto_guard/`, `tests/joto_guard/`, `docs/`, `THIRD_PARTY_NOTICES.md` | _names_ |
| 2026-09-19 | Claude Code | R16/A03 margin for WBGT below the wet bulb (decision 0008, spec 0.4); WBGT forecast from ECMWF IFS through Open-Meteo, past-forecast download and the raw forecast's error against the station (decision 0009) | `src/conduit_sentinel/`, `src/joto_guard/`, `scripts/`, `tests/`, `config/`, `docs/` | _names_ |
