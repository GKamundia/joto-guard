import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from joto_bot import Guidance, local_date, work_type_from
from joto_guard import messages
from joto_guard.subscriptions import Subscriptions


@pytest.fixture
def document():
    today = str(datetime.now(UTC).date())
    tomorrow = str((datetime.now(UTC) + timedelta(days=1)).date())
    return {
        "work_types": {"light": {}, "moderate": {}, "heavy": {}, "very_heavy": {}},
        "days": [{"date": today}, {"date": tomorrow}],
    }


def test_no_work_type_means_the_default(document):
    assert work_type_from([], document) == messages.DEFAULT_WORK_TYPE


@pytest.mark.parametrize("asked", ["heavy", "HEAVY", "very-heavy", "Very_Heavy"])
def test_a_named_work_type_is_taken_however_it_is_typed(asked, document):
    assert work_type_from([asked], document) in document["work_types"]


def test_an_unknown_work_type_is_refused_with_the_known_ones(document):
    with pytest.raises(messages.NoGuidance, match="light, moderate, heavy, very_heavy"):
        work_type_from(["quarrying"], document)


def test_today_and_tomorrow_are_in_the_forecast(document):
    assert local_date(document, 0) == document["days"][0]["date"]
    assert local_date(document, 1) == document["days"][1]["date"]


def test_a_day_the_forecast_does_not_reach_is_refused(document):
    with pytest.raises(messages.NoGuidance, match="the forecast covers"):
        local_date(document, 5)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    """Counts the calls, so the test can see the cache working."""

    calls = 0

    def __init__(self, *_, **__):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def get(self, _url):
        FakeClient.calls += 1
        return FakeResponse({"fetched": FakeClient.calls})


@pytest.fixture
def fake_client(monkeypatch):
    import httpx

    FakeClient.calls = 0
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    return FakeClient


def test_the_document_is_fetched_once_and_then_reused(fake_client):
    guidance = Guidance("http://api.test")

    assert asyncio.run(guidance.get()) == {"fetched": 1}
    assert asyncio.run(guidance.get()) == {"fetched": 1}
    assert fake_client.calls == 1


def test_a_stale_document_is_fetched_again(fake_client):
    guidance = Guidance("http://api.test", cache_for=timedelta(seconds=0))

    asyncio.run(guidance.get())
    assert asyncio.run(guidance.get()) == {"fetched": 2}


def test_the_documented_commands_are_all_registered():
    from joto_bot import build

    application = build("123456:test-token-shaped-like-a-real-one", Guidance("http://api.test"))

    registered = {
        command
        for handler in application.handlers[0]
        for command in getattr(handler, "commands", ())
    }
    assert registered == {"start", "help", "now", "today", "tomorrow", "subscribe", "stop"}


def test_subscribe_and_stop_are_registered_alongside_the_lookups():
    from joto_bot import build

    application = build(
        "123456:test-token-shaped-like-a-real-one",
        Guidance("http://api.test"),
        Subscriptions(),
    )

    registered = {
        command
        for handler in application.handlers[0]
        for command in getattr(handler, "commands", ())
    }
    assert {"subscribe", "stop"} <= registered


def test_the_morning_and_alert_jobs_are_scheduled():
    from joto_bot import build

    application = build(
        "123456:test-token-shaped-like-a-real-one",
        Guidance("http://api.test"),
        Subscriptions(),
    )

    assert {job.name for job in application.job_queue.jobs()} == {"morning", "alerts"}


class Recorder:
    """Stands in for the Telegram bot, so the jobs can be run without a network."""

    def __init__(self, fail_for=()):
        self.sent = []
        self.fail_for = set(fail_for)

    @property
    def bot(self):
        return self

    async def send_message(self, chat_id, text):
        if chat_id in self.fail_for:
            raise RuntimeError("chat blocked the bot")
        self.sent.append((chat_id, text))


def _guidance_with(document):
    guidance = Guidance("http://api.test")
    guidance._document = document
    guidance._fetched_at = datetime.now(UTC)
    return guidance


def _hot_document():
    """One day, hot enough that heavy work needs work/rest and light work does not."""
    import numpy as np
    import pandas as pd

    from joto_guard import bands
    from joto_guard.guidance import forecast_guidance

    root = Path(__file__).resolve().parents[2]
    guidance = bands.load_guidance(root / "config" / "heat_guidance.yaml")
    hours = pd.date_range("2026-09-20T03:00Z", periods=12, freq="h")
    wbgt = np.array([18.0, 20.0, 23.0, 25.0, 26.5, 27.5, 28.0, 27.0, 25.0, 22.0, 20.0, 19.0])
    table = pd.DataFrame(
        {
            "hour_utc": hours,
            "wbgt_c": wbgt - 2,
            "wbgt_corrected_c": wbgt,
            "wbgt_low_c": wbgt - 1,
            "wbgt_high_c": wbgt + 1,
        }
    )
    return forecast_guidance(
        table,
        guidance,
        {"name": "test"},
        "Africa/Nairobi",
        "ecmwf_ifs",
        datetime(2026, 9, 20, tzinfo=UTC),
    )


def test_nobody_subscribed_means_nothing_is_sent(monkeypatch):
    import joto_bot

    recorder = Recorder()
    asyncio.run(joto_bot.send_alerts(recorder, _guidance_with(_hot_document()), Subscriptions()))

    assert recorder.sent == []


def test_a_subscriber_is_warned_once_and_not_again_that_day(tmp_path, monkeypatch):
    import joto_bot

    monkeypatch.setattr(joto_bot, "datetime", _FrozenClock(datetime(2026, 9, 20, 3, tzinfo=UTC)))
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(7, "heavy")
    recorder = Recorder()
    guidance = _guidance_with(_hot_document())

    asyncio.run(joto_bot.send_alerts(recorder, guidance, people))
    asyncio.run(joto_bot.send_alerts(recorder, guidance, people))

    assert len(recorder.sent) == 1
    assert recorder.sent[0][0] == 7
    assert "Heat warning" in recorder.sent[0][1]


def test_light_work_is_not_warned_about_on_a_day_heavy_work_is(tmp_path, monkeypatch):
    import joto_bot

    monkeypatch.setattr(joto_bot, "datetime", _FrozenClock(datetime(2026, 9, 20, 3, tzinfo=UTC)))
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(7, "light")
    recorder = Recorder()

    asyncio.run(joto_bot.send_alerts(recorder, _guidance_with(_hot_document()), people))

    assert recorder.sent == []


def test_one_blocked_chat_does_not_stop_the_others(tmp_path, monkeypatch):
    import joto_bot

    monkeypatch.setattr(joto_bot, "datetime", _FrozenClock(datetime(2026, 9, 20, 3, tzinfo=UTC)))
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(1, "heavy")
    people.subscribe(2, "heavy")
    recorder = Recorder(fail_for={1})

    asyncio.run(joto_bot.send_alerts(recorder, _guidance_with(_hot_document()), people))

    assert [chat for chat, _ in recorder.sent] == [2]


def test_the_morning_message_goes_to_everyone_subscribed(tmp_path, monkeypatch):
    import joto_bot

    monkeypatch.setattr(joto_bot, "datetime", _FrozenClock(datetime(2026, 9, 20, 3, tzinfo=UTC)))
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(1, "heavy")
    people.subscribe(2, "light")
    recorder = Recorder()

    asyncio.run(joto_bot.send_morning(recorder, _guidance_with(_hot_document()), people))

    assert sorted(chat for chat, _ in recorder.sent) == [1, 2]
    assert all(text.startswith("Good morning") for _, text in recorder.sent)


class _FrozenClock:
    """Stands in for `datetime` so the jobs see a fixed moment."""

    def __init__(self, moment):
        self._moment = moment

    def now(self, tz=None):
        return self._moment if tz is None else self._moment.astimezone(tz)
