from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from joto_guard import bands, hot_season


@pytest.fixture(scope="module")
def guidance(config_path):
    return bands.load_guidance(config_path.parent / "heat_guidance.yaml")


def reanalysis(wbgt_by_month, hours_per_day=24):
    """One day in each month given, every hour at that month's WBGT."""
    rows = []
    for month, wbgt in wbgt_by_month.items():
        for hour in range(hours_per_day):
            rows.append(
                {
                    "hour_utc": pd.Timestamp(f"2025-{month:02d}-15T{hour:02d}:00Z"),
                    "local_hour": (hour + 3) % 24,
                    "month": month,
                    "year": 2025,
                    "wbgt_c": wbgt,
                }
            )
    return pd.DataFrame(rows)


def test_only_working_hours_count():
    table = reanalysis({2: 20.0})

    kept = hot_season.working(table)

    assert kept["local_hour"].min() == hot_season.WORK_START_H
    assert kept["local_hour"].max() == hot_season.WORK_END_H - 1
    assert len(kept) == hot_season.WORK_END_H - hot_season.WORK_START_H


def test_the_offsets_recover_how_far_the_reanalysis_reads_cool():
    era5 = reanalysis({8: 20.0})
    station = era5[["hour_utc"]].assign(wbgt_c=22.0)

    offsets = hot_season.station_offsets(era5, station)

    assert np.allclose(offsets, 2.0)


def test_offsets_need_some_hours_in_common():
    era5 = reanalysis({8: 20.0})
    station = pd.DataFrame({"hour_utc": [pd.Timestamp("2019-01-01T00:00Z")], "wbgt_c": [22.0]})

    with pytest.raises(ValueError, match="share no hours"):
        hot_season.station_offsets(era5, station)


def test_shares_count_hours_over_each_limit(guidance):
    # Heavy work: new workers 22.3 degC, workers used to the heat 26.0 degC.
    table = reanalysis({2: 24.0})

    result = hot_season.shares(table, guidance, "wbgt_c")

    assert result["heavy"]["over_new_workers_pct"] == 100.0
    assert result["heavy"]["over_acclimatized_pct"] == 0.0
    assert result["light"]["over_new_workers_pct"] == 0.0


def test_a_value_exactly_at_the_limit_is_within_it(guidance):
    limit = guidance.new_workers.at(guidance.work_types["heavy"])
    table = reanalysis({2: float(limit)})

    assert hot_season.shares(table, guidance, "wbgt_c")["heavy"]["over_new_workers_pct"] == 0.0


def test_the_summary_sets_the_hot_season_against_the_months_on_record(guidance):
    table = reanalysis({1: 27.0, 2: 27.0, 3: 27.0, 8: 18.0, 9: 18.0})
    offsets = np.zeros(24)

    summary = hot_season.summarise(table, offsets, guidance, datetime(2026, 9, 21, tzinfo=UTC))

    assert summary["hot_months"] == ["Jan", "Feb", "Mar"]
    assert summary["record_months"] == ["Aug", "Sep"]
    hot = summary["hot_season"]["likely"]["heavy"]
    record = summary["record_season"]["likely"]["heavy"]
    assert hot["over_acclimatized_pct"] == 100.0
    assert record["over_acclimatized_pct"] == 0.0
    assert len(summary["by_month"]) == 12


def test_the_likely_figure_is_the_floor_moved_by_the_station_correction(guidance):
    # 21 degC is under the heavy new-worker limit (22.3); 2 degC more is over it.
    table = reanalysis({2: 21.0})
    offsets = np.full(24, 2.0)

    summary = hot_season.summarise(table, offsets, guidance, datetime(2026, 9, 21, tzinfo=UTC))

    february = summary["hot_season"]
    assert february["at_least"]["heavy"]["over_new_workers_pct"] == 0.0
    assert february["likely"]["heavy"]["over_new_workers_pct"] == 100.0
    assert summary["reanalysis_minus_station_c"] == -2.0


def test_a_month_with_no_hours_is_reported_empty_not_as_an_error(guidance):
    table = reanalysis({2: 25.0})

    summary = hot_season.summarise(table, np.zeros(24), guidance, datetime(2026, 9, 21, tzinfo=UTC))
    june = next(m for m in summary["by_month"] if m["name"] == "Jun")

    assert june["peak_wbgt_c"] is None
    assert june["likely"]["heavy"]["over_new_workers_pct"] == 0.0


def test_the_request_asks_for_the_forecasts_own_inputs_from_era5():
    params = hot_season.request_params(-1.1, 37.0, 1523.0, "2016-01-01", "2026-09-15")

    assert params["models"] == "era5"
    assert params["timezone"] == "GMT"
    assert "shortwave_radiation" in params["hourly"]
    assert "wind_speed_10m" in params["hourly"]
