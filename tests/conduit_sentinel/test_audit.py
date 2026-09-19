import numpy as np
import pandas as pd

from conduit_sentinel.audit import AUDIT_COLUMNS, is_night, run_audits
from conduit_sentinel.qc import apply_qc
from conduit_sentinel.thermo import stull_wet_bulb_c


def audits_for(obs, config):
    return run_audits(apply_qc(obs, config).obs, config)


def metric(audits, audit_id, name, variable=None):
    rows = audits[(audits["audit_id"] == audit_id) & (audits["metric"] == name)]
    if variable is not None:
        rows = rows[rows["variable"] == variable]
    assert len(rows) == 1
    return rows.iloc[0]


def test_results_follow_the_contract(make_obs, config):
    audits = audits_for(make_obs(n=10), config)

    assert list(audits.columns) == list(AUDIT_COLUMNS)
    assert set(audits["audit_id"]) == {"A01", "A02", "A03", "A04", "A05"}


def test_wet_bulb_computed_with_stull_matches(make_obs, config):
    obs = make_obs(n=10)
    obs["wet_bulb_fw_c"] = np.round(stull_wet_bulb_c(obs["t_sht_c"], obs["rh_pct"]), 1)
    row = metric(audits_for(obs, config), "A01", "mae_c")

    assert row["value"] <= 0.05
    assert row["n_rows"] == 10
    assert row["verdict"] == "matches Stull"


def test_offset_wet_bulb_does_not_match_stull(make_obs, config):
    obs = make_obs(n=10)
    obs["wet_bulb_fw_c"] = stull_wet_bulb_c(obs["t_sht_c"], obs["rh_pct"]) + 0.5
    row = metric(audits_for(obs, config), "A01", "mae_c")

    assert row["value"] == 0.5
    assert row["verdict"] == "does not match Stull"


def test_heat_index_is_reported_without_a_verdict(make_obs, config):
    row = metric(audits_for(make_obs(n=10), config), "A02", "mae_c")

    assert row["verdict"] == "report only"
    assert row["value"] >= 0


def test_wbgt_far_below_wet_bulb_is_split_by_local_night_and_day(make_obs, config):
    # 00, 06, 12, 18 UTC are 03, 09, 15, 21 EAT: night, day, day, night
    obs = make_obs(
        offsets_s=[0, 6 * 3600, 12 * 3600, 18 * 3600],
        wet_bulb_fw_c=15.0,
        wbgt_fw_c=[13.0, 14.0, 16.0, 13.0],
    )
    audits = audits_for(obs, config)

    assert metric(audits, "A03", "rows_below_wet_bulb")["value"] == 3
    assert metric(audits, "A03", "pct_below_wet_bulb")["value"] == 75.0
    assert metric(audits, "A03", "rows_far_below_wet_bulb")["value"] == 2
    assert metric(audits, "A03", "pct_far_below_wet_bulb")["value"] == 50.0
    night = metric(audits, "A03", "pct_far_below_wet_bulb_night")
    day = metric(audits, "A03", "pct_far_below_wet_bulb_day")
    assert (night["value"], night["n_rows"]) == (100.0, 2)
    assert (day["value"], day["n_rows"]) == (0.0, 2)
    assert set(audits.loc[audits["audit_id"] == "A03", "verdict"]) == {"non-standard"}
    assert "more than 1.5 °C below" in metric(audits, "A03", "pct_far_below_wet_bulb")["note"]


def test_small_dips_below_wet_bulb_are_within_tolerance(make_obs, config):
    # a standard WBGT dips this far on calm, clear nights
    audits = audits_for(make_obs(n=10, wet_bulb_fw_c=15.0, wbgt_fw_c=14.0), config)

    assert metric(audits, "A03", "pct_below_wet_bulb")["value"] == 100.0
    row = metric(audits, "A03", "pct_far_below_wet_bulb")
    assert (row["value"], row["verdict"]) == (0.0, "within tolerance")


def test_wbgt_never_below_wet_bulb_is_within_tolerance(make_obs, config):
    row = metric(audits_for(make_obs(n=10), config), "A03", "pct_below_wet_bulb")
    assert (row["value"], row["verdict"]) == (0.0, "within tolerance")


def test_standard_wbgt_audit_waits_for_light_calibration(make_obs, config):
    row = metric(audits_for(make_obs(n=3), config), "A04", "diff_by_local_hour_c")

    assert row["verdict"] == "pending"
    assert row["n_rows"] == 0
    assert pd.isna(row["value"])


def test_thermometer_pairs(make_obs, config):
    obs = make_obs(
        n=4,
        t_sht_c=[20.0, 20.5, 21.0, 21.5],
        t_mcp_c=[19.0, 20.0, 21.0, 21.5],
        t_bmx_c=[20.0, 20.5, 21.0, 21.5],
    )
    audits = audits_for(obs, config)

    assert metric(audits, "A05", "mean_abs_diff_c", "t_sht_c-t_mcp_c")["value"] == 0.375
    assert metric(audits, "A05", "max_abs_diff_c", "t_sht_c-t_mcp_c")["value"] == 1.0
    assert metric(audits, "A05", "max_abs_diff_c", "t_sht_c-t_bmx_c")["value"] == 0.0


def test_values_flagged_bad_are_left_out(make_obs, config):
    audits = audits_for(make_obs(n=4, t_sht_c=[20.4, 20.5, 60.0, 20.4]), config)
    assert metric(audits, "A05", "max_abs_diff_c", "t_sht_c-t_bmx_c")["n_rows"] == 3


def test_audit_without_usable_rows_says_so(make_obs, config):
    row = metric(audits_for(make_obs(n=3, wet_bulb_fw_c=np.nan), config), "A01", "mae_c")
    assert (row["verdict"], row["n_rows"]) == ("no usable rows", 0)


def test_is_night_wraps_past_midnight():
    hours = pd.Series(range(24))
    assert hours[is_night(hours, 19, 5)].tolist() == [0, 1, 2, 3, 4, 5, 19, 20, 21, 22, 23]
    assert hours[is_night(hours, 1, 4)].tolist() == [1, 2, 3, 4]


def test_thermometer_offset_is_reported_with_its_sign(make_obs, config):
    audits = audits_for(make_obs(n=4, t_sht_c=21.0, t_mcp_c=20.5, t_bmx_c=20.5), config)

    assert metric(audits, "A05", "mean_signed_diff_c", "t_sht_c-t_mcp_c")["value"] == 0.5
    assert metric(audits, "A05", "mean_signed_diff_c", "t_bmx_c-t_mcp_c")["value"] == 0.0


def test_audits_without_usable_rows_say_so(make_obs, config):
    audits = audits_for(make_obs(n=3, t_sht_c=np.nan), config)

    assert metric(audits, "A02", "mae_c")["verdict"] == "no usable rows"
    assert (
        metric(audits, "A05", "mean_abs_diff_c", "t_sht_c-t_mcp_c")["verdict"] == "no usable rows"
    )
    assert metric(audits, "A05", "mean_abs_diff_c", "t_bmx_c-t_mcp_c")["verdict"] == "report only"
