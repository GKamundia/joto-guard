# bot/ (Telegram)

`joto_bot.py` answers the same guidance the web page shows, in a Telegram chat.

| Command | Answers |
|---|---|
| `/start`, `/help` | what Joto Guard is and which work types it knows |
| `/now` | the current hour: WBGT, what the level means, and the minutes of work it allows |
| `/today` | the rest of today: the peak, the window needing breaks, and every hour above normal |
| `/tomorrow` | the same for tomorrow |

Add a work type to any command, for example `/today light`. Without one the bot answers for
heavy work, which covers the quarrying, construction and farming the evidence points to
around Juja (`docs/PROBLEM_EVIDENCE.md`).

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
