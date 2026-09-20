# web/ (React + Vite + Leaflet)

The Joto Guard page. Five tabs over two endpoints' worth of data; the page holds no numbers of its own.

```bash
npm install
npm run dev      # http://localhost:5173, expects the API on http://127.0.0.1:8000
npm run build    # production build into dist/
```

Point it at another API with `VITE_API_BASE`, for example `VITE_API_BASE=https://api.example.org npm run build`.

| Tab | What it answers | Source |
|---|---|---|
| Guidance | Can this work go ahead in this hour, and when must it stop? | `/v1/heat-guidance` |
| Forecast | What is WBGT doing for three days, and how far can the correction be trusted? | `/v1/forecast` |
| Station record | What did the station itself measure, and what is its WBGT column worth? | `/v1/wbgt`, `/v1/station-health` |
| Station health | How far can the station be trusted, day by day and sensor by sensor? | `/v1/station-health` |
| Method | How a reading becomes advice | `/v1/heat-guidance` |

Guidance and Station health must load; Forecast and Station record say so and stay usable if their own endpoint fails.

## Conventions

- **Colour, spacing and radius are tokens** on `:root` in `src/styles.css`, redefined once for dark. Components never hard-code a colour.
- **Themes.** The page follows the device unless the header button sets `data-theme`, which is kept in `localStorage` and wins over the device setting.
- **Severity is never colour alone.** Every level carries its name in text or a pill, because the four fills have to work for a colour-blind reader and in sunlight.
- **Built mobile first and checked at 375 px**: cards stack, the tab row scrolls sideways instead of wrapping, and wide tables scroll inside their card rather than the page. From 62 rem the hour strip switches to one column per hour of the day, so the same hour lines up across days.
- **Layout belongs in the stylesheet.** The only inline styles left are the two that carry data: the matrix's column count and an hour's own column.
