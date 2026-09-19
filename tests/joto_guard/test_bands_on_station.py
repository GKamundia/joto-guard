"""Heat guidance on the real station record (28 Aug to 15 Sep 2026).

Skipped unless the organiser exports are in data/raw/organiser.
"""

from pathlib import Path

import pytest

from conduit_sentinel.pipeline import run
from joto_guard import bands
from joto_guard.solar_calibration import load
from joto_guard.station_wbgt import wbgt_hourly

ROOT = Path(__file__).resolve().parents[2]
EXPORTS = sorted((ROOT / "data" / "raw" / "organiser").glob("*.csv"))

pytestmark = pytest.mark.skipif(len(EXPORTS) < 3, reason="needs the organiser exports")


@pytest.fixture(scope="module")
def days(config):
    sentinel = run(EXPORTS, config)
    station = sentinel.report["station"]
    series = wbgt_hourly(
        sentinel.hourly,
        load(ROOT / "config" / "solar_calibration.json"),
        station["latitude"],
        station["longitude"],
    )
    guidance = bands.load_guidance(ROOT / "config" / "heat_guidance.yaml")
    by_hour = bands.guidance_by_hour(series, guidance, value="wbgt_c", high=None)
    summaries = bands.day_summaries(by_hour, config.station.display_timezone)
    return summaries[summaries["hours"] == 24].set_index(["work_type", "date"])


def test_heavy_work_needed_breaks_around_midday_on_about_half_the_days(days):
    heavy = days.loc["heavy"]
    limited = heavy[heavy["hours_work_rest"] > 0]

    assert len(heavy) == 11
    assert 4 <= len(limited) <= 8
    assert limited["limited_from"].min() >= "09:00"
    assert limited["limited_until"].max() <= "17:00"


def test_light_work_never_needed_breaks_and_nothing_needed_rescheduling(days):
    assert (days.loc["light", "hours_work_rest"] == 0).all()
    assert (days["hours_reschedule"] == 0).all()


def test_new_workers_are_limited_more_often_than_acclimatized_ones(days):
    moderate = days.loc["moderate"]
    assert moderate["hours_acclimatized_only"].sum() > 5 * moderate["hours_work_rest"].sum()
