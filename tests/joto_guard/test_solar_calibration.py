import json

import numpy as np
import pandas as pd
import pytest

from joto_guard.__main__ import main
from joto_guard.solar import hourly_mean_cos_zenith
from joto_guard.solar_calibration import (
    Calibration,
    calibrate,
    estimate_ghi,
    fit,
    ghi_hourly,
    held_out_errors,
    load,
    reference_from_open_meteo,
    save,
    training_table,
)

JKUAT = (-1.099736, 37.014528)
FLOOR = 253.0
A, B = 0.135, 0.099


def synthetic(days=4, noise=0.0, seed=1):
    """Station hours, and a reference the model describes exactly apart from `noise`."""
    hours = pd.date_range("2026-08-28T00:00Z", periods=24 * days, freq="h")
    mu = hourly_mean_cos_zenith(hours, *JKUAT)
    rng = np.random.default_rng(seed)
    ghi = 1000 * mu * rng.uniform(0.6, 1.0, len(hours))
    counts = np.where(mu > 0, ghi / (A + B * (1 - mu)), 0) + FLOOR
    reference_ghi = np.clip(ghi + rng.normal(0, noise, len(hours)) * (mu > 0), 0, None)
    hourly = pd.DataFrame({"hour_utc": hours, "light_ir_counts": counts})
    reference = pd.DataFrame({"hour_utc": hours, "ghi_ref_wm2": reference_ghi})
    return hourly, reference


def calibration(**changes):
    values = {
        "dark_floor_counts": FLOOR,
        "a": A,
        "b": B,
        "reference": "test",
        "first_day": "2026-08-28",
        "last_day": "2026-08-31",
        "n_days": 4,
        "n_hours": 48,
        "held_out": {},
    }
    return Calibration(**{**values, **changes})


def test_open_meteo_values_move_to_the_hour_they_average():
    payload = {
        "timezone": "GMT",
        "hourly": {
            "time": ["2026-08-28T10:00", "2026-08-28T11:00"],
            "shortwave_radiation": [500.0, None],
            "cloud_cover": [10, 20],
        },
    }
    reference = reference_from_open_meteo(payload)

    assert reference["hour_utc"].tolist() == [pd.Timestamp("2026-08-28T09:00Z")]
    assert reference["ghi_ref_wm2"].tolist() == [500.0]
    assert reference["cloud_cover_pct"].tolist() == [10]


def test_reference_in_local_time_is_refused():
    payload = {"timezone": "Africa/Nairobi", "hourly": {"time": [], "shortwave_radiation": []}}
    with pytest.raises(ValueError, match="timezone=GMT"):
        reference_from_open_meteo(payload)


def test_training_keeps_daylight_hours_only():
    hourly, reference = synthetic(days=2)
    table = training_table(hourly, reference, *JKUAT, FLOOR)

    assert (table["mu"] > 0.05).all()
    assert 20 <= len(table) <= 26
    assert (table["ir_net"] >= 0).all()


def test_fit_recovers_the_coefficients():
    hourly, reference = synthetic()
    a, b = fit(training_table(hourly, reference, *JKUAT, FLOOR))

    assert (a, b) == (pytest.approx(A, abs=1e-6), pytest.approx(B, abs=1e-6))


def test_held_out_errors_vanish_when_the_model_is_exact():
    hourly, reference = synthetic()
    errors = held_out_errors(training_table(hourly, reference, *JKUAT, FLOOR))

    assert errors.abs().max() < 1e-6


def test_calibration_reports_skill_on_days_left_out():
    hourly, reference = synthetic(days=5, noise=30)
    result = calibrate(hourly, reference, *JKUAT, FLOOR, "synthetic")

    assert (result.first_day, result.last_day, result.n_days) == ("2026-08-28", "2026-09-01", 5)
    daylight = result.held_out["daylight"]
    assert 20 < daylight["rmse_wm2"] < 40
    assert daylight["r2"] > 0.9
    assert result.held_out["high_sun"]["n_hours"] < daylight["n_hours"]
    assert "clear_reference_sky" not in result.held_out  # no cloud cover in this reference


def test_clear_sky_skill_is_reported_when_the_reference_has_cloud_cover():
    hourly, reference = synthetic(days=3, noise=10)
    reference["cloud_cover_pct"] = np.where(reference.index % 2 == 0, 5, 90)
    result = calibrate(hourly, reference, *JKUAT, FLOOR, "synthetic")

    clear = result.held_out["clear_reference_sky"]
    assert 0 < clear["n_hours"] < result.held_out["daylight"]["n_hours"]


def test_calibration_needs_two_days():
    hourly, reference = synthetic(days=1)
    with pytest.raises(ValueError, match="two days"):
        calibrate(hourly, reference, *JKUAT, FLOOR, "synthetic")


def test_estimates_are_zero_with_the_sun_down_and_never_negative():
    counts = [FLOOR, 100.0, 5000.0, np.nan, np.nan, 5000.0]
    cos_zenith = [0.5, 0.5, 0.0, 0.5, 0.0, 1.0]
    estimates = estimate_ghi(counts, cos_zenith, calibration())

    assert estimates[:3].tolist() == [0.0, 0.0, 0.0]  # at the floor, below it, at night
    assert np.isnan(estimates[3])  # daylight without counts stays unknown
    assert estimates[4] == 0.0  # the night needs no sensor
    assert estimates[5] == pytest.approx((5000 - FLOOR) * A)


def test_estimates_for_every_station_hour():
    hourly, _ = synthetic(days=2)
    estimates = ghi_hourly(hourly, calibration(), *JKUAT)

    assert list(estimates.columns) == ["hour_utc", "cos_zenith", "ghi_wm2"]
    assert len(estimates) == len(hourly)
    assert (estimates.loc[estimates["cos_zenith"] == 0, "ghi_wm2"] == 0).all()
    assert estimates["ghi_wm2"].max() < 1000


def test_calibration_file_round_trip(tmp_path):
    original = calibration(held_out={"daylight": {"rmse_wm2": 12.5}})
    path = tmp_path / "solar_calibration.json"
    save(original, path)

    assert json.loads(path.read_text())["formula"].startswith("GHI = (IR counts - dark floor)")
    assert load(path) == original


def open_meteo_payload(reference):
    """The synthetic reference in Open-Meteo's shape: values stamped at the hour's end."""
    return {
        "latitude": -1.0,
        "longitude": 37.0,
        "timezone": "GMT",
        "hourly": {
            "time": (reference["hour_utc"] + pd.Timedelta(hours=1))
            .dt.strftime("%Y-%m-%dT%H:%M")
            .tolist(),
            "shortwave_radiation": reference["ghi_ref_wm2"].tolist(),
            "cloud_cover": [10] * len(reference),
        },
    }


def test_command_line_fits_and_writes_estimates(tmp_path, capsys):
    hourly, reference = synthetic(days=4, noise=5)
    processed = tmp_path / "processed"
    processed.mkdir()
    hourly.assign(hour_utc=hourly["hour_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")).to_csv(
        processed / "obs_hourly.csv", index=False
    )
    report = {
        "station": {"latitude": JKUAT[0], "longitude": JKUAT[1]},
        "light": {"night_counts": {"light_ir_counts": {"median": FLOOR}}},
    }
    (processed / "report.json").write_text(json.dumps(report))
    reference_path = tmp_path / "reference.json"
    reference_path.write_text(json.dumps(open_meteo_payload(reference)))
    out = tmp_path / "config" / "solar_calibration.json"

    code = main(
        [
            "calibrate-light",
            "--processed",
            str(processed),
            "--reference",
            str(reference_path),
            "--out",
            str(out),
        ]
    )

    assert code == 0
    fitted = load(out)
    assert fitted.a == pytest.approx(A, abs=0.005)
    assert fitted.reference.endswith("grid -1.0, 37.0")
    assert (processed / "ghi_hourly.csv").exists()
    assert "Fitted on 4 days" in capsys.readouterr().out


def test_command_line_reports_a_missing_reference(tmp_path, capsys):
    code = main(
        [
            "calibrate-light",
            "--processed",
            str(tmp_path),
            "--reference",
            str(tmp_path / "none.json"),
        ]
    )

    assert code == 1
    assert "error" in capsys.readouterr().err
