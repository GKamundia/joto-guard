import json

import numpy as np
import pandas as pd
import pytest

from joto_guard import bias
from joto_guard.__main__ import main
from joto_guard.forecast import VARIABLES, forecast_wbgt, variable_name

TIMEZONE = "Africa/Nairobi"
JKUAT = (-1.099736, 37.014528)
# How much the station reads above the forecast at each local hour: more around midday.
TRUE_OFFSETS = 0.5 + 2.0 * np.exp(-(((np.arange(24) - 13) / 3.0) ** 2))


def synthetic(days=6, noise=0.0, leads=(0, 1), seed=3):
    """A station series and forecasts that miss it by TRUE_OFFSETS plus noise."""
    hours = pd.date_range("2026-08-28T00:00Z", periods=24 * days, freq="h")
    local_hour = hours.tz_convert(TIMEZONE).hour
    rng = np.random.default_rng(seed)
    daily = 16 + 8 * np.clip(np.sin((local_hour - 6) / 12 * np.pi), 0, None)
    station = pd.DataFrame({"hour_utc": hours, "wbgt_c": daily + rng.normal(0, noise, len(hours))})
    forecasts = {
        lead: pd.DataFrame(
            {
                "hour_utc": hours,
                "wbgt_c": daily - TRUE_OFFSETS[local_hour] + rng.normal(0, noise, len(hours)),
            }
        )
        for lead in leads
    }
    return station, forecasts


def correction(**changes):
    values = {
        "model": "ecmwf_ifs",
        "timezone": TIMEZONE,
        "offsets_c": tuple(float(v) for v in range(24)),
        "band_low_c": (-1.0,) * 24,
        "band_high_c": (2.0,) * 24,
        "first_day": "2026-08-28",
        "last_day": "2026-09-02",
        "n_days": 6,
        "n_pairs": 288,
        "held_out": {},
    }
    return bias.Correction(**{**values, **changes})


def test_pairs_are_labelled_with_the_local_hour_and_day():
    station, forecasts = synthetic(days=2)
    pairs = bias.pair_forecasts(station, forecasts, TIMEZONE)

    assert list(pairs.columns) == bias.PAIR_COLUMNS
    assert len(pairs) == 2 * 48
    first = pairs.iloc[0]
    # 00:00 UTC is 03:00 in Nairobi
    assert (first["local_hour"], str(first["local_day"])) == (3, "2026-08-28")


def test_hours_missing_a_value_are_not_paired():
    station, forecasts = synthetic(days=2, leads=(0,))
    station.loc[5, "wbgt_c"] = np.nan

    assert len(bias.pair_forecasts(station, forecasts, TIMEZONE)) == 47


def test_offsets_recover_a_bias_that_follows_the_clock():
    station, forecasts = synthetic(days=4)
    offsets = bias.hourly_offsets(bias.pair_forecasts(station, forecasts, TIMEZONE))

    assert offsets == pytest.approx(TRUE_OFFSETS)


def test_every_local_hour_needs_data():
    station, forecasts = synthetic(days=3)
    pairs = bias.pair_forecasts(station, forecasts, TIMEZONE)

    with pytest.raises(ValueError, match=r"local hours \[13\]"):
        bias.hourly_offsets(pairs[pairs["local_hour"] != 13])


def test_on_days_left_out_the_correction_beats_the_raw_forecast():
    station, forecasts = synthetic(days=8, noise=0.4)
    skill = bias.evaluate(bias.pair_forecasts(station, forecasts, TIMEZONE))

    overall = skill["all"]
    assert overall["corrected"]["mae_c"] < overall["raw"]["mae_c"] / 2
    assert abs(overall["corrected"]["bias_c"]) < 0.1
    assert set(skill["by_lead_day"]) == {"0", "1"}
    assert overall["n_pairs"] == 2 * 8 * 24
    assert skill["midday"]["n_pairs"] == 2 * 8 * 6


def test_the_band_holds_about_four_in_five_station_values():
    station, forecasts = synthetic(days=12, noise=0.8)
    skill = bias.evaluate(bias.pair_forecasts(station, forecasts, TIMEZONE))

    assert 70 <= skill["band_held_station_pct"] <= 90


def test_fit_stores_offsets_band_and_skill():
    station, forecasts = synthetic(days=5, noise=0.3)
    fitted = bias.fit(bias.pair_forecasts(station, forecasts, TIMEZONE), "ecmwf_ifs", TIMEZONE)

    assert len(fitted.offsets_c) == len(fitted.band_low_c) == len(fitted.band_high_c) == 24
    assert all(low < high for low, high in zip(fitted.band_low_c, fitted.band_high_c, strict=True))
    # five UTC days span six local days: the last hours fall after midnight in Nairobi
    assert (fitted.first_day, fitted.n_days) == ("2026-08-28", 6)
    assert "band_held_station_pct" in fitted.held_out


def test_fit_needs_three_days():
    station, forecasts = synthetic(days=2)
    pairs = bias.pair_forecasts(station, forecasts, TIMEZONE)
    with pytest.raises(ValueError, match="three days"):
        bias.fit(pairs[pairs["local_day"] < pairs["local_day"].max()], "ecmwf_ifs", TIMEZONE)


def test_applying_adds_the_offset_for_the_local_hour_and_the_band():
    table = pd.DataFrame(
        {"hour_utc": pd.to_datetime(["2026-09-20T09:00Z", "2026-09-20T21:00Z"]), "wbgt_c": 20.0}
    )
    corrected = bias.apply(table, correction())

    # 09:00 and 21:00 UTC are 12:00 and 00:00 in Nairobi
    assert corrected["wbgt_corrected_c"].tolist() == [32.0, 20.0]
    assert corrected["wbgt_low_c"].tolist() == [31.0, 19.0]
    assert corrected["wbgt_high_c"].tolist() == [34.0, 22.0]


def test_correction_file_round_trip(tmp_path):
    original = correction(held_out={"all": {"n_pairs": 10}})
    path = tmp_path / "forecast_correction.json"
    bias.save(original, path)

    assert json.loads(path.read_text())["method"].startswith("WBGT + offset")
    assert bias.load(path) == original


def open_meteo_past_forecasts(hours, leads=(0, 1)):
    """Past forecasts in Open-Meteo's shape: a steady sunny day, the same at every lead."""
    local_hour = hours.tz_convert(TIMEZONE).hour
    sun = np.clip(np.sin((local_hour - 6) / 12 * np.pi), 0, None)
    values = {
        "temperature_2m": 18 + 7 * sun,
        "relative_humidity_2m": 70 - 30 * sun,
        "surface_pressure": np.full(len(hours), 855.0),
        "wind_speed_10m": np.full(len(hours), 3.0),
        "shortwave_radiation": 900 * sun,
    }
    hourly = {"time": hours.strftime("%Y-%m-%dT%H:%M").tolist()}
    for lead in leads:
        for name in VARIABLES:
            hourly[variable_name(name, lead)] = np.round(values[name], 2).tolist()
    return {"timezone": "GMT", "latitude": -1.09, "longitude": 37.02, "hourly": hourly}


def test_command_line_fits_and_the_forecast_uses_it(tmp_path, fixtures_dir, config_path, capsys):
    hours = pd.date_range("2026-08-28T00:00Z", periods=24 * 5 + 1, freq="h")
    payload = open_meteo_past_forecasts(hours)
    processed = tmp_path / "processed"
    processed.mkdir()
    station = forecast_wbgt(payload, *JKUAT)[["hour_utc", "wbgt_c"]]
    station.assign(
        hour_utc=station["hour_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        wbgt_c=station["wbgt_c"] + 1.5,
    ).to_csv(processed / "wbgt_hourly.csv", index=False)
    report = {"station": {"latitude": JKUAT[0], "longitude": JKUAT[1], "elevation_m": 1523.0}}
    (processed / "report.json").write_text(json.dumps(report))
    past = tmp_path / "past.json"
    past.write_text(json.dumps(payload))
    out = tmp_path / "forecast_correction.json"

    code = main(
        [
            "fit-correction",
            "--processed",
            str(processed),
            "--past-forecasts",
            str(past),
            "--config",
            str(config_path),
            "--out",
            str(out),
        ]
    )

    assert code == 0
    fitted = bias.load(out)
    assert fitted.offsets_c == pytest.approx((1.5,) * 24)
    assert "forecasts made 0 to 1 days ahead" in capsys.readouterr().out

    code = main(
        [
            "forecast",
            "--processed",
            str(processed),
            "--payload",
            str(fixtures_dir / "open_meteo_ecmwf_ifs_forecast.json"),
            "--config",
            str(config_path),
            "--correction",
            str(out),
        ]
    )

    assert code == 0
    table = pd.read_csv(processed / "wbgt_forecast.csv")
    assert (table["wbgt_corrected_c"] - table["wbgt_c"]).round(2).eq(1.5).all()
    assert "Corrected towards the station" in capsys.readouterr().out
