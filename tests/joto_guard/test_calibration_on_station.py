"""The light-sensor calibration on the real station and ERA5 reference.

Skipped unless the organiser exports are in data/raw/organiser and the reference saved by
scripts/fetch_solar_reference.py is in data/reference.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from conduit_sentinel.pipeline import run
from joto_guard.solar_calibration import calibrate, ghi_hourly, reference_from_open_meteo

ROOT = Path(__file__).resolve().parents[2]
EXPORTS = sorted((ROOT / "data" / "raw" / "organiser").glob("*.csv"))
REFERENCE = ROOT / "data" / "reference" / "open_meteo_era5_2026-08-28_2026-09-15.json"

pytestmark = pytest.mark.skipif(
    len(EXPORTS) < 3 or not REFERENCE.exists(),
    reason="needs the organiser exports and the ERA5 reference (scripts/fetch_solar_reference.py)",
)

# The five days with the least minute-to-minute scatter in the light counts around noon.
CLEAR_DAYS = [
    date(2026, 8, 28),
    date(2026, 8, 29),
    date(2026, 9, 2),
    date(2026, 9, 3),
    date(2026, 9, 4),
]


@pytest.fixture(scope="module")
def fitted(config):
    sentinel = run(EXPORTS, config)
    station = sentinel.report["station"]
    location = (station["latitude"], station["longitude"])
    dark_floor = sentinel.report["light"]["night_counts"]["light_ir_counts"]["median"]
    reference = reference_from_open_meteo(json.loads(REFERENCE.read_text()))
    calibration = calibrate(sentinel.hourly, reference, *location, dark_floor, "ERA5")
    return calibration, ghi_hourly(sentinel.hourly, calibration, *location)


def test_sensor_reads_weaker_when_the_sun_is_low(fitted):
    calibration, _ = fitted
    assert calibration.dark_floor_counts == 253
    assert calibration.b > 0


def test_clear_days_peak_where_the_september_sun_should(fitted):
    _, estimates = fitted
    peaks = estimates.groupby(estimates["hour_utc"].dt.date)["ghi_wm2"].max()

    for day in CLEAR_DAYS:
        assert 800 <= peaks[day] <= 1100, day


def test_nights_read_zero(fitted):
    _, estimates = fitted
    assert (estimates.loc[estimates["cos_zenith"] == 0, "ghi_wm2"] == 0).all()


def test_skill_on_days_left_out_of_the_fit(fitted):
    calibration, _ = fitted
    assert (calibration.n_days, calibration.first_day, calibration.last_day) == (
        10,
        "2026-08-28",
        "2026-09-12",
    )
    assert calibration.held_out["daylight"]["rmse_wm2"] < 170
    # the station and a 25 km grid cell disagree about clouds; under a clear reference sky
    # the error roughly halves
    assert calibration.held_out["clear_reference_sky"]["rmse_wm2"] < 100
