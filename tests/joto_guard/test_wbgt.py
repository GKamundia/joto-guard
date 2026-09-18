import numpy as np
import pandas as pd
import pytest

from joto_guard.solar import cos_zenith, earth_sun_distance, hourly_sun
from joto_guard.wbgt import (
    MAX_CLEARNESS,
    MIN_WIND_MS,
    SOLAR_CONSTANT,
    direct_beam,
    liljegren,
    saturation_vapour_pressure,
    stability_class,
    wbgt_for_hours,
    wind_at_reference_height,
)

JKUAT = (-1.099736, 37.014528)

# Liljegren's own program (WBGT v1.1, calc_wbgt, compiled unchanged) on these inputs. The
# irradiance, direct share and cos zenith are the values it derived from the date, place
# and measured irradiance; wind is at 2 m. Its iteration stops at 0.02 K.
#   air degC, RH %, hPa, wind m/s, W/m2, fdir, cos zenith -> globe, natural wet bulb,
#   psychrometric wet bulb, WBGT (degC)
ORIGINAL = [
    # JKUAT 1 Sep 09:30 UTC, sunny, light wind
    ((28, 40, 852, 1.0, 900.0, 0.712765, 0.986814), (48.3233, 21.5639, 17.7491, 27.5594)),
    # JKUAT 1 Sep 21:30 UTC, calm humid night
    ((15, 85, 852, 0.0, 0.0, 0.0, -0.992678), (12.3539, 12.7179, 13.3787, 12.8733)),
    # hot, humid and sunny at sea level
    ((33, 65, 1010, 2.5, 950.0, 0.725457, 0.999403), (48.1206, 28.8586, 27.2160, 33.1251)),
    # hot, dry and windy
    ((38, 15, 950, 6.0, 800.0, 0.676270, 0.867033), (46.9492, 19.7904, 18.2530, 27.0431)),
    # low morning sun
    ((16, 80, 852, 0.5, 200.0, 0.586275, 0.245834), (26.1289, 16.3478, 13.7475, 18.2693)),
    # overcast noon, almost no direct beam
    ((21, 70, 852, 1.5, 300.0, 0.010073, 0.987832), (28.5064, 18.8612, 17.0519, 21.0041)),
    # 1300 W/m2 measured, capped at 85 % of the top of the atmosphere
    ((26, 50, 852, 1.0, 1125.692505, 0.9, 0.986814), (49.7022, 21.7798, 18.1285, 27.7863)),
]


def run(inputs):
    return liljegren(*zip(*inputs, strict=True))


def test_matches_the_original_program_to_within_its_tolerance():
    result = run([inputs for inputs, _ in ORIGINAL])
    expected = np.array([outputs for _, outputs in ORIGINAL])

    assert list(result.columns) == ["tg_c", "tnwb_c", "tpsy_c", "wbgt_c"]
    np.testing.assert_allclose(result.to_numpy(), expected, atol=0.02)


def test_wbgt_is_the_weighted_sum_of_its_parts():
    result = run([inputs for inputs, _ in ORIGINAL])
    air = np.array([inputs[0] for inputs, _ in ORIGINAL])

    weighted = 0.1 * air + 0.2 * result["tg_c"] + 0.7 * result["tnwb_c"]
    np.testing.assert_allclose(result["wbgt_c"], weighted)


def test_on_a_calm_clear_night_globe_and_wick_cool_below_the_air():
    night = liljegren(15, 85, 852, 0.0, 0.0, 0.0, 0.0).iloc[0]

    # both radiate to a sky colder than the air
    assert night["tg_c"] < 15
    assert night["tnwb_c"] < night["tpsy_c"]
    # so even the standard index can sit a little below the wet bulb
    assert -1.0 < night["wbgt_c"] - night["tpsy_c"] < 0


def test_wind_pulls_the_globe_towards_air_temperature():
    calm, windy = liljegren(20, 60, 852, [0.5, 10.0], 0.0, 0.0, 0.0)["tg_c"]

    # at night the globe still loses heat to the sky, but a strong wind replaces most of it
    assert calm < windy < 20
    assert 20 - windy < (20 - calm) / 2


def test_psychrometric_wet_bulb_equals_air_temperature_in_saturated_air():
    result = liljegren(20, 100, 852, 3.0, 0.0, 0.0, 0.0).iloc[0]
    assert result["tpsy_c"] == pytest.approx(20, abs=0.01)


def test_wet_bulb_is_lower_at_the_station_pressure_than_at_sea_level():
    station, sea_level = liljegren(28, 40, [852, 1013.25], 2.0, 0.0, 0.0, 0.0)["tpsy_c"]
    assert station < sea_level - 0.2


def test_more_sun_raises_wbgt_and_more_wind_lowers_it():
    sun = liljegren(25, 50, 852, 1.0, [0.0, 300.0, 600.0, 900.0], 0.7, 0.9)["wbgt_c"]
    wind = liljegren(25, 50, 852, [0.5, 1.0, 3.0, 6.0], 800.0, 0.7, 0.9)["wbgt_c"]

    assert sun.is_monotonic_increasing and sun.is_unique
    assert wind.is_monotonic_decreasing and wind.is_unique


def test_wind_below_the_floor_counts_as_the_floor():
    still, floor = liljegren(25, 50, 852, [0.0, MIN_WIND_MS], 800.0, 0.7, 0.9)["wbgt_c"]
    assert still == pytest.approx(floor)


def test_a_missing_input_leaves_only_its_row_missing():
    result = liljegren([25, 25, np.nan], [50, np.nan, 50], 852, 1.0, 500.0, 0.5, 0.8)

    assert result.iloc[0].notna().all()
    assert result.iloc[1].isna().all()
    assert result.iloc[2].isna().all()


def test_saturation_vapour_pressure():
    # Buck (1981) gives 23.37 hPa at 20 degC; Liljegren adds 0.4 % for moist air
    assert saturation_vapour_pressure(293.15) == pytest.approx(23.37 * 1.004, abs=0.01)


def top_of_atmosphere(time, cos_zenith):
    distance = earth_sun_distance(pd.DatetimeIndex([time]))[0]
    return SOLAR_CONSTANT * cos_zenith / distance**2


def test_direct_beam_share_matches_the_original_program():
    toa = top_of_atmosphere("2026-09-01T09:30Z", 0.986814)
    solar, fdir = direct_beam([900.0, 1300.0], [toa, toa])

    assert solar == pytest.approx([900.0, 1125.6925], abs=0.05)
    assert fdir == pytest.approx([0.712765, 0.9], abs=1e-4)


def test_irradiance_is_capped_at_85_percent_of_the_top_of_the_atmosphere():
    solar, fdir = direct_beam([2000.0, 50.0], [1000.0, 1000.0])

    assert solar[0] == pytest.approx(MAX_CLEARNESS * 1000)
    assert solar[1] == 50.0
    assert 0 < fdir[1] < 0.01  # a dull sky is nearly all diffuse
    assert fdir[0] == 0.9  # the share never exceeds 0.9


def test_without_a_sun_all_light_is_diffuse_and_kept():
    solar, fdir = direct_beam([0.0, 40.0], [0.0, 0.0])
    assert solar.tolist() == [0.0, 40.0]
    assert fdir.tolist() == [0.0, 0.0]


def test_stability_classes():
    day = stability_class(True, [1.0, 1.0, 2.5, 7.0], [950, 100, 700, 950])
    night = stability_class(False, [1.0, 1.0, 3.0], 0.0, [0.0, -0.5, 0.0])

    # by day: strong sun and light wind are very unstable, weak sun is neutral
    assert day.tolist() == [1, 4, 2, 3]
    # by night: light wind is stable, moderate wind neutral
    assert night.tolist() == [6, 5, 4]


def test_wind_from_10_m_down_to_2_m_matches_the_original_program():
    day = wind_at_reference_height(1.0, 10.0, stability_class(True, 1.0, 900.0))
    night = wind_at_reference_height(1.5, 10.0, stability_class(False, 1.5, 0.0))

    assert day == pytest.approx(0.8935, abs=1e-4)
    assert night == pytest.approx(0.6190, abs=1e-4)


def test_wind_at_2_m_is_used_as_measured():
    assert wind_at_reference_height([0.0, 3.0], 2.0, [6, 6]).tolist() == [0.0, 3.0]


def test_adjusted_wind_never_drops_below_the_floor():
    assert wind_at_reference_height(0.0, 10.0, 6) == MIN_WIND_MS


def test_hourly_wbgt_through_a_day():
    hours = pd.date_range("2026-09-01T00:00Z", periods=24, freq="h")
    result = wbgt_for_hours(hours, 20.0, 60.0, 852.0, 1.0, 0.0, *JKUAT)

    assert list(result.columns) == [
        "hour_utc",
        "cos_zenith",
        "solar_wm2",
        "fdir",
        "wind_2m_ms",
        "tg_c",
        "tnwb_c",
        "tpsy_c",
        "wbgt_c",
    ]
    assert (result["hour_utc"] == hours).all()
    # no irradiance at all: every hour is the same whatever the sun angle
    assert result["wbgt_c"].nunique() == 1
    assert (result["fdir"] == 0).all()


def test_sunrise_hour_uses_the_sun_after_it_rises():
    # the sun rises at about 03:33 UTC, so at 03:30, the middle of the hour, it is still down
    hour = pd.DatetimeIndex(["2026-09-01T03:00Z"])
    assert cos_zenith(hour + pd.Timedelta(minutes=30), *JKUAT)[0] < 0
    sun = hourly_sun(hour, *JKUAT).iloc[0]
    toa = SOLAR_CONSTANT * sun["cos_zenith_hour"] / sun["earth_sun_distance_au"] ** 2

    result = wbgt_for_hours(hour, 16.0, 80.0, 852.0, 1.0, 0.5 * toa, *JKUAT).iloc[0]

    assert result["cos_zenith"] == pytest.approx(sun["cos_zenith_sunlit"], abs=1e-4)
    # judged against the hour's own top-of-atmosphere sunlight, half of it is half clear
    assert result["fdir"] == pytest.approx(np.exp(3 - 1.34 * 0.5 - 1.65 / 0.5), abs=1e-3)
