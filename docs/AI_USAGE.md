# AI usage log

The Hack The Weather rules allow AI tools with disclosure, and every team member must be able to explain the solution. Add a row for each substantial AI-assisted piece of work. The README's "AI usage" section is summarised from this file.

| Date | Tool | What it helped with | Files | Reviewed and understood by |
|---|---|---|---|---|
| 2026-09-15 to 17 | Claude (Cowork) | Research brief, idea evaluation, data profiling of the organiser sample, repository structure and the Sentinel spec | `docs/`, `README.md` skeleton | _names_ |
| 2026-09-17 | Claude Code | Conduit Sentinel implementation (GeoCSV ingest, QC rules R01 to R16, hourly aggregation, health score, derived-variable audits, report payload, command line), unit and acceptance tests, CI workflow, spec 0.2 corrections (decision 0004) | `src/conduit_sentinel/`, `tests/`, `config/qc_rules.yaml`, `.github/workflows/`, `docs/` | _names_ |
