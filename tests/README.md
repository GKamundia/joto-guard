# tests/

`pytest`, no network access.

- `conduit_sentinel/test_*.py`: unit tests per module. Rule tests build small observation tables with the `make_obs` fixture in `conftest.py`.
- `conduit_sentinel/test_acceptance.py`: the expected values in `docs/SENTINEL_SPEC.md` section 11, run on the two organiser CSVs in `data/raw/organiser/`. They are skipped, with a message, when those files are missing. To read the files from another folder, set `CONDUIT_ORGANISER_DIR`.
- `fixtures/`: small GeoCSV files for the ingest and pipeline tests.

```bash
pytest                                        # everything
pytest tests/conduit_sentinel/test_qc.py -q   # one module
```
