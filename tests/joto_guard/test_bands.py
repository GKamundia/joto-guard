import math
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from joto_guard import bands
from joto_guard.guidance import forecast_guidance

TIMEZONE = "Africa/Nairobi"


@pytest.fixture(scope="module")
def guidance(config_path):
    return bands.load_guidance(config_path.parent / "heat_guidance.yaml")


def test_limits_follow_the_niosh_equations(guidance):
    # NIOSH section 8.1: REL = 56.7 - 11.5 log10 M, RAL = 59.9 - 14.1 log10 M, M in W
    assert guidance.acclimatized.at(349) == pytest.approx(56.7 - 11.5 * math.log10(349))
    assert guidance.new_workers.at(349) == pytest.approx(59.9 - 14.1 * math.log10(349))


def test_limits_at_the_top_of_each_category_match_niosh_table_5_1(guidance):
    # Table 5-1 gives the acclimatized limit by category, rounded: 30, 28, 26 and 25 degC
    table = {"light": 30, "moderate": 28, "heavy": 26, "very_heavy": 25}
    for work_type, rounded in table.items():
        limit = guidance.acclimatized.at(guidance.work_types[work_type])
        assert abs(limit - rounded) < 0.6, work_type


def test_new_workers_always_get_the_lower_limit(guidance):
    for rate in guidance.work_types.values():
        assert guidance.new_workers.at(rate) < guidance.acclimatized.at(rate)


def test_rest_lowers_the_hours_average_metabolic_rate():
    assert bands.hourly_rate_w(465, 60, 117) == 465
    assert bands.hourly_rate_w(465, 30, 117) == pytest.approx(291)


def test_allowed_minutes_shrink_as_the_heat_rises(guidance):
    wbgt = np.arange(18.0, 36.0, 0.25)
    minutes = bands.allowed_minutes(wbgt, 465, guidance.acclimatized, guidance)

    assert minutes[0] == 60
    assert minutes[-1] == 0
    assert (np.diff(minutes) <= 0).all()
    assert set(minutes) <= {0, 15, 30, 45, 60}


def test_the_boundary_itself_is_within_the_limit(guidance):
    limit = guidance.acclimatized.at(465)
    minutes = bands.allowed_minutes([limit, limit + 0.01], 465, guidance.acclimatized, guidance)
    assert minutes[0] == 60
    assert minutes[1] < 60


def test_levels_step_up_with_the_heat(guidance):
    heavy = guidance.work_types["heavy"]
    rel, ral = guidance.acclimatized.at(heavy), guidance.new_workers.at(heavy)
    wbgt = [ral - 1, (ral + rel) / 2, rel + 0.5, 40.0, np.nan]

    assert bands.levels(wbgt, "heavy", guidance).tolist() == [
        "normal",
        "acclimatized_only",
        "work_rest",
        "reschedule",
        None,
    ]


def test_lighter_work_tolerates_more_heat(guidance):
    # 26.8 degC is above the new-worker limit for light work (26.5) and below its REL
    at_26_8 = {work: bands.levels([26.8], work, guidance)[0] for work in guidance.work_types}

    assert at_26_8 == {
        "light": "acclimatized_only",
        "moderate": "acclimatized_only",
        "heavy": "work_rest",
        "very_heavy": "work_rest",
    }


def forecast_table():
    hours = pd.date_range("2026-09-20T03:00Z", periods=6, freq="h")  # 06:00 to 11:00 in Nairobi
    wbgt = np.array([18.0, 20.0, 23.0, 26.5, 27.5, np.nan])
    return pd.DataFrame(
        {
            "hour_utc": hours,
            "wbgt_c": wbgt - 2,
            "wbgt_corrected_c": wbgt,
            "wbgt_low_c": wbgt - 3,
            "wbgt_high_c": wbgt + 3,
        }
    )


def test_guidance_by_hour_covers_every_hour_and_work_type(guidance):
    by_hour = bands.guidance_by_hour(forecast_table(), guidance)

    assert list(by_hour.columns) == bands.BY_HOUR_COLUMNS
    assert len(by_hour) == 6 * len(guidance.work_types)
    heavy = by_hour[by_hour["work_type"] == "heavy"]
    assert heavy["level"].tolist()[:5] == [
        "normal",
        "normal",
        "acclimatized_only",
        "work_rest",
        "work_rest",
    ]
    assert pd.isna(heavy["level"].iloc[5])  # no WBGT, no level
    # at the top of its band (23 degC), 20 degC could be too warm for new workers
    assert heavy["level_if_high"].tolist()[:2] == ["normal", "acclimatized_only"]


def test_day_summary_gives_the_window_when_breaks_are_needed(guidance):
    by_hour = bands.guidance_by_hour(forecast_table(), guidance)
    summary = bands.day_summaries(by_hour, TIMEZONE).set_index("work_type")

    heavy = summary.loc["heavy"]
    assert (heavy["hours"], heavy["peak_wbgt_c"], heavy["peak_time"]) == (5, 27.5, "10:00")
    assert (heavy["limited_from"], heavy["limited_until"]) == ("09:00", "11:00")
    assert (heavy["hours_work_rest"], heavy["worst_level"]) == (2, "work_rest")
    assert pd.isna(summary.loc["light", "limited_from"])


def test_bad_configuration_is_refused(config_path):
    import yaml

    raw = yaml.safe_load((config_path.parent / "heat_guidance.yaml").read_text())
    raw["work_minutes_per_hour"] = [45, 30]
    with pytest.raises(ValueError, match="include 60"):
        bands.guidance_from_dict(raw)


def test_every_english_string_has_a_kiswahili_twin(guidance):
    assert set(guidance.swahili["work_types"]) == set(guidance.work_types)
    assert set(guidance.swahili["levels"]) == set(bands.LEVELS)
    assert set(guidance.swahili["advice"]) == set(guidance.advice)


def test_a_missing_kiswahili_string_is_refused(config_path):
    import yaml

    raw = yaml.safe_load((config_path.parent / "heat_guidance.yaml").read_text())
    del raw["swahili"]["levels"]["work_rest"]
    with pytest.raises(ValueError, match="no Kiswahili for levels: work_rest"):
        bands.guidance_from_dict(raw)


def test_forecast_guidance_document(guidance):
    station = {"name": "Conduit@Empathy1", "latitude": -1.1, "longitude": 37.0}
    document = forecast_guidance(
        forecast_table(),
        guidance,
        station,
        TIMEZONE,
        "ecmwf_ifs",
        datetime(2026, 9, 19, tzinfo=UTC),
    )

    assert document["forecast"] == {"model": "ecmwf_ifs", "corrected_towards_station": True}
    assert document["generated_at_utc"] == "2026-09-19T00:00:00Z"
    assert document["work_types"]["heavy"]["limit_acclimatized_c"] == 26.0
    assert document["work_types"]["heavy"]["examples"]
    hour = document["hours"][4]
    assert (hour["local_time"], hour["wbgt_c"], hour["wbgt_high_c"]) == (
        "2026-09-20 10:00",
        27.5,
        30.5,
    )
    assert hour["by_work_type"]["heavy"]["level"] == "work_rest"
    assert isinstance(hour["by_work_type"]["heavy"]["work_minutes_acclimatized"], int)
    assert document["hours"][5]["by_work_type"]["heavy"]["level"] is None
    assert document["days"][0]["by_work_type"]["heavy"]["limited_from"] == "09:00"
    assert "NIOSH" in document["sources"][0]


def test_raw_forecast_guidance_has_no_band(guidance):
    table = forecast_table().drop(columns=["wbgt_corrected_c", "wbgt_low_c", "wbgt_high_c"])
    document = forecast_guidance(table, guidance, {}, TIMEZONE, "ecmwf_ifs", datetime.now(UTC))

    assert document["forecast"]["corrected_towards_station"] is False
    assert document["hours"][0]["wbgt_low_c"] is None
