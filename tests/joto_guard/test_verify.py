import numpy as np
import pandas as pd
import pytest

from joto_guard import bands, verify

TIMEZONE = "Africa/Nairobi"


@pytest.fixture(scope="module")
def guidance(config_path):
    return bands.load_guidance(config_path.parent / "heat_guidance.yaml")


def test_a_perfect_forecast_agrees_everywhere(guidance):
    values = np.array([18.0, 24.0, 26.5, 28.0])

    result = verify.agreement(values, values, "heavy", guidance)

    assert result["exact_pct"] == 100.0
    assert result["under_warned_pct"] == 0.0
    assert result["worst_under_warning_levels"] == 0


def test_a_forecast_that_reads_cool_is_counted_as_under_warning(guidance):
    # Heavy work: acclimatized limit 26.0 degC. 24 is normal, 28 needs work/rest.
    station = np.array([28.0, 28.0, 24.0])
    predicted = np.array([24.0, 24.0, 24.0])

    result = verify.agreement(predicted, station, "heavy", guidance)

    assert result["under_warned_pct"] == pytest.approx(66.7, abs=0.1)
    assert result["over_warned_pct"] == 0.0
    assert result["worst_under_warning_levels"] >= 1


def test_a_forecast_that_reads_warm_over_warns_rather_than_under_warns(guidance):
    station = np.array([20.0, 20.0])
    predicted = np.array([28.0, 28.0])

    result = verify.agreement(predicted, station, "heavy", guidance)

    assert result["over_warned_pct"] == 100.0
    assert result["under_warned_pct"] == 0.0


def _pairs(days=5, hours_per_day=24, offset=1.5):
    """Station and forecast pairs where the forecast reads `offset` degC cool."""
    start = pd.Timestamp("2026-09-01T00:00Z")
    rows = []
    for day in range(days):
        for hour in range(hours_per_day):
            moment = start + pd.Timedelta(days=day, hours=hour)
            local = moment.tz_convert(TIMEZONE)
            station = 20.0 + 6.0 * np.sin((local.hour - 6) / 24 * 2 * np.pi) + 0.2 * day
            rows.append(
                {
                    "hour_utc": moment,
                    "lead_day": 0,
                    "local_day": local.date(),
                    "local_hour": local.hour,
                    "station_c": station,
                    "forecast_c": station - offset,
                }
            )
    return pd.DataFrame(rows)


def test_verification_reports_error_levels_and_what_the_band_top_would_change(guidance):
    result = verify.verify(_pairs(), guidance)

    # 5 UTC days span 6 local days: Nairobi is 3 hours ahead of the UTC midnight they start on.
    assert result["n_days"] == 6
    assert result["n_hours"] == 120
    # A constant offset is exactly what the correction removes, so little error should remain.
    assert result["error_c"]["mae"] < 0.2
    assert set(result["levels"]) == set(guidance.work_types)
    assert set(result["levels_from_band_top"]) == set(guidance.work_types)
    assert 0 <= result["hours_near_a_limit_pct"]["heavy"] <= 100


def test_the_band_top_never_under_warns_more_than_the_central_value(guidance):
    result = verify.verify(_pairs(offset=2.5), guidance)

    for work_type in guidance.work_types:
        central = result["levels"][work_type]["under_warned_pct"]
        from_top = result["levels_from_band_top"][work_type]["under_warned_pct"]
        assert from_top <= central, work_type
