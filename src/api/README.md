# src/api/ (FastAPI)

Serves what `python -m conduit_sentinel` and `python -m joto_guard` last wrote. The outputs are re-read whenever they change on disk, so re-running either pipeline refreshes the API without a restart.

```bash
pip install -e ".[api,dev]"
python -m conduit_sentinel data/raw/organiser --out data/processed
python -m joto_guard wbgt
python -m joto_guard forecast
uvicorn api.app:app --reload
```

| Endpoint | Returns |
|---|---|
| `GET /v1/stations` | The station registry with its latest health score and the periods the exports cover |
| `GET /v1/station-health` | The Station Health Report payload (spec section 10), which the web page renders |
| `GET /v1/qc?days=7` | Health, sensor-group status, rule firings and gaps over the most recent covered days |
| `GET /v1/history?var=t_sht_c&start=&end=` | One hourly variable as a series, with its unit |
| `GET /v1/wbgt?days=7` | The station's hourly WBGT (Liljegren model), the firmware's WBGT column minus it by local hour, and the light-sensor calibration |
| `GET /v1/heat-guidance` | The latest forecast's heat guidance: WBGT with its band, and for each hour and type of work the NIOSH level and minutes of work allowed per hour |
| `GET /v1/dataset/{name}` | Download an output file, for example `obs_qc.csv` or `heat_guidance.json` |

OpenAPI documentation at `/docs`. `SENTINEL_DATA_DIR` sets where the outputs are read from (default `data/processed`) and `JOTO_CONFIG_DIR` where the light calibration is (default `config`); without them an endpoint answers 503 saying which command to run.
