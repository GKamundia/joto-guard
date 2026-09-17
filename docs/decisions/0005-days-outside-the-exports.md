# 0005. Days no export covers are not scored

Date: 17 Sep 2026. Status: accepted.

**Context.** The organisers' Drive folder holds three exports: 28 Aug to 1 Sep, 31 Aug to 4 Sep, and 11 to 15 Sep 2026. Nothing covers 5 to 10 Sep. Run over the folder, spec 0.2 scored those six days 0, listed every channel as bad, and charged 8,640 missing minutes, which reads as a six-day station outage. The portal shows the instrument reporting through that period, so the days are missing from the exports, not from the station. A six-day outage on the Station Health Report would misrepresent JHUB's station to the judges.

**Decision.** `ingest` returns the periods the input covers, taken from each file's first and last observation with overlapping files merged, and `apply_qc` carries them through. Then:

- `health_daily` and `channel_status_daily` have rows only for days a coverage window touches. A day with no observations *inside* a window still scores 0, because there the station really did stop reporting.
- Missing minutes count only inside a window, so the space between two exports is charged to nobody. The last day of one export and the first of the next score as normal days.
- `gaps` keeps every interval above the threshold but marks it `reporting` or `between_exports`.
- The cadence figures on the station card (median, minimum, maximum interval) ignore intervals between exports, so six days does not become the station's worst reporting interval.

With one continuous export, which is the usual case and what the spec's acceptance tests use, none of this changes anything.

**Consequences.** On the three organiser exports the report covers 13 days rather than 19, with no day scored 0. `gaps` has a new column, so anything reading it should expect `kind`. The report's coverage section lists `export_windows`, which the Station Health Report page can draw as gaps in the calendar rather than as failures.
