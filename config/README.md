# config/

- `qc_rules.yaml`: thresholds for QC rules R01 to R16, hourly coverage limits, health-score weights and audit settings. Defaults follow `docs/SENTINEL_SPEC.md` sections 6 and 8. `conduit_sentinel.config.load_config` rejects missing, unknown or out-of-range values.
