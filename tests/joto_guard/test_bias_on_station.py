"""The forecast correction on the real station series and the saved past forecasts.

Skipped unless the organiser exports are in data/raw/organiser and the past forecasts
saved by scripts/fetch_past_forecasts.py are in data/reference.
"""

import json
from pathlib import Path

import pytest

from conduit_sentinel.pipeline import run
from joto_guard import bias
from joto_guard.forecast import forecast_wbgt
from joto_guard.solar_calibration import load
from joto_guard.station_wbgt import wbgt_hourly

ROOT = Path(__file__).resolve().parents[2]
EXPORTS = sorted((ROOT / "data" / "raw" / "organiser").glob("*.csv"))
PAST = (
    ROOT / "data" / "reference" / "open_meteo_ecmwf_ifs_past_forecasts_2026-08-28_2026-09-15.json"
)

pytestmark = pytest.mark.skipif(
    len(EXPORTS) < 3 or not PAST.exists(),
    reason="needs the organiser exports and the past forecasts (scripts/fetch_past_forecasts.py)",
)


@pytest.fixture(scope="module")
def skill(config):
    sentinel = run(EXPORTS, config)
    station = sentinel.report["station"]
    location = (station["latitude"], station["longitude"])
    series = wbgt_hourly(
        sentinel.hourly, load(ROOT / "config" / "solar_calibration.json"), *location
    )
    payload = json.loads(PAST.read_text())
    forecasts = {lead: forecast_wbgt(payload, *location, lead) for lead in range(4)}
    pairs = bias.pair_forecasts(series, forecasts, config.station.display_timezone)
    return bias.evaluate(pairs)


def test_correction_beats_the_raw_forecast_and_the_usual_hour(skill):
    overall = skill["all"]
    assert overall["corrected"]["mae_c"] < overall["raw"]["mae_c"] - 0.3
    assert overall["corrected"]["mae_c"] < overall["station_usual"]["mae_c"]
    for lead in ("0", "1", "2", "3"):
        by_lead = skill["by_lead_day"][lead]
        assert by_lead["corrected"]["mae_c"] < by_lead["station_usual"]["mae_c"], lead


def test_band_holds_about_four_in_five_station_values(skill):
    assert 70 <= skill["band_held_station_pct"] <= 90
