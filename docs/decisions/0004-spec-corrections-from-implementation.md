# 0004. Spec 0.2: corrections found while implementing Sentinel

Date: 17 Sep 2026. Status: accepted.

**Context.** Building `conduit_sentinel` against spec 0.1 and re-checking section 11 on the organiser sample turned up one wrong expected value, one rule that breaks on long records, and several details the spec left open.

**Decisions taken by the team.**

1. **Late intervals are 120 to 300 s inclusive; the sample has 22.** Spec 0.1 printed 21. The sample has two intervals of exactly 120.0 s (one missed report each) and 20 between 120 and 300 s. The 21 only reproduces as "interval above 120 s", which also counts the 755 s gap, so a gap would count as both a gap and a late report.
2. **Missing minutes are charged to the days they fall in.** Spec 0.1 charged a gap's minutes to the day it ended. On the portal history, a three-day outage would have scored the day data resumed at 0 and left the outage days without a row. Now each UTC day gets its share, and a day without observations gets a row with every group bad and a score of 0. The sample scores are unchanged.

**Details fixed during implementation.** These follow the spec's intent; change them in code or config if the team disagrees.

- Hourly values also need at least 50 % of the expected minutes to be usable for that variable (`hourly.min_variable_coverage_pct`), so a mean is never built from a few good minutes in an hour that is mostly flagged. Set it to 0 to go back to the spec 0.1 behaviour.
- `wind_dir_deg` is averaged as a unit vector (the mean of 350° and 10° is 0°, not 180°).
- R11 flags every channel of the zero gauge (per-observation, today and prior totals), since all three come from the same instrument. Values already flagged bad by R05 are not counted towards the rain totals.
- Daily rules (R11, R12, R13) and R14 appear in `qc_notes`, so every non-zero flag on a row is explained on that row.
- When files overlap, the copy from the file whose record starts earliest is kept. File names are not used for ordering: sorted by name, the `(31-4)` export would come first. Ingest counts overlapping timestamps whose values differ (`conflicting_duplicates`) and logs a warning if there are any.
- Threshold comparisons allow 1e-9 of float slack, because differences such as 16.1 − 14.1 evaluate to 2.0000000000000018.

**Findings recorded for later, not acted on.**

- The station's `Rain Gauge 1 Total Today` resets at 06:00 UTC (09:00 EAT), the WMO rain-day convention, seen at both transitions in the sample (31 Aug and 1 Sep). R11 and the report use UTC days as the spec says. Anyone comparing with CHIRPS or KMD daily rain should align to the 06:00 UTC day.
- Device code 33501705 appears about every 22.9 hours (every 1,341 to 1,351 rows), and in all 9 cases after a longer-than-normal interval (median 135 s). That is consistent with a periodic restart, but the code is undocumented; ask JHUB before saying so.

**Consequences.** Acceptance tests use 22 late intervals. `channel_status_daily` and `rule_hits` are new outputs the report and API can use. `health_daily` can contain days with `n_obs` 0.
