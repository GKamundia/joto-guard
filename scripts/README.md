# scripts/

One-off data scripts, not part of the importable packages.

- `fetch_conduit_history.py`: downloads CHORDS instrument history month by month into `data/raw/portal/`. Needs `CHORDS_EMAIL` and `CHORDS_API_KEY` in the environment **and** the "Data Downloader" permission on the portal; without it the portal returns HTTP 406. Written during planning (15 Sep 2026) as a data-preparation helper.
