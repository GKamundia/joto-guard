from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from conduit_sentinel.health import (
    STATUS_COLUMNS,
    group_status,
    health_daily,
    missing_minutes_by_day,
)
from conduit_sentinel.qc import apply_qc
from conduit_sentinel.schema import SCORED_GROUPS


def score(obs, config):
    qc = apply_qc(obs, config)
    status = group_status(qc, config)
    return status, health_daily(qc, status, config)


def test_clean_day_scores_100(make_obs, config):
    status, health = score(make_obs(n=100), config)

    assert health["score"].tolist() == [100.0]
    assert health.loc[0, "bad_groups"] == []
    assert health.loc[0, "n_obs"] == 100
    assert status["group"].tolist() == list(SCORED_GROUPS)
    assert set(status["status"]) == {"good"}


def test_empty_channel_makes_its_group_bad(make_obs, config):
    status, health = score(make_obs(n=100, battery_voltage=np.nan), config)

    assert health.loc[0, "score"] == 90.0
    assert health.loc[0, "bad_groups"] == ["battery"]
    battery = status.set_index("group").loc["battery"]
    assert (battery["status"], battery["rules"]) == ("bad", ["R12"])


@pytest.mark.parametrize(("bad_rows", "expected"), [(5, 100.0), (6, 90.0)])
def test_group_is_bad_only_above_five_percent_bad_rows(make_obs, config, bad_rows, expected):
    pressure = [852.0 + 0.1 * (i % 3) for i in range(100)]
    for i in range(bad_rows):
        pressure[i * 10] = 950.0
    _, health = score(make_obs(n=100, p_station_hpa=pressure), config)

    assert health.loc[0, "score"] == expected


def test_suspect_rows_and_rain_disagreement_make_groups_suspect(make_obs, config):
    obs = make_obs(
        n=100,
        rain1_mm=[0.4] + [0.0] * 99,
        light_vis_counts=[200.0] * 6 + [300.0] * 94,
    )
    status, health = score(obs, config)

    assert health.loc[0, "suspect_groups"] == ["rain_gauge_2", "light"]
    assert health.loc[0, "score"] == 96.0
    rules = status.set_index("group")["rules"]
    assert rules["rain_gauge_2"] == ["R11"]
    assert rules["light"] == ["R06"]


def test_duplicated_gust_direction_makes_its_group_bad(make_obs, config):
    gust = [2.0 + 0.1 * (i % 4) for i in range(100)]
    status, health = score(make_obs(n=100, wind_gust_ms=gust, wind_gust_dir_deg=gust), config)

    assert health.loc[0, "bad_groups"] == ["wind_gust_dir"]
    assert status.set_index("group").loc["wind_gust_dir", "rules"] == ["R13"]


def test_firmware_derived_values_do_not_change_the_score(make_obs, config):
    status, health = score(make_obs(n=100, wbgt_fw_c=5.0), config)

    assert health.loc[0, "score"] == 100.0
    assert "derived_fw" not in set(status["group"])


def test_gap_minutes_are_charged_to_the_days_they_fall_in(make_obs, config):
    # last report 23:50, next 00:20: missing from 23:51, so 9 minutes then 20 minutes
    obs = make_obs(offsets_s=[0, 60, 1860, 1920], start="2026-08-28T23:49:00Z")
    _, health = score(obs, config)

    assert health["missing_minutes"].tolist() == [9.0, 20.0]
    assert health["score"].tolist() == [99.4, 98.6]


def test_day_without_observations_scores_zero(make_obs, config):
    obs = make_obs(offsets_s=[0, 60, 2 * 86400, 2 * 86400 + 60])
    status, health = score(obs, config)

    assert health["date_utc"].tolist() == [date(2026, 8, 28), date(2026, 8, 29), date(2026, 8, 30)]
    empty_day = health.iloc[1]
    assert empty_day["n_obs"] == 0
    assert empty_day["missing_minutes"] == 1440.0
    assert empty_day["score"] == 0.0
    assert empty_day["bad_groups"] == list(SCORED_GROUPS)
    rules = status.loc[status["date_utc"] == date(2026, 8, 29), "rules"]
    assert all(r == ["R12"] for r in rules)


def test_missing_minutes_split_a_multi_day_gap():
    gaps = pd.DataFrame(
        {
            "gap_start_utc": [pd.Timestamp("2026-08-28T12:00:00Z")],
            "gap_end_utc": [pd.Timestamp("2026-08-30T06:00:00Z")],
        }
    )
    days = pd.date_range("2026-08-28", "2026-08-30", freq="D", tz="UTC")

    minutes = missing_minutes_by_day(gaps, days, expected_interval_s=60)

    assert minutes.round(2).tolist() == [719.0, 1440.0, 360.0]


def test_days_no_export_covers_are_not_scored(make_obs, config):
    obs = make_obs(offsets_s=[0, 60, 6 * 86400, 6 * 86400 + 60])
    times = obs["time_utc"]
    coverage = ((times.iloc[0], times.iloc[1]), (times.iloc[2], times.iloc[3]))
    qc = apply_qc(obs, config, coverage)
    status = group_status(qc, config)
    health = health_daily(qc, status, config)

    assert health["date_utc"].tolist() == [date(2026, 8, 28), date(2026, 9, 3)]
    assert health["missing_minutes"].tolist() == [0.0, 0.0]
    assert health["score"].tolist() == [100.0, 100.0]
    assert set(status["date_utc"]) == {date(2026, 8, 28), date(2026, 9, 3)}


def test_missing_minutes_are_clipped_to_the_covered_periods():
    gaps = pd.DataFrame(
        {
            "gap_start_utc": [pd.Timestamp("2026-08-28T23:50:00Z")],
            "gap_end_utc": [pd.Timestamp("2026-09-03T00:10:00Z")],
        }
    )
    days = pd.DatetimeIndex(["2026-08-28", "2026-09-03"], tz="UTC")
    coverage = (
        (pd.Timestamp("2026-08-28T00:00:00Z"), pd.Timestamp("2026-08-28T23:50:00Z")),
        (pd.Timestamp("2026-09-03T00:10:00Z"), pd.Timestamp("2026-09-03T23:50:00Z")),
    )

    minutes = missing_minutes_by_day(gaps, days, expected_interval_s=60, coverage=coverage)

    assert minutes.tolist() == [0.0, 0.0]


def test_without_covered_days_the_tables_are_empty(make_obs, config):
    qc = replace(apply_qc(make_obs(n=3), config), coverage=())
    status = group_status(qc, config)

    assert status.empty
    assert list(status.columns) == list(STATUS_COLUMNS)
    assert health_daily(qc, status, config).empty
