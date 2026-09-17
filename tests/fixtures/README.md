# tests/fixtures/

Small inputs for unit tests. Keep each under a few hundred rows.

| File | Contents |
|---|---|
| `conduit_part_a.csv` | GeoCSV with the first 6 rows of the organiser sample (28 Aug 2026, 00:00 to 00:05 UTC) |
| `conduit_part_b.csv` | GeoCSV with rows 5 to 10 of the same sample, so it overlaps part A by 2 timestamps |

The data rows are copied from the organiser sample. The `#` metadata headers are written by hand in the documented CHORDS format (key: value pairs, spec section 2), with `Measurements in File` set to rows × 24 non-empty variables.

Rule-level QC tests build observation tables in code instead (`make_obs` in `tests/conftest.py`), because a flat line, a gap or a thermometer disagreement is clearer as a few lines of Python than as a CSV file.
