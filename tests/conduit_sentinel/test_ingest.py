import pandas as pd
import pytest

from conduit_sentinel.ingest import ingest, read_geocsv, station_from_metadata
from conduit_sentinel.schema import OBS_RAW_COLUMNS


def write_variant(source, target, replacements):
    text = source.read_text()
    for old, new in replacements:
        assert old in text
        text = text.replace(old, new, 1)
    target.write_text(text)
    return target


def test_read_geocsv_splits_metadata_from_data(fixtures_dir):
    metadata, frame = read_geocsv(fixtures_dir / "conduit_part_a.csv")

    assert metadata["sensor_id"] == "61"
    assert metadata["measurements in file"] == "144"
    assert metadata["creation_date"] == "2026-09-02 08:29:51 +0000"
    assert metadata["doi"] == "https://doi.org/10.5065/d6v1236q"
    assert metadata["delimiter"] == ","
    assert frame.shape == (6, 26)
    assert frame.loc[0, "Time"] == "2026-08-28T00:00:25Z"
    assert frame.loc[0, "Battery Voltage"] == ""


def test_station_metadata_is_parsed(fixtures_dir):
    metadata, _ = read_geocsv(fixtures_dir / "conduit_part_a.csv")
    station = station_from_metadata(metadata)

    assert station.station_id == 61
    assert station.name == "Kenya Kiambu JKUAT IOT AWS - Conduti@Empathy1"
    assert station.site == "Site JKUAT"
    # the header gives elevation as "1523.0 meters"
    assert (station.latitude, station.longitude, station.elevation_m) == (
        -1.099736,
        37.014528,
        1523.0,
    )
    assert station.doi == "https://doi.org/10.5065/d6v1236q"


def test_station_metadata_without_sensor_id_is_an_error():
    with pytest.raises(ValueError, match="sensor_id"):
        station_from_metadata({"data collection latitude": "-1.1"}, "x.csv")


def test_columns_are_renamed_and_typed(fixtures_dir):
    obs = ingest([fixtures_dir / "conduit_part_a.csv"]).obs

    assert list(obs.columns) == list(OBS_RAW_COLUMNS)
    assert obs.loc[0, "time_utc"] == pd.Timestamp("2026-08-28T00:00:25Z")
    assert str(obs["time_utc"].dt.tz) == "UTC"
    assert obs.loc[0, "t_sht_c"] == 12.6
    assert obs.loc[0, "light_ir_counts"] == 253
    assert obs["health_code"].dtype == "Int64"
    assert obs["battery_voltage"].isna().all()
    assert (obs["station_id"] == 61).all()
    assert (obs["source_file"] == "conduit_part_a.csv").all()


def test_measurement_count_is_checked_against_the_header(fixtures_dir):
    source = ingest([fixtures_dir / "conduit_part_a.csv"]).files[0]

    assert (source.rows, source.columns) == (6, 26)
    assert source.measurements_declared == 144
    assert source.measurements_counted == 144
    assert source.measurements_match is True


def test_overlapping_files_keep_each_timestamp_once(fixtures_dir):
    result = ingest([fixtures_dir / "conduit_part_b.csv", fixtures_dir / "conduit_part_a.csv"])
    obs = result.obs

    assert result.duplicates_removed == 2
    assert result.conflicting_duplicates == 0
    assert len(obs) == 10
    assert obs["time_utc"].is_monotonic_increasing
    assert [f.name for f in result.files] == ["conduit_part_a.csv", "conduit_part_b.csv"]
    overlap = obs["time_utc"] == pd.Timestamp("2026-08-28T00:04:27Z")
    assert obs.loc[overlap, "source_file"].item() == "conduit_part_a.csv"


def test_duplicates_with_different_values_are_counted(fixtures_dir, tmp_path):
    row = "2026-08-28T00:04:27Z,0,,3,100,0,0,0,0,0,0,12.2,"
    changed = write_variant(
        fixtures_dir / "conduit_part_b.csv",
        tmp_path / "changed.csv",
        [(row, row.replace("12.2,", "19.9,"))],
    )
    result = ingest([fixtures_dir / "conduit_part_a.csv", changed])

    assert result.duplicates_removed == 2
    assert result.conflicting_duplicates == 1
    kept = result.obs["time_utc"] == pd.Timestamp("2026-08-28T00:04:27Z")
    assert result.obs.loc[kept, "t_bmx_c"].item() == 12.2


def test_files_from_different_stations_are_refused(fixtures_dir, tmp_path):
    other = write_variant(
        fixtures_dir / "conduit_part_b.csv",
        tmp_path / "other.csv",
        [("# sensor_id: 61", "# sensor_id: 10")],
    )
    with pytest.raises(ValueError, match="different stations"):
        ingest([fixtures_dir / "conduit_part_a.csv", other])


def test_unreadable_times_and_values_are_counted(fixtures_dir, tmp_path):
    broken = write_variant(
        fixtures_dir / "conduit_part_a.csv",
        tmp_path / "broken.csv",
        [("2026-08-28T00:01:25Z", "not-a-time"), ("852.2", "n/a")],
    )
    result = ingest([broken])
    source = result.files[0]

    assert (source.rows, source.invalid_times, source.invalid_values) == (6, 1, 1)
    assert len(result.obs) == 5
    assert result.obs["p_station_hpa"].isna().sum() == 1


def test_absent_column_is_read_as_an_empty_channel(fixtures_dir, tmp_path):
    lines = (fixtures_dir / "conduit_part_a.csv").read_text().splitlines()
    header_at = next(i for i, line in enumerate(lines) if not line.startswith("#"))
    drop = lines[header_at].split(",").index("Heat Index")
    rows = [
        ",".join(cell for j, cell in enumerate(line.split(",")) if j != drop)
        for line in lines[header_at:]
    ]
    path = tmp_path / "no_heat_index.csv"
    path.write_text("\n".join(lines[:header_at] + rows) + "\n")

    result = ingest([path])

    assert result.obs["heat_index_fw_c"].isna().all()
    assert result.files[0].columns == 25
    assert result.files[0].measurements_match is False


def test_file_without_a_time_column_is_refused(tmp_path):
    path = tmp_path / "no_time.csv"
    path.write_text("# sensor_id: 61\nHealth,SHT Temperature\n0,12.0\n")
    with pytest.raises(ValueError, match="Time"):
        ingest([path])


def test_no_input_files_is_an_error():
    with pytest.raises(ValueError, match="no input files"):
        ingest([])
