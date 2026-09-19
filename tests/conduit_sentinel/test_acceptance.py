"""Acceptance tests: the expected values in docs/SENTINEL_SPEC.md section 11.

They run on the two organiser CSVs in data/raw/organiser/ and are skipped when those files
are absent. Set CONDUIT_ORGANISER_DIR to read the files from somewhere else.
"""

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from conduit_sentinel.pipeline import run
from conduit_sentinel.qc import run_lengths

ORGANISER_DIR = Path(
    os.environ.get(
        "CONDUIT_ORGANISER_DIR",
        Path(__file__).resolve().parents[2] / "data" / "raw" / "organiser",
    )
)
FILE_1 = ORGANISER_DIR / "3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy1.csv"
FILE_2 = ORGANISER_DIR / "3DFEWSNET_SiteJKUAT_KenyaKiambuJKUATIOTAWS-Conduti@Empathy1(31-4).csv"

pytestmark = pytest.mark.skipif(
    not (FILE_1.exists() and FILE_2.exists()),
    reason="organiser CSVs not found; see data/raw/organiser/README.md",
)

SAMPLE_DAYS = [date(2026, 8, 28) + timedelta(days=i) for i in range(8)]


@pytest.fixture(scope="module")
def sentinel(config):
    return run([FILE_1, FILE_2], config)


def utc(text):
    return pd.Timestamp(text)


def days_fired(sentinel, rule_id, variable=None):
    hits = sentinel.qc.rule_hits
    hits = hits[hits["rule_id"] == rule_id]
    if variable is not None:
        hits = hits[hits["variable"] == variable]
    return sorted(set(hits["date_utc"]))


def audit(sentinel, audit_id):
    audits = sentinel.audits
    return audits[audits["audit_id"] == audit_id].set_index("metric")


def test_file_rows_columns_and_spans(sentinel):
    first, second = sentinel.ingest.files

    assert (first.name, first.rows, first.columns) == (FILE_1.name, 7060, 26)
    assert (first.first_utc, first.last_utc) == (
        utc("2026-08-28T00:00:25Z"),
        utc("2026-09-01T23:58:31Z"),
    )
    assert (second.name, second.rows, second.columns) == (FILE_2.name, 7067, 26)
    assert (second.first_utc, second.last_utc) == (
        utc("2026-08-31T00:00:24Z"),
        utc("2026-09-04T23:58:18Z"),
    )


def test_merge_removes_duplicate_timestamps(sentinel):
    times = sentinel.qc.obs["time_utc"]

    assert sentinel.ingest.duplicates_removed == 2825
    assert len(times) == 11302
    assert (times.min(), times.max()) == (utc("2026-08-28T00:00:25Z"), utc("2026-09-04T23:58:18Z"))


def test_measurement_counts(sentinel):
    first, second = sentinel.ingest.files

    assert (first.measurements_declared, first.measurements_counted) == (169440, 169440)
    assert (second.measurements_declared, second.measurements_counted) == (169608, 169608)


def test_station_metadata(sentinel):
    station = sentinel.ingest.station

    assert station.station_id == 61
    assert (station.latitude, station.longitude, station.elevation_m) == (
        -1.099736,
        37.014528,
        1523.0,
    )


def test_reporting_intervals(sentinel):
    intervals = sentinel.qc.intervals

    assert (intervals.median_s, intervals.min_s, intervals.max_s) == (61, 60, 755)
    # 22, not the 21 printed in spec 0.1: two intervals are exactly 120 s (decision 0004)
    assert intervals.late == 22


def test_one_gap(sentinel):
    gaps = sentinel.qc.gaps

    assert len(gaps) == 1
    gap = gaps.iloc[0]
    assert gap["interval_s"] == 755
    assert gap["gap_end_utc"] == utc("2026-08-30T03:45:32Z")
    assert gap["missing_minutes"] == 11.58


def test_hourly_rows(sentinel):
    table = sentinel.hourly
    short = table[table["n_obs"] < 54]

    assert len(table) == 192
    assert short["hour_utc"].tolist() == [utc("2026-08-30T03:00:00Z")]
    assert short["n_obs"].tolist() == [48]


def test_rain_gauges(sentinel):
    obs = sentinel.qc.obs
    tips = obs[obs["rain1_mm"] > 0]

    assert tips["rain1_mm"].tolist() == [0.2, 0.2]
    assert tips["time_utc"].tolist() == [utc("2026-08-31T00:13:44Z"), utc("2026-08-31T03:41:33Z")]
    assert obs["rain2_mm"].sum() == 0.0
    assert days_fired(sentinel, "R11") == [date(2026, 8, 31)]


def test_battery_voltage_is_empty_every_day(sentinel):
    assert sentinel.qc.obs["battery_voltage"].notna().sum() == 0
    assert days_fired(sentinel, "R12", "battery_voltage") == SAMPLE_DAYS


def test_gust_direction_copies_gust_every_day(sentinel):
    obs = sentinel.qc.obs

    assert (obs["wind_gust_dir_deg"] == obs["wind_gust_ms"]).all()
    assert days_fired(sentinel, "R13") == SAMPLE_DAYS


def test_health_codes(sentinel):
    counts = sentinel.qc.obs["health_code"].value_counts().to_dict()
    assert counts == {0: 11280, 16: 12, 33501705: 9, 32: 1}


def test_range_step_flat_line_consistency_and_gust_rules_do_not_fire(sentinel):
    quiet = {"R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R08b", "R08c", "R09", "R10"}
    assert quiet.isdisjoint(sentinel.qc.rule_hits["rule_id"])


def test_longest_identical_runs(sentinel):
    obs = sentinel.qc.obs
    wind_runs = run_lengths(obs["wind_speed_ms"])

    assert run_lengths(obs["t_sht_c"]).max() == 48
    assert run_lengths(obs["rh_pct"]).max() == 12
    assert run_lengths(obs["p_station_hpa"]).max() == 18
    assert wind_runs.max() == 317
    assert (obs.loc[wind_runs == 317, "wind_speed_ms"] == 0).all()


def test_thermometer_agreement(sentinel):
    maxima = audit(sentinel, "A05").loc["max_abs_diff_c"].set_index("variable")["value"]
    assert maxima.to_dict() == {
        "t_sht_c-t_mcp_c": 1.6,
        "t_sht_c-t_bmx_c": 1.3,
        "t_bmx_c-t_mcp_c": 1.1,
    }


def test_wet_bulb_audit(sentinel):
    a01 = audit(sentinel, "A01")

    assert a01.loc["mae_c", "value"] == 0.032
    assert a01.loc["max_abs_diff_c", "value"] == 0.103
    assert set(a01["verdict"]) == {"matches Stull"}


def test_wbgt_below_wet_bulb_audit(sentinel):
    a03 = audit(sentinel, "A03")

    assert a03.loc["rows_below_wet_bulb", "value"] == 5833
    assert a03.loc["rows_below_wet_bulb", "n_rows"] == 11302
    assert a03.loc["pct_below_wet_bulb", "value"] == 51.6
    assert a03.loc["rows_far_below_wet_bulb", "value"] == 3850
    assert a03.loc["pct_far_below_wet_bulb", "value"] == 34.1
    assert a03.loc["pct_far_below_wet_bulb_night", "value"] == 51.3
    assert a03.loc["pct_far_below_wet_bulb_day", "value"] == 19.5
    assert set(a03["verdict"]) == {"non-standard"}


def test_daily_health_scores(sentinel):
    health = sentinel.health
    suspect = dict(zip(health["date_utc"], health["suspect_groups"], strict=True))

    assert health["date_utc"].tolist() == SAMPLE_DAYS
    assert health["score"].tolist() == [80.0, 80.0, 79.2, 78.0, 80.0, 80.0, 80.0, 80.0]
    assert all(sorted(groups) == ["battery", "wind_gust_dir"] for groups in health["bad_groups"])
    assert suspect.pop(date(2026, 8, 31)) == ["rain_gauge_2"]
    assert all(groups == [] for groups in suspect.values())


@pytest.mark.parametrize(
    ("variable", "low", "high"),
    [
        ("t_sht_c", 11.8, 29.5),
        ("t_bmx_c", 11.4, 28.8),
        ("t_mcp_c", 11.6, 29.0),
        ("rh_pct", 30.2, 95.0),
        ("p_station_hpa", 848.4, 856.1),
        ("wind_speed_ms", 0.0, 3.0),
        ("wind_gust_ms", 0.0, 15.7),
        ("light_vis_counts", 257, 1200),
        ("light_ir_counts", 251, 10965),
        ("uv_index", 0.0, 5.1),
    ],
)
def test_observed_ranges(sentinel, variable, low, high):
    values = sentinel.qc.obs[variable]
    assert (values.min(), values.max()) == (low, high)
