import numpy as np
import pandas as pd
import pytest

from conduit_sentinel.aggregate import HOURLY_COLUMNS, hourly
from conduit_sentinel.qc import apply_qc
from conduit_sentinel.schema import Flag


def hourly_from(obs, config):
    return hourly(apply_qc(obs, config).obs, config)


def test_one_row_per_hour_including_hours_without_data(make_obs, config):
    table = hourly_from(make_obs(offsets_s=[0, 60, 3 * 3600]), config)

    assert list(table.columns) == list(HOURLY_COLUMNS)
    start = pd.Timestamp("2026-08-28T00:00:00Z")
    assert table["hour_utc"].tolist() == [start + pd.Timedelta(hours=h) for h in range(4)]
    assert table["n_obs"].tolist() == [2, 0, 0, 1]
    assert table["coverage_pct"].tolist() == [3.3, 0.0, 0.0, 1.7]
    assert (table["station_id"] == 61).all()


def test_mean_leaves_out_bad_values_and_keeps_suspect_ones(make_obs, config):
    obs = make_obs(n=60, t_sht_c=[20.0] * 59 + [46.0])
    qc = apply_qc(obs, config)
    row = hourly(qc.obs, config).iloc[0]

    assert qc.obs.loc[59, "qc_t_sht_c"] == Flag.BAD
    assert qc.obs.loc[59, "qc_t_bmx_c"] == Flag.SUSPECT
    assert row["t_sht_c"] == 20.0
    assert row["t_bmx_c"] == round(obs["t_bmx_c"].mean(), 2)


def test_hour_below_half_coverage_has_no_values(make_obs, config):
    offsets = np.concatenate([np.arange(29) * 60, 3600 + np.arange(30) * 60])
    table = hourly_from(make_obs(offsets_s=offsets), config)

    assert table["n_obs"].tolist() == [29, 30]
    assert table["coverage_pct"].tolist() == [48.3, 50.0]
    assert np.isnan(table.loc[0, "t_sht_c"])
    assert not np.isnan(table.loc[1, "t_sht_c"])


def test_variable_with_too_few_usable_values_is_null(make_obs, config):
    humidity = [0.0] * 31 + [60.0 + 0.1 * (i % 5) for i in range(29)]
    row = hourly_from(make_obs(n=60, rh_pct=humidity), config).iloc[0]

    assert row["coverage_pct"] == 100.0
    assert np.isnan(row["rh_pct"])
    assert not np.isnan(row["t_sht_c"])


def test_rain_is_summed_and_gust_takes_the_maximum(make_obs, config):
    obs = make_obs(n=60, rain1_mm=[0.2] + [0.0] * 58 + [0.2], wind_gust_ms=[2.0] * 59 + [7.5])
    row = hourly_from(obs, config).iloc[0]

    assert row["rain1_mm"] == 0.4
    assert row["rain2_mm"] == 0.0
    assert row["wind_gust_ms"] == 7.5


def test_wind_direction_is_averaged_around_the_circle(make_obs, config):
    row = hourly_from(make_obs(n=60, wind_dir_deg=[350.0, 10.0] * 30), config).iloc[0]
    assert row["wind_dir_deg"] == pytest.approx(0.0, abs=0.01)


def test_codes_running_totals_and_gust_direction_are_not_aggregated(make_obs, config):
    table = hourly_from(make_obs(n=5), config)
    for column in ("health_code", "battery_status", "rain1_today_mm", "wind_gust_dir_deg"):
        assert column not in table


def test_no_observations_gives_an_empty_table(make_obs, config):
    obs_qc = apply_qc(make_obs(n=3), config).obs
    table = hourly(obs_qc.iloc[0:0], config)

    assert table.empty
    assert list(table.columns) == list(HOURLY_COLUMNS)
