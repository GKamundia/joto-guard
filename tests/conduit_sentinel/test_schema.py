from conduit_sentinel.schema import (
    CANONICAL_NAMES,
    CHANNEL_GROUPS,
    GEOCSV_NAMES,
    SCORED_GROUPS,
    VARIABLES,
    Flag,
)


def test_column_map_covers_time_and_25_variables():
    assert len(CANONICAL_NAMES) == 26
    assert len(VARIABLES) == 25
    assert len(set(CANONICAL_NAMES.values())) == 26
    assert CANONICAL_NAMES["Time"] == "time_utc"
    assert CANONICAL_NAMES["Wet Bulb Globe Temperature"] == "wbgt_fw_c"


def test_geocsv_names_invert_the_canonical_map():
    assert GEOCSV_NAMES["battery_voltage"] == "Battery Voltage"
    assert {GEOCSV_NAMES[name] for name in VARIABLES} <= set(CANONICAL_NAMES)


def test_every_grouped_variable_exists_and_belongs_to_one_group():
    grouped = [v for members in CHANNEL_GROUPS.values() for v in members]
    assert len(grouped) == len(set(grouped))
    assert set(grouped) <= set(VARIABLES)
    assert set(VARIABLES) - set(grouped) == {"health_code"}


def test_firmware_derived_group_is_not_scored():
    assert "derived_fw" in CHANNEL_GROUPS
    assert "derived_fw" not in SCORED_GROUPS
    assert len(SCORED_GROUPS) == 10


def test_flag_codes_match_spec():
    assert [int(f) for f in Flag] == [0, 1, 2, 3, 4]
    assert Flag.SUSPECT < Flag.BAD < Flag.MISSING
