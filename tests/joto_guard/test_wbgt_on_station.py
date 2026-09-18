"""The station's WBGT from the organiser exports and the tracked light calibration.

Skipped unless the organiser exports are in data/raw/organiser.
"""

from pathlib import Path

import pytest

from conduit_sentinel.audit import is_night
from conduit_sentinel.pipeline import run
from joto_guard.solar_calibration import load
from joto_guard.station_wbgt import firmware_by_local_hour, mean_difference, wbgt_hourly

ROOT = Path(__file__).resolve().parents[2]
EXPORTS = sorted((ROOT / "data" / "raw" / "organiser").glob("*.csv"))
CALIBRATION = ROOT / "config" / "solar_calibration.json"

pytestmark = pytest.mark.skipif(len(EXPORTS) < 3, reason="needs the organiser exports")


@pytest.fixture(scope="module")
def series(config):
    sentinel = run(EXPORTS, config)
    station = sentinel.report["station"]
    table = wbgt_hourly(
        sentinel.hourly, load(CALIBRATION), station["latitude"], station["longitude"]
    )
    local = table["hour_utc"].dt.tz_convert(config.station.display_timezone)
    return table.assign(local_hour=local.dt.hour, local_day=local.dt.date)


def test_every_hour_with_inputs_has_a_wbgt(series):
    inputs = ["t_air_c", "rh_pct", "p_station_hpa", "wind_ms", "ghi_wm2"]
    complete = series[inputs].notna().all(axis=1)

    assert (series["wbgt_c"].notna() == complete).all()
    # 13 full days; 5 to 10 September is in no export
    assert (len(series), int(complete.sum())) == (456, 312)


def test_firmware_reads_far_below_the_model_in_the_sun(series, config):
    by_hour = firmware_by_local_hour(series, config.station.display_timezone)

    assert mean_difference(by_hour, range(10, 16)) < -4
    assert mean_difference(by_hour, range(8, 12)) < -6


def test_night_values_below_the_wet_bulb_separate_firmware_from_model(series, config):
    night = series[
        is_night(series["local_hour"], config.audit.night_start_hour, config.audit.night_end_hour)
    ].dropna(subset=["wbgt_c", "wbgt_fw_c", "wet_bulb_fw_c"])
    model = night["wbgt_c"] - night["wet_bulb_fw_c"]
    firmware = night["wbgt_fw_c"] - night["wet_bulb_fw_c"]

    # on calm clear nights the standard index itself dips a little below the wet bulb
    assert (model < 0).mean() > 0.2
    assert model.min() > -1.0
    # the firmware goes several times further
    assert firmware.min() < -3.0
    assert (firmware < -1.0).mean() > 0.5


def test_daily_peak_comes_with_or_before_the_air_temperature_peak(series):
    full_days = series.groupby("local_day").filter(
        lambda day: day["wbgt_c"].notna().all() and len(day) == 24
    )
    days = full_days.groupby("local_day")

    wbgt_peak = full_days.loc[days["wbgt_c"].idxmax()].set_index("local_day")["local_hour"]
    air_peak = full_days.loc[days["t_air_c"].idxmax()].set_index("local_day")["local_hour"]
    lead = air_peak - wbgt_peak

    # the sun's share of WBGT peaks near solar noon (12:30 local), the air later
    assert len(lead) >= 10
    assert lead.between(0, 4).all()
    assert days["wbgt_c"].max().between(20, 30).all()
