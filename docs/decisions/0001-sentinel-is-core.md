# 0001. Conduit Sentinel is the core of every candidate project

Date: 16 Sep 2026. Status: accepted.

**Context.** The Conduit@Empathy1 sample shows export and sensor issues (empty battery telemetry, a duplicated gust-direction column, a suspected second rain gauge fault, a non-standard firmware WBGT). Every candidate application depends on trustworthy station data, and "use of Conduit data" is the largest judging criterion (25%).

**Decision.** Build `conduit_sentinel` first. Its QC flags must gate the application's calculations, and its findings are shown in a Station Health Report page.

**Consequences.** Sentinel work starts before the application is chosen. Application code must read `obs_qc` or `obs_hourly`, never the raw CSV.
