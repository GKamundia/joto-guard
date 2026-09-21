# config/

- `qc_rules.yaml`: thresholds for QC rules R01 to R16, hourly coverage limits, health-score weights and audit settings. Defaults follow `docs/SENTINEL_SPEC.md` sections 6 and 8. `conduit_sentinel.config.load_config` rejects missing, unknown or out-of-range values.
- `heat_guidance.yaml`: NIOSH limits by type of work, work/rest spells and the advice, in English and Kiswahili (decision 0011).

Results computed once from downloaded data and reviewed, tracked here so that a rerun cannot silently change them. Each carries how it was scored:

- `solar_calibration.json`: the light sensor against ERA5 irradiance (decision 0006).
- `forecast_correction.json`: the forecast corrected towards the station by hour of day (decision 0010).
- `forecast_verification.json`: whether that forecast gets the level right (decision 0012), from `python -m joto_guard verify`.
- `hot_season.json`: every working hour since 2016 against the limits (decision 0013), from `python -m joto_guard hot-season`.
