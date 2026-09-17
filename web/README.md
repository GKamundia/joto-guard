# web/ (React + Vite + Leaflet)

The **Station Health Report**: how far the Conduit@Empathy1 station can be trusted, and what to fix. Every figure comes from `GET /v1/station-health`; the page holds no numbers of its own.

```bash
npm install
npm run dev      # http://localhost:5173, expects the API on http://127.0.0.1:8000
npm run build    # production build into dist/
```

Point it at another API with `VITE_API_BASE`, for example `VITE_API_BASE=https://api.example.org npm run build`.

| Section | Source in the report |
|---|---|
| Station, files read | `station` |
| Daily health score and the scoring rule | `health` |
| Coverage, export periods, interruptions | `coverage` |
| Sensor groups day by day | `channel_status`, `rules` |
| The station's own calculated columns | `audits`, `thermometer_agreement` |
| Rain, light, device codes | `rain`, `light`, `device_codes` |
| What we suggest to JHUB | `recommendations` |
| Downloads | `/v1/dataset/...` |

It is built mobile first and checked at 375 px: cards stack and wide tables scroll inside their card rather than the page. Application pages come after decision 0003.
