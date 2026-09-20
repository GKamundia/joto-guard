"""Joto Guard on Telegram: the same guidance the web page shows, in a chat.

The bot holds no heat logic. It fetches the guidance document from the API and hands it to
`joto_guard.messages`, so the web page, the API and the bot can never disagree.

It also sends without being asked, which is the difference between a lookup tool and a
warning: a morning message before work starts, and an alert when the next day turns bad.

    export TELEGRAM_BOT_TOKEN=...      # from @BotFather
    export JOTO_API_BASE=...           # default http://127.0.0.1:8000
    python bot/joto_bot.py
"""

import logging
import os
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from joto_guard import messages
from joto_guard.subscriptions import Subscriptions

API_BASE = os.environ.get("JOTO_API_BASE", "http://127.0.0.1:8000").rstrip("/")
CACHE_FOR = timedelta(minutes=15)  # the forecast is refreshed far less often than this

#: Local time the morning message goes out, before outdoor work starts.
MORNING_LOCAL = time(hour=6, minute=30)
#: How often to look ahead for a spell worth warning about.
ALERT_EVERY = timedelta(hours=6)
#: How far ahead an alert looks.
ALERT_WINDOW_H = 24

TIMEZONE = "Africa/Nairobi"

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


def build(token: str, guidance: Guidance, people: Subscriptions | None = None) -> Application:
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

    subscribers = people if people is not None else Subscriptions.load()

    async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await answer(update, messages.start_message)

    async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        def confirm(document: dict) -> str:
            work_type = work_type_from(context.args, document)
            subscribers.subscribe(update.effective_chat.id, work_type)
            name = messages.WORK_NAMES.get(work_type, work_type).lower()
            return (
                f"Subscribed for {name}.\n\n"
                f"You will get a message each morning at {MORNING_LOCAL:%H:%M} with the day "
                "ahead, and a warning when the next 24 hours turn bad for that work.\n\n"
                "Send /subscribe with another type of work to change it, or /stop to stop."
            )

        await answer(update, confirm)

    async def stop(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        had = subscribers.unsubscribe(update.effective_chat.id)
        await update.message.reply_text(
            "Stopped. Nothing more will be sent unless you ask."
            if had
            else "You were not subscribed. /subscribe to start."
        )

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
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("stop", stop))

    if application.job_queue is not None:
        application.job_queue.run_daily(
            lambda context: send_morning(context, guidance, subscribers),
            time=MORNING_LOCAL.replace(tzinfo=ZoneInfo(TIMEZONE)),
            name="morning",
        )
        application.job_queue.run_repeating(
            lambda context: send_alerts(context, guidance, subscribers),
            interval=ALERT_EVERY,
            first=timedelta(seconds=30),
            name="alerts",
        )
    else:
        log.warning("no job queue: install python-telegram-bot[job-queue] to send unprompted")
    return application


async def send_morning(context, guidance: Guidance, subscribers: Subscriptions) -> None:
    """The day ahead, to everyone subscribed, before work starts."""
    if not subscribers.all():
        return
    document = await guidance.get()
    now = datetime.now(UTC)
    today = str(now.astimezone(ZoneInfo(document.get("timezone", TIMEZONE))).date())
    for person in subscribers.all():
        try:
            text = messages.morning_message(document, person.work_type, today, now)
        except messages.NoGuidance as gap:
            log.info("no morning message for %s: %s", person.chat_id, gap)
            continue
        await _send(context, person.chat_id, text)


async def send_alerts(context, guidance: Guidance, subscribers: Subscriptions) -> None:
    """A warning when the next day contains work that has to stop or slow down."""
    if not subscribers.all():
        return
    document = await guidance.get()
    now = datetime.now(UTC)
    zone = ZoneInfo(document.get("timezone", TIMEZONE))
    today = str(now.astimezone(zone).date())
    threshold = messages.bands_rank(messages.ALERT_FROM)

    for person in subscribers.all():
        level, hour = messages.worst_ahead(document, person.work_type, now, ALERT_WINDOW_H)
        if level is None or messages.bands_rank(level) < threshold:
            continue
        if not subscribers.needs_alert(person.chat_id, today, level, messages.LEVELS):
            continue
        await _send(
            context, person.chat_id, messages.alert_message(document, person.work_type, level, hour)
        )
        subscribers.record_alert(person.chat_id, today, level)


async def _send(context, chat_id: int, text: str) -> None:
    try:
        await context.bot.send_message(chat_id=chat_id, text=text)
    except Exception as problem:
        log.warning("could not reach %s: %s", chat_id, problem)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN. Copy .env.example to .env and fill it in.")
    people = Subscriptions.load(
        Path(os.environ.get("JOTO_SUBSCRIPTIONS", "data/subscriptions.json"))
    )
    log.info("reading guidance from %s, %d subscribers", API_BASE, len(people.all()))
    build(token, Guidance(API_BASE), people).run_polling()


if __name__ == "__main__":
    main()
