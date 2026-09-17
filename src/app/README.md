# src/app/ (application layer, pending decision 0003)

Reads Sentinel outputs (`obs_qc`, `obs_hourly`), never raw CSVs. Create modules only after the project is chosen.

Planned modules if **Shamba Twin**: `solar_calibration.py`, `et0.py` (FAO-56 Penman-Monteith), `soil.py`, `water_balance.py`, `forecast.py`, `recommend.py`.

Planned modules if **Joto Guard**: `solar_calibration.py`, `wbgt.py` (Liljegren), `forecast.py`, `bias.py`, `bands.py`.

`solar_calibration.py` is shared by both options and can be started as soon as Sentinel's hourly output exists.
