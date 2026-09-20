# bot/ (Telegram)

`joto_bot.py` answers the same guidance the web page shows, in a Telegram chat.

| Command | Answers |
|---|---|
| `/start`, `/help` | what Joto Guard is and which work types it knows |
| `/now` | the current hour: WBGT, what the level means, and the minutes of work it allows |
| `/today` | the rest of today: the peak, the window needing breaks, and every hour above normal |
| `/tomorrow` | the same for tomorrow |
| `/subscribe` | be told without asking: a morning message and a warning when it turns bad |
| `/stop` | stop those messages |

Add a work type to any command, for example `/today light`. Without one the bot answers for
heavy work, which covers the quarrying, construction and farming the evidence points to
around Juja (`docs/PROBLEM_EVIDENCE.md`).

## Sending without being asked

A lookup tool waits to be opened; a warning has to arrive. Two jobs do that:

- **06:30 East Africa Time**, every day: the day ahead for each subscriber's type of work.
- **Every six hours**: if the next 24 hours contain an hour that needs work and rest spells
  or worse, a short warning naming the hour. At most one a day per subscriber, unless the
  forecast worsens, which is worth saying again.

Subscriptions live in `data/subscriptions.json`, one line per chat, and nothing else. There
is no database for the same reason the rest of the project has none.

The bot holds no heat logic. It reads `GET /v1/heat-guidance` from the API and hands the
document to `joto_guard.messages`, whose wording is tested in `tests/joto_guard/test_messages.py`.
That way the page, the API and the bot cannot disagree, and the messages can be tested without
a token or a network.

## Running it

Create the bot with [@BotFather](https://t.me/BotFather), then:

```bash
pip install -e ".[api,bot]"
```

```bash
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN
```

```bash
set -a && . ./.env && set +a && python bot/joto_bot.py
```

It reads the API at `JOTO_API_BASE` (default `http://127.0.0.1:8000`), so the API must be
running and `python -m joto_guard forecast` must have written the guidance. `docker compose up`
starts all three together.
