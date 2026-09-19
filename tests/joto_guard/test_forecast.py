import io
import json
import urllib.error

import numpy as np
import pandas as pd
import pytest

from joto_guard import forecast
from joto_guard.__main__ import main
from joto_guard.forecast import (
    INPUT_COLUMNS,
    fetch_json,
    forecast_wbgt,
    hourly_inputs,
    request_params,
    variable_name,
)

JKUAT = (-1.099736, 37.014528)


@pytest.fixture
def ecmwf(fixtures_dir):
    """48 hours of a real ECMWF IFS forecast for the station, from 19 Sep 2026 00:00 UTC."""
    return json.loads((fixtures_dir / "open_meteo_ecmwf_ifs_forecast.json").read_text())


def payload(times, lead_day=0, **columns):
    """An Open-Meteo response; every variable is 0 unless given."""
    hourly = {"time": times}
    for variable in forecast.VARIABLES:
        name = variable_name(variable, lead_day)
        hourly[name] = columns.get(variable, [0.0] * len(times))
    return {"timezone": "GMT", "hourly": hourly}


def test_lead_days_are_named_as_open_meteo_names_them():
    assert variable_name("temperature_2m") == "temperature_2m"
    assert variable_name("temperature_2m", 2) == "temperature_2m_previous_day2"


def test_request_asks_for_utc_hours_in_metres_per_second_at_the_station_height():
    params = request_params(*JKUAT, 1523.0, lead_days=(0, 1), forecast_days=3)

    assert params["timezone"] == "GMT"
    assert params["wind_speed_unit"] == "ms"
    assert params["elevation"] == "1523"
    assert params["models"] == "ecmwf_ifs"
    assert params["forecast_days"] == "3"
    hourly = params["hourly"].split(",")
    assert len(hourly) == 10
    assert "shortwave_radiation" in hourly
    assert "wind_speed_10m_previous_day1" in hourly


def test_hour_means_from_values_at_the_stamps_and_radiation_from_the_hour_after():
    times = ["2026-09-19T08:00", "2026-09-19T09:00", "2026-09-19T10:00"]
    inputs = hourly_inputs(
        payload(times, temperature_2m=[20.0, 22.0, 25.0], shortwave_radiation=[500, 700, 800])
    )

    assert list(inputs.columns) == INPUT_COLUMNS
    assert inputs["hour_utc"].tolist() == [
        pd.Timestamp("2026-09-19T08:00Z"),
        pd.Timestamp("2026-09-19T09:00Z"),
    ]
    assert inputs["t_air_c"].tolist() == [21.0, 23.5]
    # radiation stamped 09:00 averages 08:00 to 09:00
    assert inputs["ghi_wm2"].tolist() == [700, 800]


def test_a_missing_value_leaves_the_hours_it_touches_missing():
    times = ["2026-09-19T08:00", "2026-09-19T09:00", "2026-09-19T10:00", "2026-09-19T11:00"]
    inputs = hourly_inputs(payload(times, relative_humidity_2m=[50, None, 60, 60]))

    assert inputs["rh_pct"].isna().tolist() == [True, True, False]


def test_earlier_forecasts_are_read_by_lead_day():
    times = ["2026-09-19T08:00", "2026-09-19T09:00"]
    inputs = hourly_inputs(payload(times, lead_day=2, temperature_2m=[18.0, 20.0]), lead_day=2)

    assert inputs["t_air_c"].tolist() == [19.0]
    with pytest.raises(ValueError, match="temperature_2m_previous_day1"):
        hourly_inputs(payload(times, lead_day=2), lead_day=1)


def test_a_response_in_local_time_is_refused():
    response = payload(["2026-09-19T08:00", "2026-09-19T09:00"]) | {"timezone": "Africa/Nairobi"}
    with pytest.raises(ValueError, match="timezone=GMT"):
        hourly_inputs(response)


def test_wbgt_for_a_real_forecast(ecmwf):
    table = forecast_wbgt(ecmwf, *JKUAT)

    assert len(table) == 48
    assert table["wbgt_c"].notna().all()
    # 10 m wind is brought down to 2 m
    windy = table["wind_10m_ms"] > 1
    assert (table.loc[windy, "wind_2m_ms"] < table.loc[windy, "wind_10m_ms"]).all()
    local_hour = table["hour_utc"].dt.tz_convert("Africa/Nairobi").dt.hour
    midday = table.loc[local_hour.between(11, 14), "wbgt_c"]
    night = table.loc[local_hour.isin([1, 2, 3, 4]), "wbgt_c"]
    assert 20 < midday.mean() < 28
    assert night.max() < midday.min()


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_decodes_json_and_sends_the_parameters(monkeypatch):
    seen = {}

    def urlopen(request, timeout):
        seen["url"] = request.full_url
        return FakeResponse(b'{"hourly": {"time": []}}')

    monkeypatch.setattr(forecast.urllib.request, "urlopen", urlopen)
    assert fetch_json("https://example.org/v1/forecast", {"models": "ecmwf_ifs"}) == {
        "hourly": {"time": []}
    }
    assert seen["url"] == "https://example.org/v1/forecast?models=ecmwf_ifs"


def test_fetch_reports_the_reason_open_meteo_gives(monkeypatch):
    def urlopen(request, timeout):
        body = io.BytesIO(b'{"error": true, "reason": "Latitude must be in range"}')
        raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, body)

    monkeypatch.setattr(forecast.urllib.request, "urlopen", urlopen)
    with pytest.raises(ValueError, match="Latitude must be in range"):
        fetch_json("https://example.org/v1/forecast", {})


def processed_dir(tmp_path):
    directory = tmp_path / "processed"
    directory.mkdir()
    station = {"latitude": JKUAT[0], "longitude": JKUAT[1], "elevation_m": 1523.0}
    (directory / "report.json").write_text(json.dumps({"station": station}))
    return directory


def test_command_line_computes_a_saved_forecast(tmp_path, fixtures_dir, config_path, capsys):
    processed = processed_dir(tmp_path)
    saved = fixtures_dir / "open_meteo_ecmwf_ifs_forecast.json"

    code = main(
        [
            "forecast",
            "--processed",
            str(processed),
            "--payload",
            str(saved),
            "--config",
            str(config_path),
            "--correction",
            str(tmp_path / "none.json"),
        ]
    )

    assert code == 0
    table = pd.read_csv(processed / "wbgt_forecast.csv")
    assert len(table) == 48
    assert table["hour_utc"].iloc[0] == "2026-09-19T00:00:00Z"
    assert "wbgt_corrected_c" not in table
    guidance = json.loads((processed / "heat_guidance.json").read_text())
    assert len(guidance["hours"]) == 48
    assert set(guidance["work_types"]) == {"light", "moderate", "heavy", "very_heavy"}
    assert guidance["forecast"]["corrected_towards_station"] is False
    out = capsys.readouterr().out
    assert "2026-09-20: highest WBGT" in out
    assert "Raw model output" in out


def test_command_line_saves_what_it_fetches(tmp_path, ecmwf, config_path, monkeypatch):
    processed = processed_dir(tmp_path)
    requests = []

    def fetch(url, params):
        requests.append(params)
        return ecmwf

    monkeypatch.setattr("joto_guard.__main__.fetch_json", fetch)
    raw = tmp_path / "raw"

    code = main(
        [
            "forecast",
            "--processed",
            str(processed),
            "--raw-dir",
            str(raw),
            "--days",
            "2",
            "--config",
            str(config_path),
            "--correction",
            str(tmp_path / "none.json"),
        ]
    )

    assert code == 0
    assert requests[0]["forecast_days"] == "2"
    assert requests[0]["elevation"] == "1523"
    (saved,) = raw.glob("open_meteo_ecmwf_ifs_forecast_*.json")
    assert json.loads(saved.read_text()) == ecmwf
    assert np.isclose(
        pd.read_csv(processed / "wbgt_forecast.csv")["wbgt_c"].max(),
        forecast_wbgt(ecmwf, *JKUAT)["wbgt_c"].max(),
    )


def test_command_line_refuses_an_impossible_horizon(tmp_path, config_path, capsys):
    processed = processed_dir(tmp_path)
    code = main(["forecast", "--processed", str(processed), "--days", "30"])

    assert code == 1
    assert "--days" in capsys.readouterr().err
