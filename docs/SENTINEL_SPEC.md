# Conduit Sentinel: specification

Version 0.2, 17 Sep 2026. This is the build contract for `src/conduit_sentinel/`. Every expected value in section 11 was computed from the two organiser CSVs; if an implementation disagrees, check the implementation first, then raise it with the team.

Changes from 0.1 (same day, see `decisions/0004-spec-corrections-from-implementation.md`): the late-interval count in section 11 is 22, not 21; missing minutes are charged to the days they fall in, and days without observations get a health row; the hourly, R11 and `qc_notes` rules are stated precisely; two supporting tables (`rule_hits`, `channel_status_daily`) are added.

## 1. Purpose and scope

Sentinel turns raw Conduit@Empathy1 observations into quality-controlled data that the application layer can trust, and documents the station's condition in a Station Health Report.

**In scope (MVP):** ingest, QC flags, hourly aggregation, daily health score, derived-variable audit, report data (JSON) for the API and web page.

**Out of scope for now:** gap-filling, anomaly-detection models, comparisons with other stations, and ERA5-Land residual checks. ERA5-Land checks are an optional later addition.

## 2. Input format (GeoCSV)

- Lines beginning with `#` are metadata, formatted `# key: value`.
- The metadata keys used are: `instrument_name`, `sensor_id`, `data collection site`, `data collection latitude`, `data collection longitude`, `data collection elevation`, `Measurements in File`, `field_unit`, `creation_date`, `doi`.
- Then one header row with the 26 column names in section 3, then data rows.
- `Time` is ISO 8601 UTC ending in `Z`, for example `2026-08-28T00:00:25Z`.
- Empty cells mean no value (for example `Battery Voltage`).
- Consistency check: `Measurements in File` equals rows × non-empty variables (24 for both sample files).

## 3. Column map

| GeoCSV column | Portal short name | Unit | Canonical name |
|---|---|---|---|
| Time | | ISO 8601 UTC | `time_utc` |
| Health | hth | code | `health_code` |
| Battery Voltage | bv | % | `battery_voltage` |
| Battery charge status | bcs | code | `battery_status` |
| Cell signal strength | css | % | `cell_signal` |
| Rain Gauge 1 | rg | mm | `rain1_mm` |
| Rain Gauge 2 | rg2 | mm | `rain2_mm` |
| Rain Gauge 1 Total Today | rgt | mm | `rain1_today_mm` |
| Rain Gauge 2 Total Today | rgt2 | mm | `rain2_today_mm` |
| Rain Gauge 1 Total Prior | rgp | mm | `rain1_prior_mm` |
| Rain Gauge 2 Total Prior | rgp2 | mm | `rain2_prior_mm` |
| BMX Temperature 1 | bt1 | °C | `t_bmx_c` |
| BMX Pressure 1 | bp1 | hPa | `p_station_hpa` |
| MCP Temperature 1 | mt1 | °C | `t_mcp_c` |
| SHT Temperature | st1 | °C | `t_sht_c` |
| SHT Humidity | sh1 | % | `rh_pct` |
| SI1145 Visible 1 | sv1 | counts | `light_vis_counts` |
| SI1145 Infrared 1 | si1 | counts | `light_ir_counts` |
| SI1145 Ultraviolet 1 | su1 | index | `uv_index` |
| Wind Speed | ws | m/s | `wind_speed_ms` |
| Wind Direction | wd | degrees | `wind_dir_deg` |
| Wind Gust | wg | m/s | `wind_gust_ms` |
| Wind Gust Direction | wgd | degrees (duplicated, see issues) | `wind_gust_dir_deg` |
| Heat Index | hi | °C | `heat_index_fw_c` |
| Wet Bulb Temperature | wbt | °C | `wet_bulb_fw_c` |
| Wet Bulb Globe Temperature | wbgt | °C | `wbgt_fw_c` |

The `_fw` suffix marks values computed by the station firmware, so nobody confuses them with values Sentinel computes.

**Channel groups** (used by the health score): `thermometers` (t_bmx_c, t_mcp_c, t_sht_c), `humidity` (rh_pct), `pressure` (p_station_hpa), `rain_gauge_1` (rain1_*), `rain_gauge_2` (rain2_*), `light` (light_*, uv_index), `wind` (wind_speed_ms, wind_dir_deg, wind_gust_ms), `wind_gust_dir` (wind_gust_dir_deg), `battery` (battery_voltage, battery_status), `comms` (cell_signal), `derived_fw` (heat_index_fw_c, wet_bulb_fw_c, wbgt_fw_c).

## 4. Data contracts

**`obs_raw`**: one row per observation. Columns: `station_id` (int, 61), `time_utc`, the canonical variables, and `source_file`.

**`obs_qc`**: `obs_raw` plus one `qc_<variable>` column per variable (int flag, section 7), plus `qc_notes` (semicolon-separated rule ids that fired on that row, sorted, each once). A null value is always flagged 3. Daily rules (R11, R12, R13) note every row of the day they fire on, so every non-zero flag on a row is explained in its notes.

**`gaps`**: `station_id`, `gap_start_utc` (last observation before the gap), `gap_end_utc` (first after), `interval_s`, `missing_minutes` = (interval_s − 60) / 60.

**`obs_hourly`**: `station_id`, `hour_utc`, `n_obs`, `coverage_pct` = n_obs / 60 × 100, then one column per variable under its canonical name: the mean over rows flagged 0 or 1 for continuous variables, the circular (unit-vector) mean for `wind_dir_deg`, the maximum for `wind_gust_ms`, and the sum for `rain1_mm` and `rain2_mm`. Device codes, the station's running rain totals and `wind_gust_dir_deg` are not aggregated. Every hour from the first to the last observation has a row, including hours without data. A value is null when `coverage_pct` is below 50, or when the variable's usable (flag 0 or 1) values cover less than 50 % of the expected 60. The second threshold is `hourly.min_variable_coverage_pct` in config; 0 turns it off.

**`health_daily`**: `station_id`, `date_utc`, `score`, `bad_groups` (list), `suspect_groups` (list), `missing_minutes`, `n_obs`. One row for every UTC day from the first to the last observation, including days without observations.

**`channel_status_daily`**: `station_id`, `date_utc`, `group`, `status` (good, suspect or bad), `rules` (the rule ids behind a suspect or bad status). One row per scored group per day; `health_daily` summarises it.

**`rule_hits`**: `rule_id`, `variable`, `date_utc`, `n_rows`: how many rows each rule fired on, per variable and UTC day. R14 is recorded against `time_utc`.

**`audit_results`**: one row per audit (section 9). Columns: `audit_id`, `variable`, `metric`, `value`, `n_rows`, `verdict`, `note`.

**`report.json`**: the Station Health Report payload (section 10).

## 5. Modules

| Module | Responsibility | Main inputs | Main outputs |
|---|---|---|---|
| `schema.py` | Column map, channel groups and flag codes (sections 3 and 7) | | |
| `config.py` | Load and validate `config/qc_rules.yaml` | YAML path | `Config` |
| `ingest.py` | Parse GeoCSV metadata and data; map to canonical names; parse times as UTC; concatenate files; drop exact duplicate timestamps and log the count; check the measurement count | GeoCSV paths | `obs_raw`, station metadata, per-file ingest record |
| `qc.py` | Apply the rules in section 6 using `config/qc_rules.yaml`; produce flags and `qc_notes`; build the `gaps` table | `obs_raw`, config | `obs_qc`, `gaps`, `rule_hits` |
| `aggregate.py` | Hourly aggregation with coverage | `obs_qc` | `obs_hourly` |
| `health.py` | Daily health score (section 8) | `obs_qc`, `gaps`, `rule_hits`, config | `channel_status_daily`, `health_daily` |
| `thermo.py` | Stull (2011) wet bulb and NWS heat index | temperature, humidity | arrays |
| `audit.py` | Derived-variable audits (section 9) | `obs_qc` | `audit_results` |
| `report.py` | Assemble the Station Health Report payload | all of the above, station metadata | `report.json` |
| `pipeline.py`, `__main__.py` | Run every step and write the outputs; command line | GeoCSV paths, config | files in `data/processed/` |

Keep functions pure where possible: data in, data out, no hidden file or network access.

## 6. QC rules

Thresholds go in `config/qc_rules.yaml`. The values below are the starting defaults.

| Id | Applies to | Rule | Default | Flag |
|---|---|---|---|---|
| R01 | t_bmx_c, t_mcp_c, t_sht_c | Outside plausible range | below -5 or above 45 °C | 2 |
| R02 | rh_pct | Outside range | ≤ 0 or above 100 % | 2 |
| R03 | p_station_hpa | Outside site range (1523 m) | below 800 or above 900 hPa | 2 |
| R04 | wind_speed_ms, wind_gust_ms | Outside range | below 0, or above 60 (speed) / 75 (gust) m/s | 2 |
| R05 | rain1_mm, rain2_mm | Outside per-minute range | below 0 or above 10 mm | 2 |
| R06 | light_vis_counts, light_ir_counts | Below dark floor | below 240 counts | 1 |
| R07 | thermometers | Step change between consecutive rows no more than 120 s apart | above 5 °C per minute | 1 |
| R08 | t_sht_c, rh_pct | Flat line: identical value for consecutive rows | 120 or more rows | 1 |
| R08b | p_station_hpa | Flat line | 180 or more rows | 1 |
| R08c | wind_speed_ms | Flat line, **excluding zero** (calm nights are real) | 180 or more non-zero identical rows | 1 |
| R09 | thermometers | Any pair differs | above 2.0 °C | 1 on all three |
| R10 | wind_gust_ms | Gust below speed | gust below speed | 1 |
| R11 | rain_gauge_2 vs rain_gauge_1 (daily) | One gauge records ≥ 0.4 mm in a UTC day, the other reports and sums to 0 (values flagged 2 are not counted) | 0.4 mm | 1 on every channel of the zero gauge for that day |
| R12 | any variable (daily) | Empty for the whole UTC day | all null | 3; the group counts as *bad* in the health score |
| R13 | wind_gust_dir_deg (daily) | Identical to wind_gust_ms | ≥ 99 % of rows in the day | 2; exclude the column |
| R14 | time | Interval between rows | above 300 s creates a `gaps` row; 120 to 300 s inclusive counts as "late" (info only) | none |
| R15 | health_code | Non-zero device code | any non-zero | info note only (meaning undocumented) |
| R16 | wbgt_fw_c | Below the firmware wet bulb | wbgt_fw_c < wet_bulb_fw_c | 1, note `wbgt_below_wet_bulb` |

## 7. Flag codes

| Code | Meaning |
|---|---|
| 0 | good |
| 1 | suspect |
| 2 | bad |
| 3 | missing |
| 4 | filled (reserved; not used in the MVP) |

## 8. Daily health score

For each UTC day, score every channel group in section 3 **except `derived_fw`**. Firmware-derived values are judged by the audit in section 9, not by the health score; otherwise R16 would mark every day suspect because of a formula choice, not a sensor problem.

- A channel group is **bad** if one of its channels is empty for the day (R12; a day without any observations counts as empty), or more than 5 % of its rows are flagged 2, or R13 fired.
- A channel group is **suspect** if it is not bad and more than 5 % of its rows are flagged 1, or R11 fired for it that day.
- `missing_minutes` is the missing time that falls inside the day. A gap's missing time runs from one expected interval (60 s) after the last observation to the next observation, and is split at UTC midnight. A three-day outage therefore charges each day its own share, and the fully empty days score 0.
- `score = max(0, 100 − 10 × n_bad_groups − 2 × n_suspect_groups − missing_minutes / 14.4)`, rounded to one decimal place. 14.4 minutes is 1 % of a day.

Weights (10, 2, 14.4) and the 5 % share come from config. The report must print this rule next to the chart.

## 9. Derived-variable audit

| Audit id | What | Method | Verdict rule |
|---|---|---|---|
| A01 | Firmware wet bulb vs Stull (2011) applied to t_sht_c and rh_pct | Mean and max absolute difference | "matches Stull" if MAE ≤ 0.1 °C |
| A02 | Firmware heat index vs NWS Rothfusz heat index | MAE; note the NWS formula is designed for hot conditions | Report only |
| A03 | Firmware WBGT vs firmware wet bulb | Share of rows where WBGT < wet bulb, split day and night (night = 19:00 to 05:59 EAT) | "non-standard" if the share is above 1 % |
| A04 | Firmware WBGT vs a standards-grade estimate | Liljegren et al. (2008) via `pywbgt`, or `thermofeel`, or the Dimiceli approximation; needs calibrated solar input, so it waits for light calibration | Report difference by hour of day |
| A05 | Thermometer agreement | Pairwise mean and max absolute differences | Report only |

A04 depends on converting light counts to irradiance, which belongs to the application layer; stub it until then.

## 10. Station Health Report contents

The payload feeds `/v1/station-health` and the web page.

1. Station card: sensor_id, name, coordinates, elevation, record span, cadence, DOI, source files.
2. Coverage calendar: rows per UTC day, plus the gaps table.
3. Health score by day, with the rule text from section 8.
4. Channel-group status per day (good, suspect, bad) with the rule ids that caused it.
5. Thermometer agreement (A05).
6. Rain check: daily totals for both gauges; later add CHIRPS for comparison.
7. Light-sensor summary: dark floor and daily maxima. Calibration comes later.
8. Derived-variable audit results (A01 to A04).
9. Device codes seen (R15) with counts and "meaning undocumented".
10. Recommendations to JHUB, each worded by evidence level: confirm Rain Gauge 2 during the next rain; check battery telemetry export; fix the gust-direction export; document Health codes; consider a black-globe thermometer.
11. Links to the QC'd dataset download and the API documentation.

## 11. Acceptance tests (expected values from the organiser sample)

Files: `data/raw/organiser/` (see its README for exact names).

| Test | Expected |
|---|---|
| File 1 rows | 7,060; first 2026-08-28T00:00:25Z; last 2026-09-01T23:58:31Z |
| File 2 rows | 7,067; first 2026-08-31T00:00:24Z; last 2026-09-04T23:58:18Z |
| Columns per file | 26 |
| Duplicate timestamps removed when merging | 2,825 |
| Merged rows | 11,302; span 2026-08-28T00:00:25Z to 2026-09-04T23:58:18Z |
| Measurement count check | 169,440 (file 1) and 169,608 (file 2) = rows × 24 |
| Station metadata | sensor_id 61; lat -1.099736; lon 37.014528; elevation 1523.0 |
| Median interval | 61 s; minimum 60 s; maximum 755 s |
| Gaps above 300 s | exactly 1: interval 755 s ending 2026-08-30T03:45:32Z; missing_minutes 11.58 |
| Late intervals (120 to 300 s inclusive) | 22 (two intervals are exactly 120 s; 0.1 printed 21, which also counted the 755 s gap) |
| Hourly rows | 192 hours; exactly one hour below 54 observations: 2026-08-30T03:00Z with 48 |
| Rain Gauge 1 | total 0.4 mm; two 0.2 mm tips at 2026-08-31T00:13:44Z and 03:41:33Z |
| Rain Gauge 2 | total 0.0 mm; R11 fires on 2026-08-31 only |
| Battery Voltage | 0 non-null values; R12 fires every day |
| Wind Gust Direction | identical to Wind Gust on 100 % of rows; R13 fires every day |
| Health codes | 0: 11,280; 16: 12; 33501705: 9; 32: 1 |
| R01 to R07, R09, R10 | fire on 0 rows |
| Longest identical runs | t_sht_c 48 rows; rh_pct 12; p_station_hpa 18; wind_speed_ms 317 (all zeros, so R08c does not fire) |
| Max pairwise thermometer difference | SHT–MCP 1.6 °C; SHT–BMX 1.3 °C; BMX–MCP 1.1 °C |
| A01 Stull | MAE 0.032 °C; max 0.103 °C; verdict "matches Stull" |
| A03 WBGT below wet bulb | 5,833 of 11,302 rows (51.6 %); night 71.3 %; day 34.9 %; verdict "non-standard" |
| Daily health scores | 28 Aug 80.0; 29 Aug 80.0; 30 Aug 79.2; 31 Aug 78.0; 1 Sep 80.0; 2 Sep 80.0; 3 Sep 80.0; 4 Sep 80.0 (bad groups every day: battery, wind_gust_dir; suspect on 31 Aug: rain_gauge_2) |
| Observed ranges (merged) | t_sht_c 11.8 to 29.5; t_bmx_c 11.4 to 28.8; t_mcp_c 11.6 to 29.0; rh_pct 30.2 to 95.0; p_station_hpa 848.4 to 856.1; wind_speed_ms 0.0 to 3.0; wind_gust_ms 0.0 to 15.7; light_vis 257 to 1200; light_ir 251 to 10965; uv 0.0 to 5.1 |

## 12. Later (after the MVP works)

- Run on the full portal history if access is granted; re-check R11 and R12 conclusions with more rain and more days.
- ERA5-Land residual check via Open-Meteo (spatial consistency).
- CHIRPS comparison for the rain gauges.
- Light-sensor calibration against NASA POWER, which unlocks audit A04.
- Gap-filling with uncertainty (flag 4).
