import numpy as np
import pandas as pd
import pytest

from joto_guard.solar import cos_zenith, earth_sun_distance, hourly_mean_cos_zenith, hourly_sun

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


def test_earth_is_nearest_the_sun_in_january_and_farthest_in_july():
    distance = earth_sun_distance(pd.DatetimeIndex(["2026-01-03T12:00Z", "2026-07-06T12:00Z"]))
    assert distance == pytest.approx([0.9833, 1.0167], abs=2e-4)


def test_hourly_sun_through_a_day():
    hours = pd.date_range("2026-09-01T00:00Z", periods=24, freq="h")
    sun = hourly_sun(hours, *JKUAT)

    assert list(sun.columns) == ["cos_zenith_hour", "cos_zenith_sunlit", "earth_sun_distance_au"]
    night = sun["cos_zenith_hour"] == 0
    assert (sun.loc[night, "cos_zenith_sunlit"] == 0).all()
    assert night.sum() == 11  # 16:00 to 02:00 UTC hold no sunlight
    # the hour mean agrees with the coarser mean the light calibration uses
    assert sun["cos_zenith_hour"].to_numpy() == pytest.approx(
        hourly_mean_cos_zenith(hours, *JKUAT), abs=1e-3
    )


def test_sunlit_mean_differs_from_the_hour_mean_only_at_sunrise_and_sunset():
    hours = pd.date_range("2026-09-01T03:00Z", periods=13, freq="h")
    sun = hourly_sun(hours, *JKUAT)
    ratio = sun["cos_zenith_sunlit"] / sun["cos_zenith_hour"]

    # 03:00 and 15:00 UTC: the sun is up for only part of the hour
    assert ratio.iloc[0] > 2
    assert ratio.iloc[-1] > 1.5
    assert ratio.iloc[1:-1].to_numpy() == pytest.approx(1.0)
