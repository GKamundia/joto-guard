# tests/fixtures/

Small inputs for unit tests. Keep each under a few hundred rows.

| File | Contents |
|---|---|
| `conduit_part_a.csv` | Rows 1 to 6 of the first organiser file (28 Aug 2026, 00:00 to 00:05 UTC) |
| `conduit_part_b.csv` | Rows 5 to 10 of the same file, so it overlaps part A by 2 timestamps |
| `open_meteo_ecmwf_ifs_forecast.json` | The first 49 hourly stamps (48 station hours) of an ECMWF IFS forecast for the station from the Open-Meteo forecast API, fetched 19 Sep 2026: 19 Sep 00:00 to 21 Sep 00:00 UTC. Weather data by Open-Meteo.com, CC BY 4.0 |

Both are cut from `data/raw/organiser/3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy1.csv` with its 18-line `#` header copied as is. The only change is `Measurements in File`, set to 144 (6 rows × 24 non-empty variables).

Rule-level QC tests build observation tables in code instead (`make_obs` in `tests/conftest.py`), because a flat line, a gap or a thermometer disagreement is clearer as a few lines of Python than as a CSV file.
