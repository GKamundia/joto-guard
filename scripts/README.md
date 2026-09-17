# scripts/

One-off data scripts, not part of the importable packages.

- `fetch_conduit_history.py`: downloads CHORDS instrument history month by month into `data/raw/portal/`, saving each chunk exactly as the portal sends it so that the GeoCSV `#` header survives and `python -m conduit_sentinel data/raw/portal` can read the station metadata from it. Needs `CHORDS_EMAIL` and `CHORDS_API_KEY` in the environment **and** "Registered User" plus "Data Downloader" permissions, which a portal admin grants; without them every request returns HTTP 406. Written during planning (15 Sep 2026) as a data-preparation helper.
