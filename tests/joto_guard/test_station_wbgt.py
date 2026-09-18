import json

import numpy as np
import pandas as pd
import pytest

from joto_guard.__main__ import main
from joto_guard.solar_calibration import Calibration, save
from joto_guard.station_wbgt import firmware_by_local_hour, mean_difference, wbgt_hourly

JKUAT = (-1.099736, 37.014528)
CALIBRATION = Calibration(
    dark_floor_counts=253.0,
    a=0.135,
    b=0.099,
    reference="test",
    first_day="2026-08-28",
    last_day="2026-08-29",
    n_days=2,
    n_hours=24,
    held_out={},
)


def station_hours(days=2, **columns):
    """Sentinel's obs_hourly for a steady, sunny site; keyword arguments replace columns."""
    hours = pd.date_range("2026-08-28T00:00Z", periods=24 * days, freq="h")
    daylight = (hours.hour >= 4) & (hours.hour <= 14)
    hourly = pd.DataFrame(
        {
            "hour_utc": hours,
            "t_sht_c": 22.0,
            "rh_pct": 55.0,
            "p_station_hpa": 852.0,
            "wind_speed_ms": 1.0,
            "light_ir_counts": np.where(daylight, 4000.0, 253.0),
            "wbgt_fw_c": 16.0,
            "wet_bulb_fw_c": 16.5,
        }
    )
    for name, values in columns.items():
        hourly[name] = values
    return hourly


def test_one_row_per_station_hour_with_inputs_outputs_and_firmware_values():
    table = wbgt_hourly(station_hours(), CALIBRATION, *JKUAT)

    assert list(table.columns) == [
        "hour_utc",
        "t_air_c",
        "rh_pct",
        "p_station_hpa",
        "wind_ms",
        "ghi_wm2",
        "cos_zenith",
        "solar_wm2",
        "fdir",
        "wind_2m_ms",
        "tg_c",
        "tnwb_c",
        "tpsy_c",
        "wbgt_c",
        "wbgt_fw_c",
        "wet_bulb_fw_c",
    ]
    assert len(table) == 48
    assert table["wbgt_c"].notna().all()
    assert (table["t_air_c"] == 22.0).all()  # the SHT thermometer
    night = table["cos_zenith"] == 0
    assert (table.loc[night, "ghi_wm2"] == 0).all()
    # the sun raises WBGT above its night value
    assert table.loc[~night, "wbgt_c"].max() > table.loc[night, "wbgt_c"].max() + 3


def test_hours_missing_an_input_have_no_wbgt():
    wind = np.ones(48)
    wind[[3, 10]] = np.nan
    table = wbgt_hourly(station_hours(wind_speed_ms=wind), CALIBRATION, *JKUAT)

    assert table["wbgt_c"].isna().tolist() == [i in (3, 10) for i in range(48)]


def test_daylight_without_light_counts_has_no_wbgt_but_night_does():
    counts = station_hours()["light_ir_counts"].to_numpy().copy()
    counts[[1, 9]] = np.nan  # 01:00 UTC is night, 09:00 UTC is midday
    table = wbgt_hourly(station_hours(light_ir_counts=counts), CALIBRATION, *JKUAT)

    assert table["wbgt_c"].notna()[1]
    assert table["wbgt_c"].isna()[9]


def test_measured_wind_is_brought_down_to_2_m():
    table = wbgt_hourly(station_hours(), CALIBRATION, *JKUAT, wind_height_m=10.0)

    assert (table["wind_ms"] == 1.0).all()
    assert (table["wind_2m_ms"] < 1.0).all()


def test_firmware_is_compared_by_local_hour():
    hours = pd.date_range("2026-08-28T00:00Z", periods=48, freq="h")
    table = pd.DataFrame(
        {
            "hour_utc": hours,
            "wbgt_c": 20.0,
            "wbgt_fw_c": np.where(hours.hour == 9, 14.0, 19.0),
        }
    )
    table.loc[0, "wbgt_fw_c"] = np.nan
    by_hour = firmware_by_local_hour(table, "Africa/Nairobi")

    assert by_hour["local_hour"].tolist() == list(range(24))
    noon = by_hour.set_index("local_hour").loc[12]  # 09:00 UTC is 12:00 in Nairobi
    assert (noon["n_hours"], noon["fw_minus_model_c"]) == (2, -6.0)
    assert by_hour.set_index("local_hour").loc[3, "n_hours"] == 1  # the missing value
    assert mean_difference(by_hour, [11, 12]) == pytest.approx(-3.5)
    assert np.isnan(mean_difference(by_hour, [99]))


def write_processed(directory, hourly):
    directory.mkdir()
    hourly.assign(hour_utc=hourly["hour_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")).to_csv(
        directory / "obs_hourly.csv", index=False
    )
    report = {"station": {"latitude": JKUAT[0], "longitude": JKUAT[1]}}
    (directory / "report.json").write_text(json.dumps(report))


def test_command_line_writes_the_series_and_the_firmware_comparison(tmp_path, config_path, capsys):
    processed = tmp_path / "processed"
    write_processed(processed, station_hours())
    calibration = tmp_path / "solar_calibration.json"
    save(CALIBRATION, calibration)

    code = main(
        [
            "wbgt",
            "--processed",
            str(processed),
            "--calibration",
            str(calibration),
            "--config",
            str(config_path),
        ]
    )

    assert code == 0
    series = pd.read_csv(processed / "wbgt_hourly.csv")
    assert len(series) == 48
    assert series["hour_utc"].iloc[0] == "2026-08-28T00:00:00Z"
    by_hour = pd.read_csv(processed / "wbgt_firmware_by_hour.csv")
    assert by_hour["n_hours"].sum() == 48
    out = capsys.readouterr().out
    assert "WBGT for 48 of 48 station hours" in out
    assert "at night" in out


def test_command_line_reports_a_missing_calibration(tmp_path, config_path, capsys):
    processed = tmp_path / "processed"
    write_processed(processed, station_hours())

    code = main(
        [
            "wbgt",
            "--processed",
            str(processed),
            "--calibration",
            str(tmp_path / "none.json"),
            "--config",
            str(config_path),
        ]
    )

    assert code == 1
    assert "error" in capsys.readouterr().err
