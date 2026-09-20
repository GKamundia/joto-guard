# AI usage log

The AI tool used in this project is Anthropic's Claude: Claude Code, and Claude in Cowork during planning. It was used for debugging and explaining code errors, for writing code, tests and documentation, and for research and data analysis. The team reviewed and ran every change and can explain each part of the solution, as the Hack The Weather rules require.

| Date | Tool | What it did | Files | Reviewed by |
|---|---|---|---|---|
| 2026-09-19 | Claude Code | Evidence for the problem statement (sources checked online), forecast correction by hour of day with an uncertainty band (decision 0010) | `docs/PROBLEM_EVIDENCE.md`, `README.md`, `src/joto_guard/bias.py`, `tests/joto_guard/`, `config/forecast_correction.json`, `docs/` | _names_ |
| 2026-09-19 | Claude Code | Heat guidance from NIOSH limits by type of work (sources checked online), work/rest minutes per hour, the guidance document for the API and bot (decision 0011) | `src/joto_guard/bands.py`, `src/joto_guard/guidance.py`, `config/heat_guidance.yaml`, `tests/joto_guard/`, `docs/` | _names_ |
| 2026-09-20 | Claude Code | Front-end redesign: colour/spacing tokens with a light and dark palette, sticky tab bar, reworked Right now card, hour strip aligned one column per hour of day, responsive health chart, inline styles moved into the stylesheet | `web/src/styles.css`, `web/src/App.jsx`, `web/src/components/`, `web/src/format.js`, `web/index.html`, `web/public/favicon.svg`, `web/README.md` | _names_ |
