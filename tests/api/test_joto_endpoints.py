import json
import shutil

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.app import create_app

HOURS = pd.date_range("2026-09-10T00:00Z", periods=24 * 10, freq="h")


@pytest.fixture
def processed(tmp_path):
    """Joto Guard's outputs, small and made up."""
    directory = tmp_path / "processed"
    directory.mkdir()
    pd.DataFrame(
        {
            "hour_utc": HOURS.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "t_air_c": 22.0,
            "rh_pct": 55.0,
            "wind_2m_ms": 1.0,
            "ghi_wm2": 0.0,
            "tg_c": 23.0,
            "tnwb_c": 17.0,
            "wbgt_c": 19.0,
            "wbgt_fw_c": 16.0,
            "cos_zenith": 0.0,
        }
    ).to_csv(directory / "wbgt_hourly.csv", index=False)
    pd.DataFrame({"local_hour": range(24), "n_hours": 10, "fw_minus_model_c": -3.0}).to_csv(
        directory / "wbgt_firmware_by_hour.csv", index=False
    )
    pd.DataFrame(
        {
            "hour_utc": HOURS[:6].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "t_air_c": 24.0,
            "rh_pct": 50.0,
            "wind_2m_ms": 1.2,
            "ghi_wm2": 700.0,
            "cos_zenith": 0.9,
            "tg_c": 35.0,
            "tnwb_c": 18.0,
            "wbgt_c": 23.0,
            "wbgt_corrected_c": 25.0,
            "wbgt_low_c": 23.5,
            "wbgt_high_c": 26.5,
        }
    ).to_csv(directory / "wbgt_forecast.csv", index=False)
    guidance = {"forecast": {"model": "ecmwf_ifs"}, "hours": [{"wbgt_c": 25.1}], "days": []}
    (directory / "heat_guidance.json").write_text(json.dumps(guidance))
    return directory


@pytest.fixture
def configs(tmp_path, config_path):
    directory = tmp_path / "config"
    directory.mkdir()
    shutil.copy(config_path.parent / "solar_calibration.json", directory)
    shutil.copy(config_path.parent / "forecast_correction.json", directory)
    return directory


def client_for(processed, configs):
    return TestClient(create_app(processed, config_dir=configs))


def test_heat_guidance_serves_what_the_forecast_wrote(processed, configs):
    body = client_for(processed, configs).get("/v1/heat-guidance").json()
    assert body["forecast"]["model"] == "ecmwf_ifs"
    assert body["hours"][0]["wbgt_c"] == 25.1


def test_heat_guidance_follows_the_file(processed, configs):
    client = client_for(processed, configs)
    assert client.get("/v1/heat-guidance").json()["hours"][0]["wbgt_c"] == 25.1

    (processed / "heat_guidance.json").write_text(json.dumps({"hours": [{"wbgt_c": 30.0}]}))
    assert client.get("/v1/heat-guidance").json()["hours"][0]["wbgt_c"] == 30.0


def test_forecast_serves_both_series_the_band_and_the_weather_behind_them(processed, configs):
    body = client_for(processed, configs).get("/v1/forecast").json()

    assert body["model"] == "ecmwf_ifs"
    hour = body["hours"][0]
    assert (hour["wbgt_c"], hour["wbgt_corrected_c"]) == (23.0, 25.0)
    assert (hour["wbgt_low_c"], hour["wbgt_high_c"]) == (23.5, 26.5)
    assert hour["t_air_c"] == 24.0 and hour["ghi_wm2"] == 700.0
    assert "cos_zenith" not in hour  # an intermediate the page has no use for


def test_forecast_reports_how_well_the_correction_did_on_held_out_days(processed, configs):
    body = client_for(processed, configs).get("/v1/forecast").json()

    held_out = body["correction"]["held_out"]["all"]
    assert held_out["corrected"]["mae_c"] < held_out["raw"]["mae_c"]
    assert len(body["correction"]["offsets_c"]) == 24
    assert body["correction"]["fitted_on"]["n_days"] > 0


def test_wbgt_returns_recent_hours_the_firmware_gap_and_the_calibration(processed, configs):
    body = client_for(processed, configs).get("/v1/wbgt", params={"days": 2}).json()

    assert body["n_hours"] == 48
    assert set(body["hours"][0]) == {
        "hour_utc",
        "t_air_c",
        "rh_pct",
        "wind_2m_ms",
        "ghi_wm2",
        "tg_c",
        "tnwb_c",
        "wbgt_c",
        "wbgt_fw_c",
    }
    assert body["hours"][-1]["hour_utc"] == "2026-09-19T23:00:00Z"
    assert len(body["firmware_by_local_hour"]) == 24
    assert body["light_calibration"]["dark_floor_counts"] == 253
    assert "daylight" in body["light_calibration"]["held_out"]


def test_missing_outputs_say_what_to_run(tmp_path, configs):
    empty = tmp_path / "empty"
    empty.mkdir()
    client = client_for(empty, configs)

    for path in ("/v1/heat-guidance", "/v1/wbgt"):
        response = client.get(path)
        assert response.status_code == 503
        assert "python -m joto_guard" in response.json()["detail"]


def test_joto_outputs_can_be_downloaded(processed, configs):
    response = client_for(processed, configs).get("/v1/dataset/heat_guidance.json")
    assert response.status_code == 200
    assert response.json()["forecast"]["model"] == "ecmwf_ifs"


def test_index_lists_the_new_endpoints(processed, configs):
    endpoints = client_for(processed, configs).get("/").json()["endpoints"]
    assert "/v1/heat-guidance" in endpoints
    assert "/v1/wbgt?days=7" in endpoints
    assert "/v1/forecast" in endpoints
