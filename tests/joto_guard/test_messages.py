from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from joto_guard import bands, messages
from joto_guard.guidance import forecast_guidance

TIMEZONE = "Africa/Nairobi"


@pytest.fixture(scope="module")
def document(config_path):
    guidance = bands.load_guidance(config_path.parent / "heat_guidance.yaml")
    # 06:00 to 17:00 in Nairobi, rising into the heat of the day and back down.
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
    station = {"name": "Conduit@Empathy1", "latitude": -1.1, "longitude": 37.0}
    return forecast_guidance(
        table, guidance, station, TIMEZONE, "ecmwf_ifs", datetime(2026, 9, 20, tzinfo=UTC)
    )


def test_start_message_lists_the_commands_and_the_work_types(document):
    text = messages.start_message(document)

    assert "/now" in text and "/today" in text and "/tomorrow" in text
    for work_type in messages.work_types(document):
        assert work_type in text


def test_now_message_gives_the_hour_its_level_and_its_minutes(document):
    text = messages.now_message(document, datetime(2026, 9, 20, 8, 30, tzinfo=UTC), "heavy")

    assert "Heavy work (Kazi nzito) · 11:00" in text  # 08:30 UTC falls in the 11:00 Nairobi hour
    assert "WBGT 27.5 °C, likely 26.5 to 28.5." in text
    assert "Work in spells with rest in the shade." in text
    assert "Fanya kazi kwa vipindi, ukipumzika kivulini." in text
    assert "Used to the heat: 30 min of work in the hour." in text
    assert "New to the heat: this work should wait." in text
    assert "Drink about a cup" in text


def test_light_work_is_easier_than_heavy_work_in_the_same_hour(document):
    at = datetime(2026, 9, 20, 8, 30, tzinfo=UTC)

    assert "Used to the heat: 60 min" in messages.now_message(document, at, "light")
    assert "Used to the heat: 30 min" in messages.now_message(document, at, "heavy")


def test_now_message_outside_the_forecast_is_refused(document):
    with pytest.raises(messages.NoGuidance):
        messages.now_message(document, datetime(2026, 9, 25, tzinfo=UTC), "heavy")


def test_day_message_gives_the_peak_the_window_and_the_hours_to_watch(document):
    text = messages.day_message(document, "2026-09-20", "heavy")

    assert "Highest 28.0 °C WBGT at 12:00." in text
    assert "need breaks from 10:00 to 14:00." in text
    assert "Hour by hour:" in text
    assert "12:00  28.0 °C  work in spells, 30 min per hour" in text
    assert "08:00  23.0 °C  new workers need breaks" in text  # no spell: 60 min is still allowed
    assert "06:00" not in text  # a normal hour is not worth a line


def test_day_message_can_skip_the_hours_already_past(document):
    rest_of_day = messages.day_message(
        document, "2026-09-20", "heavy", after=datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
    )

    assert "08:00" not in rest_of_day  # 05:00 UTC, already past
    assert "13:00  27.0 °C" in rest_of_day


def test_a_day_that_only_limits_new_workers_says_so(document):
    text = messages.day_message(document, "2026-09-20", "light")

    assert "New workers need breaks for 3 of the day's 12 hours." in text
    assert "work in spells" not in text


def test_a_cool_day_says_no_limit_is_reached(config_path):
    guidance = bands.load_guidance(config_path.parent / "heat_guidance.yaml")
    hours = pd.date_range("2026-09-20T03:00Z", periods=12, freq="h")
    table = pd.DataFrame({"hour_utc": hours, "wbgt_c": np.full(12, 18.0)})
    document = forecast_guidance(
        table, guidance, {}, TIMEZONE, "ecmwf_ifs", datetime(2026, 9, 20, tzinfo=UTC)
    )

    text = messages.day_message(document, "2026-09-20", "very_heavy")

    assert "No heat limit is reached." in text
    assert "Hour by hour:" not in text


def test_day_message_outside_the_forecast_is_refused(document):
    with pytest.raises(messages.NoGuidance):
        messages.day_message(document, "2026-10-01", "heavy")
