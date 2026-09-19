import pytest
import yaml

from conduit_sentinel.config import ConfigError, config_from_dict, load_config


@pytest.fixture
def raw(config_path):
    with open(config_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_repository_config_holds_spec_defaults(config_path):
    config = load_config(config_path)

    assert config.station.expected_interval_s == 60
    assert config.ranges.temperature_c == (-5.0, 45.0)
    assert config.ranges.humidity_pct == (0.0, 100.0)
    assert config.ranges.pressure_hpa == (800.0, 900.0)
    assert config.ranges.wind_speed_ms == (0.0, 60.0)
    assert config.ranges.wind_gust_ms == (0.0, 75.0)
    assert config.ranges.rain_mm == (0.0, 10.0)
    assert config.qc.light_dark_floor_counts == 240
    assert config.qc.max_step_c_per_min == 5.0
    assert config.qc.flat_line_rows == {
        "t_sht_c": 120,
        "rh_pct": 120,
        "p_station_hpa": 180,
        "wind_speed_ms": 180,
    }
    assert config.qc.max_thermometer_spread_c == 2.0
    assert config.qc.rain_disagreement_mm == 0.4
    assert config.qc.duplicate_column_share == 0.99
    assert (config.qc.late_interval_s, config.qc.gap_interval_s) == (120, 300)
    assert config.qc.wbgt_below_wet_bulb_margin_c == 1.5
    assert config.health.bad_group_penalty == 10
    assert config.health.suspect_group_penalty == 2
    assert config.health.missing_minutes_per_point == 14.4
    assert config.health.max_flagged_share == 0.05
    assert config.hourly.min_coverage_pct == 50
    assert config.audit.stull_max_mae_c == 0.1
    assert (config.audit.night_start_hour, config.audit.night_end_hour) == (19, 5)


def test_missing_key_is_reported_by_name(raw):
    del raw["qc"]["gap_interval_s"]
    with pytest.raises(ConfigError, match="gap_interval_s"):
        config_from_dict(raw)


def test_unknown_key_is_rejected(raw):
    raw["health"]["bonus"] = 5
    with pytest.raises(ConfigError, match="bonus"):
        config_from_dict(raw)


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("ranges", "temperature_c", [45.0, -5.0], "min must be below max"),
        ("ranges", "rain_mm", [0.0], r"\[min, max\]"),
        ("qc", "late_interval_s", 400, "below qc.gap_interval_s"),
        ("qc", "duplicate_column_share", 1.5, "between 0 and 1"),
        ("qc", "wbgt_below_wet_bulb_margin_c", -0.5, "must not be negative"),
        ("health", "bad_group_penalty", "ten", "must be a number"),
        ("audit", "night_start_hour", 24, "hour from 0 to 23"),
        ("station", "display_timezone", "Mars/Olympus", "unknown time zone"),
    ],
)
def test_invalid_values_are_rejected(raw, section, key, value, message):
    raw[section][key] = value
    with pytest.raises(ConfigError, match=message):
        config_from_dict(raw)


def test_flat_line_rows_must_cover_each_checked_variable(raw):
    del raw["qc"]["flat_line_rows"]["wind_speed_ms"]
    with pytest.raises(ConfigError, match="wind_speed_ms"):
        config_from_dict(raw)
