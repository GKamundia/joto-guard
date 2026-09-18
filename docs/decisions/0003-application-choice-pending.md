# 0003. Application choice: Joto Guard

Date: 17 Sep 2026, decided 18 Sep 2026. Status: accepted.

**Options.** Shamba Twin (irrigation scheduling from station ET0 and a soil-water balance), Joto Guard (hourly WBGT heat-stress guidance) or Mbu Watch (malaria receptivity for Kiambu, following Evans et al. 2025). Evaluation in the Hack The Weather Playbook. All three build on Conduit Sentinel (decision 0001).

**Decision.** Joto Guard.

**Reasons.**

- It builds on Sentinel's strongest finding. The firmware WBGT sits below the wet bulb on 57.3 % of rows (78 % at night), which a real WBGT cannot do, and the station measures every input a standards-grade WBGT needs. Rebuilding the index from those inputs makes Sentinel and the application one story.
- The team's pitch leans towards health.
- It works on the data we have. Download permission for the portal history was not granted, so the organisers' 13 dry-season days are the record. A physics-based WBGT needs no training history; Shamba Twin's rainy-season backtest and Mbu Watch's seasonal cycle and satellite processing do.

**Known weaknesses.** Heat evidence for Juja itself is thin, and KMD already issues city heat warnings, so Joto Guard is pitched as hourly guidance by type of work that complements them. With 13 days there is no trained forecast-correction model: the forecast is corrected by hour of day, the fallback in the build plan.

**Consequences.** Application code lives in `src/joto_guard/` (the placeholder `src/app/` was named before the choice). The GitHub repository can be named `joto-guard` when it is created; the local folder keeps its working name.

**Correction (18 Sep 2026).** "Which a real WBGT cannot do" overstates it. A standard WBGT can sit a little below the wet bulb on a calm, clear night: by up to 0.76 °C on this station's nights, and 1.4 °C at most in still air between 8 and 25 °C. The firmware's gap, up to 3.4 °C, is too large for that. See decision 0007.
