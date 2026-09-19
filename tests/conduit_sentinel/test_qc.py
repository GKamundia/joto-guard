from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from conduit_sentinel.qc import RULES, apply_qc, run_lengths, usable
from conduit_sentinel.schema import VARIABLES, Flag, qc_column

GOOD, SUSPECT, BAD, MISSING = Flag.GOOD, Flag.SUSPECT, Flag.BAD, Flag.MISSING


def flags(result, variable):
    return result.obs[qc_column(variable)].tolist()


def notes(result):
    return result.obs["qc_notes"].tolist()


def hits(result, rule_id):
    table = result.rule_hits
    return table.loc[
        table["rule_id"] == rule_id, ["variable", "date_utc", "n_rows"]
    ].values.tolist()


def test_rule_catalogue_matches_spec():
    expected = {f"R{i:02d}" for i in range(1, 17)} | {"R08b", "R08c"}
    assert set(RULES) == expected


def test_clean_observations_pass_every_rule(make_obs, config):
    result = apply_qc(make_obs(n=200), config)

    for variable in VARIABLES:
        assert set(flags(result, variable)) == {GOOD}, variable
    assert set(notes(result)) == {""}
    assert result.gaps.empty
    assert result.rule_hits.empty


def test_every_row_is_kept_and_flag_columns_are_added(make_obs, config):
    obs = make_obs(n=5)
    result = apply_qc(obs, config)

    assert len(result.obs) == 5
    assert list(result.obs.columns[: obs.shape[1]]) == list(obs.columns)
    assert list(result.obs.columns[obs.shape[1] :]) == [
        *(qc_column(v) for v in VARIABLES),
        "qc_notes",
    ]


def test_missing_values_are_flagged_missing(make_obs, config):
    result = apply_qc(make_obs(n=3, t_sht_c=[20.4, np.nan, 20.5]), config)

    assert flags(result, "t_sht_c") == [GOOD, MISSING, GOOD]
    assert hits(result, "R12") == []


@pytest.mark.parametrize(
    ("variable", "value", "rule_id"),
    [
        ("t_sht_c", 45.1, "R01"),
        ("t_bmx_c", -5.1, "R01"),
        ("rh_pct", 0.0, "R02"),
        ("rh_pct", 100.1, "R02"),
        ("p_station_hpa", 799.9, "R03"),
        ("p_station_hpa", 900.1, "R03"),
        ("wind_speed_ms", 60.1, "R04"),
        ("wind_gust_ms", 75.1, "R04"),
        ("rain1_mm", 10.1, "R05"),
        ("rain2_mm", -0.1, "R05"),
    ],
)
def test_values_outside_range_are_bad(make_obs, config, variable, value, rule_id):
    obs = make_obs(n=3)
    obs.loc[1, variable] = value
    result = apply_qc(obs, config)

    assert flags(result, variable)[:2] == [GOOD, BAD]
    assert rule_id in notes(result)[1].split(";")


@pytest.mark.parametrize(
    "limits",
    [
        {"t_sht_c": 45.0, "t_bmx_c": 45.0, "t_mcp_c": 45.0},
        {"t_sht_c": -5.0, "t_bmx_c": -5.0, "t_mcp_c": -5.0},
        {"rh_pct": 100.0},
        {"p_station_hpa": 800.0},
        {"p_station_hpa": 900.0},
        {"wind_speed_ms": 0.0},
        {"rain1_mm": 10.0},
    ],
)
def test_range_limits_themselves_are_good(make_obs, config, limits):
    result = apply_qc(make_obs(n=3, **limits), config)
    for variable in limits:
        assert set(flags(result, variable)) == {GOOD}, variable


def test_light_below_dark_floor_is_suspect(make_obs, config):
    result = apply_qc(make_obs(n=2, light_vis_counts=[239.0, 240.0]), config)

    assert flags(result, "light_vis_counts") == [SUSPECT, GOOD]
    assert notes(result) == ["R06", ""]


def test_fast_temperature_step_flags_the_later_row(make_obs, config):
    obs = make_obs(
        n=3,
        t_sht_c=[20.0, 20.0, 26.0],
        t_bmx_c=[20.0, 20.0, 25.0],
        t_mcp_c=[20.0, 20.0, 25.0],
    )
    result = apply_qc(obs, config)

    assert flags(result, "t_sht_c") == [GOOD, GOOD, SUSPECT]
    assert flags(result, "t_bmx_c") == [GOOD, GOOD, GOOD]  # exactly 5 °C per minute
    assert notes(result)[2] == "R07"


def test_step_rate_is_per_minute_and_skips_rows_far_apart(make_obs, config):
    same = [20.0, 28.0, 44.0]  # +8 °C over 120 s, then +16 °C over 180 s
    obs = make_obs(offsets_s=[0, 120, 300], t_sht_c=same, t_bmx_c=same, t_mcp_c=same)
    result = apply_qc(obs, config)

    assert set(flags(result, "t_sht_c")) == {GOOD}


def test_flat_line_reaching_the_threshold_is_suspect(make_obs, config):
    result = apply_qc(make_obs(n=121, t_sht_c=[21.0] * 120 + [21.1]), config)

    assert set(flags(result, "t_sht_c")[:120]) == {SUSPECT}
    assert flags(result, "t_sht_c")[120] == GOOD
    assert notes(result)[0] == "R08"


def test_flat_line_below_the_threshold_is_good(make_obs, config):
    result = apply_qc(make_obs(n=120, rh_pct=[70.0] * 119 + [70.1]), config)
    assert set(flags(result, "rh_pct")) == {GOOD}


def test_pressure_flat_line_uses_its_own_threshold(make_obs, config):
    assert set(flags(apply_qc(make_obs(n=179, p_station_hpa=852.0), config), "p_station_hpa")) == {
        GOOD
    }
    result = apply_qc(make_obs(n=180, p_station_hpa=852.0), config)
    assert set(flags(result, "p_station_hpa")) == {SUSPECT}
    assert notes(result)[0] == "R08b"


def test_calm_wind_is_not_a_flat_line(make_obs, config):
    result = apply_qc(make_obs(n=400, wind_speed_ms=0.0), config)
    assert set(flags(result, "wind_speed_ms")) == {GOOD}


def test_stuck_non_zero_wind_speed_is_suspect(make_obs, config):
    result = apply_qc(make_obs(n=180, wind_speed_ms=1.5), config)

    assert set(flags(result, "wind_speed_ms")) == {SUSPECT}
    assert notes(result)[0] == "R08c"


def test_thermometer_disagreement_flags_all_three(make_obs, config):
    # 16.1 - 14.1 is 2.0000000000000018 in floating point, which must not count as above 2.0
    obs = make_obs(n=2, t_sht_c=[16.2, 16.1], t_bmx_c=[14.1, 14.1], t_mcp_c=[15.0, 15.0])
    result = apply_qc(obs, config)

    for variable in ("t_sht_c", "t_bmx_c", "t_mcp_c"):
        assert flags(result, variable) == [SUSPECT, GOOD]
    assert notes(result) == ["R09", ""]


def test_gust_below_speed_is_suspect(make_obs, config):
    result = apply_qc(make_obs(n=2, wind_speed_ms=2.0, wind_gust_ms=[1.9, 2.0]), config)

    assert flags(result, "wind_gust_ms") == [SUSPECT, GOOD]
    assert flags(result, "wind_speed_ms") == [GOOD, GOOD]


def test_zero_gauge_is_suspect_on_the_day_the_other_recorded_rain(make_obs, config):
    obs = make_obs(offsets_s=[0, 60, 86400, 86460], rain1_mm=[0.2, 0.2, 0.0, 0.0])
    result = apply_qc(obs, config)

    for variable in ("rain2_mm", "rain2_today_mm", "rain2_prior_mm"):
        assert flags(result, variable) == [SUSPECT, SUSPECT, GOOD, GOOD]
    assert set(flags(result, "rain1_mm")) == {GOOD}
    assert {day for _, day, _ in hits(result, "R11")} == {date(2026, 8, 28)}


def test_rain_below_the_disagreement_threshold_is_ignored(make_obs, config):
    result = apply_qc(make_obs(n=2, rain1_mm=[0.2, 0.0]), config)
    assert hits(result, "R11") == []


def test_rain_flagged_bad_does_not_count_towards_disagreement(make_obs, config):
    result = apply_qc(make_obs(n=2, rain1_mm=[12.0, 0.0]), config)

    assert flags(result, "rain1_mm") == [BAD, GOOD]
    assert hits(result, "R11") == []


def test_channel_empty_for_a_whole_day(make_obs, config):
    obs = make_obs(offsets_s=[0, 60, 86400], battery_voltage=[np.nan, np.nan, 95.0])
    result = apply_qc(obs, config)

    assert flags(result, "battery_voltage") == [MISSING, MISSING, GOOD]
    assert hits(result, "R12") == [["battery_voltage", date(2026, 8, 28), 2]]
    assert "R12" in notes(result)[0].split(";")


def test_gust_direction_copying_gust_speed_is_bad(make_obs, config):
    gust = [2.0, 2.5, 3.0]
    result = apply_qc(make_obs(n=3, wind_gust_ms=gust, wind_gust_dir_deg=gust), config)

    assert flags(result, "wind_gust_dir_deg") == [BAD, BAD, BAD]
    assert notes(result) == ["R13"] * 3


@pytest.mark.parametrize(("differing_rows", "fires"), [(1, True), (2, False)])
def test_gust_direction_rule_needs_99_percent_identical(make_obs, config, differing_rows, fires):
    gust = [2.0 + 0.1 * (i % 4) for i in range(100)]
    direction = [180.0] * differing_rows + gust[differing_rows:]
    result = apply_qc(make_obs(n=100, wind_gust_ms=gust, wind_gust_dir_deg=direction), config)

    assert bool(hits(result, "R13")) is fires


def test_intervals_are_split_into_late_reports_and_gaps(make_obs, config):
    intervals = [60, 119, 120, 300, 301, 60]
    result = apply_qc(make_obs(offsets_s=np.cumsum([0, *intervals])), config)

    assert (result.intervals.late, result.intervals.gaps) == (2, 1)
    assert (result.intervals.min_s, result.intervals.max_s) == (60, 301)
    assert notes(result) == ["", "", "", "R14", "R14", "R14", ""]

    gap = result.gaps.iloc[0]
    assert gap["interval_s"] == 301
    assert gap["missing_minutes"] == 4.02
    assert gap["gap_end_utc"] - gap["gap_start_utc"] == pd.Timedelta(seconds=301)
    assert gap["station_id"] == 61


def test_non_zero_health_code_is_noted_but_not_flagged(make_obs, config):
    result = apply_qc(make_obs(n=3, health_code=[0, 16, None]), config)

    assert flags(result, "health_code") == [GOOD, GOOD, MISSING]
    assert notes(result) == ["", "R15", ""]


def test_wbgt_far_below_wet_bulb_is_suspect(make_obs, config):
    # a standard WBGT itself dips a little below the wet bulb on calm, clear nights
    result = apply_qc(make_obs(n=3, wet_bulb_fw_c=15.0, wbgt_fw_c=[13.4, 13.5, 14.9]), config)

    assert flags(result, "wbgt_fw_c") == [SUSPECT, GOOD, GOOD]
    assert notes(result) == ["R16", "", ""]


def test_wbgt_margin_comes_from_the_config(make_obs, config):
    strict = replace(config, qc=replace(config.qc, wbgt_below_wet_bulb_margin_c=0.0))
    result = apply_qc(make_obs(n=2, wet_bulb_fw_c=15.0, wbgt_fw_c=[14.9, 15.0]), strict)

    assert flags(result, "wbgt_fw_c") == [SUSPECT, GOOD]


def test_bad_outranks_suspect_and_notes_list_each_rule_once(make_obs, config):
    result = apply_qc(make_obs(n=1, t_sht_c=[46.0], health_code=[16]), config)

    assert flags(result, "t_sht_c") == [BAD]
    assert flags(result, "t_bmx_c") == [SUSPECT]
    assert notes(result) == ["R01;R09;R15"]


def test_rule_hits_count_rows_per_variable_and_day(make_obs, config):
    result = apply_qc(make_obs(offsets_s=[0, 60, 86400], wbgt_fw_c=10.0), config)

    assert hits(result, "R16") == [
        ["wbgt_fw_c", date(2026, 8, 28), 2],
        ["wbgt_fw_c", date(2026, 8, 29), 1],
    ]


@pytest.mark.parametrize("offsets", [[60, 0], [0, 0]])
def test_unsorted_or_repeated_times_are_refused(make_obs, config, offsets):
    with pytest.raises(ValueError, match="sorted"):
        apply_qc(make_obs(offsets_s=offsets), config)


def test_run_lengths():
    values = pd.Series([1.0, 1.0, 2.0, np.nan, 2.0, 2.0, 2.0])
    assert run_lengths(values).tolist() == [2, 2, 1, 0, 3, 3, 3]


def test_usable_hides_bad_and_missing_values(make_obs, config):
    result = apply_qc(make_obs(n=3, t_sht_c=[46.0, np.nan, 20.4]), config)
    assert usable(result.obs, "t_sht_c").isna().tolist() == [True, True, False]


def test_gap_inside_one_export_is_a_reporting_gap(make_obs, config):
    result = apply_qc(make_obs(offsets_s=[0, 60, 660]), config)

    assert result.gaps["kind"].tolist() == ["reporting"]
    assert (result.intervals.gaps, result.intervals.between_exports) == (1, 0)
    assert result.intervals.max_s == 600


def test_gap_between_two_exports_is_labelled_and_left_out_of_the_cadence(make_obs, config):
    obs = make_obs(offsets_s=[0, 60, 6 * 86400, 6 * 86400 + 60])
    times = obs["time_utc"]
    coverage = ((times.iloc[0], times.iloc[1]), (times.iloc[2], times.iloc[3]))

    result = apply_qc(obs, config, coverage)

    assert result.gaps["kind"].tolist() == ["between_exports"]
    assert (result.intervals.gaps, result.intervals.between_exports) == (0, 1)
    assert result.intervals.max_s == 60  # the six days between exports are not a cadence
    assert result.coverage == coverage


def test_observations_missing_a_column_are_refused(make_obs, config):
    with pytest.raises(ValueError, match="missing columns"):
        apply_qc(make_obs(n=3).drop(columns=["rh_pct"]), config)


def test_two_stations_at_once_are_refused(make_obs, config):
    obs = make_obs(n=4)
    obs.loc[2:, "station_id"] = 10

    with pytest.raises(ValueError, match="one station at a time"):
        apply_qc(obs, config)
