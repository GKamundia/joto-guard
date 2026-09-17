# Data sources and provenance

Record every dataset the app uses: where it came from, when it was obtained, its terms, and where it lives in this repo. Update this file whenever a new source is added.

## Conduit@Empathy1 (mandatory core data)

| Item | Detail |
|---|---|
| Instrument | "Kenya Kiambu JKUAT IOT AWS - Conduti@Empathy1", CHORDS sensor_id 61 |
| Portal | UCAR 3D-PAWS FEWS NET CHORDS portal, `3d-fewsnet.icdp.ucar.edu/instruments/61` |
| DOI | 10.5065/d6v1236q (attribution: 3d-fewsnet.icdp.ucar.edu) |
| Location | lat -1.099736, lon 37.014528, elevation 1523.0 m (JKUAT, Juja) |
| Organiser sample | Two GeoCSV files from the Hack The Weather Resources page (Google Drive folder "HackTheWeather2026-Data", owner info.jhub@jkuat.ac.ke). Stored in `data/raw/organiser/`. |
| Portal history | 30 May 2025 onward. Downloading requires CHORDS "Data Downloader" permission. Stored in `data/raw/portal/` (git-ignored) if obtained. Record the date, account and any permission granted. |

| File | Obtained | Rows | Span (UTC) |
|---|---|---|---|
| `3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy1.csv` | _date you downloaded it_ | 7,060 | 2026-08-28T00:00:25Z to 2026-09-01T23:58:31Z |
| `3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy1(31-4).csv` | _date you downloaded it_ | 7,067 | 2026-08-31T00:00:24Z to 2026-09-04T23:58:18Z |

## Derived files

| File | Made from | How |
|---|---|---|
| `data/interim/conduit_combined_minute.csv` | The two organiser files | Merged, 2,825 duplicate timestamps removed, 11,302 rows. Made during planning on 15 Sep 2026, before the build started; regenerate it with `conduit_sentinel` and treat the pipeline output as authoritative. |

## External sources (add as used)

| Source | Use | Access | Terms | Obtained | Repo location |
|---|---|---|---|---|---|
| _e.g. Open-Meteo Historical Weather API_ | | | | | `data/reference/` |
