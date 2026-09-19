"""Joto Guard on Telegram: the same guidance the web page shows, in a chat.

The bot holds no heat logic. It fetches the guidance document from the API and hands it to
`joto_guard.messages`, so the web page, the API and the bot can never disagree.

    export TELEGRAM_BOT_TOKEN=...      # from @BotFather
    export JOTO_API_BASE=...           # default http://127.0.0.1:8000
    python bot/joto_bot.py
"""

import logging
import os
from datetime import UTC, datetime, timedelta

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from joto_guard import messages

API_BASE = os.environ.get("JOTO_API_BASE", "http://127.0.0.1:8000").rstrip("/")
CACHE_FOR = timedelta(minutes=15)  # the forecast is refreshed far less often than this

log = logging.getLogger("joto_bot")


class Guidance:
    """The guidance document, fetched on demand and kept for `CACHE_FOR`."""

    def __init__(self, base_url: str, cache_for: timedelta = CACHE_FOR):
        self._url = f"{base_url}/v1/heat-guidance"
        self._cache_for = cache_for
        self._document: dict | None = None
        self._fetched_at: datetime | None = None

    async def get(self) -> dict:
        now = datetime.now(UTC)
        if self._document is None or now - self._fetched_at > self._cache_for:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(self._url)
                response.raise_for_status()
                self._document = response.json()
            self._fetched_at = now
        return self._document


def work_type_from(args: list[str], document: dict) -> str:
    """The work type named in the command, or the default when none is."""
    if not args:
        return messages.DEFAULT_WORK_TYPE
    asked = args[0].lower().replace("-", "_")
    if asked not in document["work_types"]:
        known = ", ".join(document["work_types"])
        raise messages.NoGuidance(f"I do not know the work type '{args[0]}'. Try one of: {known}.")
    return asked


def local_date(document: dict, days_ahead: int) -> str:
    """Today's or a later day's date at the station, as the document writes dates."""
    available = messages.dates(document)
    wanted = str((datetime.now(UTC) + timedelta(days=days_ahead)).date())
    if wanted not in available:
        raise messages.NoGuidance(
            f"the forecast covers {available[0]} to {available[-1]}, not {wanted}."
        )
    return wanted


def build(token: str, guidance: Guidance) -> Application:
    async def reply(update: Update, text: str) -> None:
        await update.message.reply_text(text)

    async def answer(update: Update, build_text) -> None:
        """Run one command, turning a gap in the forecast into a plain answer."""
        try:
            document = await guidance.get()
            await reply(update, build_text(document))
        except messages.NoGuidance as gap:
            await reply(update, f"Sorry, {gap}")
        except httpx.HTTPError as problem:
            log.warning("cannot reach %s: %s", API_BASE, problem)
            await reply(update, "Sorry, I cannot reach the Joto Guard service just now.")

    async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await answer(update, messages.start_message)

    async def now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await answer(
            update,
            lambda document: messages.now_message(
                document, datetime.now(UTC), work_type_from(context.args, document)
            ),
        )

    async def day(update: Update, context: ContextTypes.DEFAULT_TYPE, days_ahead: int) -> None:
        await answer(
            update,
            lambda document: messages.day_message(
                document,
                local_date(document, days_ahead),
                work_type_from(context.args, document),
                after=datetime.now(UTC) if days_ahead == 0 else None,
            ),
        )

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("now", now))
    application.add_handler(CommandHandler("today", lambda u, c: day(u, c, 0)))
    application.add_handler(CommandHandler("tomorrow", lambda u, c: day(u, c, 1)))
    return application


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN. Copy .env.example to .env and fill it in.")
    log.info("reading guidance from %s", API_BASE)
    build(token, Guidance(API_BASE)).run_polling()


if __name__ == "__main__":
    main()
