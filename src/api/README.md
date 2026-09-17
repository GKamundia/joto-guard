# src/api/ (FastAPI)

Serves what `python -m conduit_sentinel` last wrote. The outputs are re-read whenever they change on disk, so re-running the pipeline refreshes the API without a restart.

```bash
pip install -e ".[api,dev]"
python -m conduit_sentinel data/raw/organiser --out data/processed
uvicorn api.app:app --reload
```

| Endpoint | Returns |
|---|---|
| `GET /v1/stations` | The station registry with its latest health score and the periods the exports cover |
| `GET /v1/station-health` | The Station Health Report payload (spec section 10), which the web page renders |
| `GET /v1/qc?days=7` | Health, sensor-group status, rule firings and gaps over the most recent covered days |
| `GET /v1/history?var=t_sht_c&start=&end=` | One hourly variable as a series, with its unit |
| `GET /v1/dataset/{name}` | Download a quality-controlled table, for example `obs_qc.csv` |

OpenAPI documentation at `/docs`. `SENTINEL_DATA_DIR` sets where the outputs are read from (default `data/processed`); without them every endpoint answers 503 saying which command to run.

Application endpoints are added after decision 0003.
