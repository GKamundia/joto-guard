# Deploying Joto Guard

Three pieces: the API (FastAPI), the page (a static Vite build) and the Telegram bot. The
page and the bot both read the API, so deploy the API first.

Everything below is free-tier. Nothing here needs the CHORDS portal: the API serves the
organiser exports bundled in `data/raw/organiser/`, and the forecast comes from Open-Meteo,
which needs no key.

## 1. Locally, in one command

```bash
docker compose up --build
```

The `pipeline` service runs Sentinel, then the WBGT model, then the forecast, and exits; the
API and the page start once it succeeds. The page is then on http://localhost:5173 and the
API on http://127.0.0.1:8000. The forecast step needs internet access; everything else works
offline. To run the bot too, put `TELEGRAM_BOT_TOKEN` in `.env` and add `--profile bot`.

## 2. The API on Render

1. Push this repository to GitHub.
2. On Render, **New → Blueprint**, choose the repository. It reads `render.yaml`.
3. Deploy. The first build takes a few minutes; the free plan sleeps after inactivity, so
   open the URL once before recording the demo.
4. Come back after step 3 below and set `JOTO_ALLOWED_ORIGINS` to the page's address, or the
   browser will refuse the API's responses.

The free plan has no disk, so the pipelines run at start-up and their outputs live in the
container. The API therefore serves the record the repository was deployed with.

## 3. The page on Vercel

1. On Vercel, **Add New → Project**, choose the repository, set the root directory to `web`.
   `web/vercel.json` supplies the rest.
2. Add one environment variable, `VITE_API_BASE`, set to the Render URL with no trailing
   slash, for example `https://joto-guard-api.onrender.com`. It is read at build time, so
   changing it needs a redeploy.
3. Deploy, then put the resulting address into `JOTO_ALLOWED_ORIGINS` on Render.

## 4. The bot

Any machine that can reach the API can run it:

```bash
TELEGRAM_BOT_TOKEN=... JOTO_API_BASE=https://joto-guard-api.onrender.com python bot/joto_bot.py
```

On Render it is a **Background Worker** from the same repository and Dockerfile, with the
command `python bot/joto_bot.py` and those two variables set. `/start` in Telegram confirms it.

## Checks before recording

- [ ] The API's `/` answers, and `/v1/heat-guidance` returns hours.
- [ ] The page loads with no console error, on a phone as well as a laptop.
- [ ] `/now` and `/today` answer in Telegram.
- [ ] The Render service has been woken from sleep.
