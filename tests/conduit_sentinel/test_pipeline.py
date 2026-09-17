import json

import pandas as pd

from conduit_sentinel.__main__ import main
from conduit_sentinel.pipeline import run, write_outputs

OUTPUT_FILES = {
    "obs_qc.csv",
    "gaps.csv",
    "obs_hourly.csv",
    "channel_status_daily.csv",
    "health_daily.csv",
    "audit_results.csv",
    "report.json",
}


def fixture_files(fixtures_dir):
    return [fixtures_dir / "conduit_part_a.csv", fixtures_dir / "conduit_part_b.csv"]


def test_run_connects_every_stage(fixtures_dir, config):
    result = run(fixture_files(fixtures_dir), config)

    assert len(result.ingest.obs) == len(result.qc.obs) == 10
    assert result.hourly["n_obs"].tolist() == [10]
    assert result.health["bad_groups"].tolist() == [["wind_gust_dir", "battery"]]
    assert result.report["station"]["duplicates_removed"] == 2


def test_outputs_are_written_as_csv_and_json(fixtures_dir, config, tmp_path):
    written = write_outputs(run(fixture_files(fixtures_dir), config), tmp_path)

    assert {path.name for path in written} == OUTPUT_FILES
    obs_qc = pd.read_csv(tmp_path / "obs_qc.csv")
    assert obs_qc.loc[0, "time_utc"] == "2026-08-28T00:00:25Z"
    health = pd.read_csv(tmp_path / "health_daily.csv")
    assert health.loc[0, "bad_groups"] == "wind_gust_dir;battery"
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["station"]["source_files"][0]["measurements_counted"] == 144


def test_command_line_run(fixtures_dir, config_path, tmp_path, capsys):
    code = main([str(fixtures_dir), "--config", str(config_path), "--out", str(tmp_path)])

    assert code == 0
    output = capsys.readouterr().out
    assert "Observations: 10 from 2 files (2 duplicate timestamps removed)" in output
    assert (tmp_path / "report.json").exists()


def test_command_line_reports_a_missing_input(tmp_path, config_path, capsys):
    code = main([str(tmp_path / "absent.csv"), "--config", str(config_path)])

    assert code == 1
    assert "no such file or folder" in capsys.readouterr().err


def test_command_line_accepts_single_files(fixtures_dir, config_path, tmp_path, capsys):
    code = main(
        [
            str(fixtures_dir / "conduit_part_a.csv"),
            "--config",
            str(config_path),
            "--out",
            str(tmp_path),
        ]
    )

    assert code == 0
    assert "Observations: 6 from 1 file " in capsys.readouterr().out


def test_command_line_reports_an_empty_folder(tmp_path, config_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()

    code = main([str(empty), "--config", str(config_path), "--out", str(tmp_path)])

    assert code == 1
    assert "no CSV files found" in capsys.readouterr().err


def test_command_line_notes_exports_that_do_not_meet(fixtures_dir, config_path, tmp_path, capsys):
    later = tmp_path / "later.csv"
    later.write_text(
        (fixtures_dir / "conduit_part_b.csv").read_text().replace("2026-08-28T", "2026-09-28T")
    )

    code = main(
        [
            str(fixtures_dir / "conduit_part_a.csv"),
            str(later),
            "--config",
            str(config_path),
            "--out",
            str(tmp_path / "out"),
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "Exports do not meet 1 time(s)" in output
    assert "over 2 days" in output  # 28 Aug and 28 Sep, not the month between them
