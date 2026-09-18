import numpy as np
import pandas as pd
import pytest

from joto_guard.solar import cos_zenith, hourly_mean_cos_zenith

JKUAT = (-1.099736, 37.014528)


def minutes_of(day):
    return pd.date_range(f"{day}T00:00Z", periods=1440, freq="min")


def test_solar_noon_at_jkuat_on_1_september():
    times = minutes_of("2026-09-01")
    cosine = cos_zenith(times, *JKUAT)

    # 37.01 E puts solar noon 2 h 28 min before 12:00 UTC; the equation of time is near 0
    assert times[int(np.argmax(cosine))].strftime("%H:%M") == "09:32"
    # declination about +8.2 deg at latitude -1.1 deg leaves the noon sun 9.3 deg off overhead
    assert np.degrees(np.arccos(cosine.max())) == pytest.approx(9.3, abs=0.1)


def test_sun_is_nearly_overhead_at_the_september_equinox():
    cosine = cos_zenith(minutes_of("2026-09-23"), *JKUAT)
    assert np.degrees(np.arccos(cosine.max())) < 1.5


def test_twelve_hours_of_daylight_near_the_equator():
    daylight_minutes = (cos_zenith(minutes_of("2026-09-01"), *JKUAT) > 0).sum()
    assert 11.8 * 60 < daylight_minutes < 12.2 * 60


def test_time_zone_awareness_does_not_change_the_answer():
    naive_utc = cos_zenith(pd.DatetimeIndex(["2026-09-01T09:27"]), *JKUAT)
    nairobi = cos_zenith(pd.DatetimeIndex(["2026-09-01T12:27+03:00"]), *JKUAT)
    assert naive_utc == pytest.approx(nairobi)


def test_hourly_mean_is_zero_at_night_and_partial_at_sunrise():
    means = hourly_mean_cos_zenith(pd.date_range("2026-09-01T02:00Z", periods=4, freq="h"), *JKUAT)

    assert means[0] == 0
    # sunrise at 03:33 UTC leaves only the end of the 03:00 hour in sunlight
    assert 0 < means[1] < 0.05
    assert means[1] < means[2] < means[3]
