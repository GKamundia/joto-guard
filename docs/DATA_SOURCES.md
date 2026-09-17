# Data sources and provenance

Record every dataset the app uses: where it came from, when it was obtained, its terms, and where it lives in this repo. Update this file whenever a new source is added.

## Conduit@Empathy1 (mandatory core data)

| Item | Detail |
|---|---|
| Instrument | "Kenya Kiambu JKUAT IOT AWS - Conduti@Empathy1", CHORDS sensor_id 61 |
| Portal | UCAR 3D-PAWS FEWS NET CHORDS portal, `3d-fewsnet.icdp.ucar.edu/instruments/61` |
| DOI | 10.5065/d6v1236q (attribution: 3d-fewsnet.icdp.ucar.edu) |
| Location | lat -1.099736, lon 37.014528, elevation 1523.0 m (JKUAT, Juja) |
| Organiser sample | Three GeoCSV files from the Hack The Weather Resources page (Google Drive folder "HackTheWeather2026-Data", https://drive.google.com/drive/folders/1KDoCh8vss7nv_B6SuVBlQQssjSh1yaBg, owner info.jhub@jkuat.ac.ke). Stored in `data/raw/organiser/`. No file covers 5 to 10 Sep 2026. |
| Portal history | 30 May 2025 onward (15,949,704 measurements on 17 Sep 2026). New portal accounts start as "guest"; downloading needs the "Registered User" and "Data Downloader" permissions, granted by a portal admin. Account registered 17 Sep 2026; download permission not granted as of that date. Stored in `data/raw/portal/` (git-ignored) if obtained. |
| Header units | The `field_unit` header line labels SHT Humidity as degC and Heat Index as #. The values are % and °C. Sentinel takes units from `docs/SENTINEL_SPEC.md` section 3, not from the header. |

| File | Obtained | Rows | Span (UTC) |
|---|---|---|---|
| `3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy1.csv` | 17 Sep 2026 | 7,060 | 2026-08-28T00:00:25Z to 2026-09-01T23:58:31Z |
| `3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy1(31-4).csv` | 17 Sep 2026 | 7,067 | 2026-08-31T00:00:24Z to 2026-09-04T23:58:18Z |
| `3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy11-15.csv` | 17 Sep 2026 | 7,062 | 2026-09-11T00:00:01Z to 2026-09-15T23:58:29Z |

## Derived files

| File | Made from | How |
|---|---|---|
| `data/interim/conduit_combined_minute.csv` | The two organiser files | Merged, 2,825 duplicate timestamps removed, 11,302 rows. Made during planning on 15 Sep 2026, before the build started; regenerate it with `conduit_sentinel` and treat the pipeline output as authoritative. |
| `data/processed/` (`obs_qc.csv`, `obs_hourly.csv`, `gaps.csv`, `health_daily.csv`, `channel_status_daily.csv`, `audit_results.csv`, `report.json`) | The GeoCSV files passed to Sentinel | `python -m conduit_sentinel data/raw/organiser --out data/processed`. Not tracked; rerun to regenerate. |

## External sources (add as used)

| Source | Use | Access | Terms | Obtained | Repo location |
|---|---|---|---|---|---|
| _e.g. Open-Meteo Historical Weather API_ | | | | | `data/reference/` |
