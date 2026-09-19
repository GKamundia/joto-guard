import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from joto_bot import Guidance, local_date, work_type_from
from joto_guard import messages


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
