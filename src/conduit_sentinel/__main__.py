"""Command line: python -m conduit_sentinel [files or folders] --out data/processed"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from .config import ConfigError, load_config
from .pipeline import SentinelRun, run, write_outputs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="conduit-sentinel",
        description="Quality-control Conduit@Empathy1 GeoCSV exports and build the "
        "Station Health Report.",
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        default=[Path("data/raw/organiser")],
        help="GeoCSV files, or folders holding them (default: data/raw/organiser)",
    )
    parser.add_argument("--config", type=Path, default=Path("config/qc_rules.yaml"))
    parser.add_argument("--out", type=Path, default=Path("data/processed"))
    parser.add_argument("-v", "--verbose", action="store_true", help="log each step")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        config = load_config(args.config)
        paths = find_csv_files(args.inputs)
        result = run(paths, config)
        written = write_outputs(result, args.out)
    except (OSError, ConfigError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(summary(result))
    print(f"Wrote {len(written)} files to {args.out}")
    return 0


def find_csv_files(inputs: Sequence[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        if item.is_dir():
            paths.extend(sorted(item.glob("*.csv")))
        elif item.is_file():
            paths.append(item)
        else:
            raise FileNotFoundError(f"no such file or folder: {item}")
    if not paths:
        raise FileNotFoundError("no CSV files found in " + ", ".join(map(str, inputs)))
    return paths


def summary(result: SentinelRun) -> str:
    station, obs, health = result.ingest.station, result.qc.obs, result.health
    times, intervals = obs["time_utc"], result.qc.intervals
    n_files = len(result.ingest.files)
    lines = [
        f"Station {station.station_id}: {station.name}",
        f"Observations: {len(obs):,} from {n_files} file{'' if n_files == 1 else 's'} "
        f"({result.ingest.duplicates_removed:,} duplicate timestamps removed)",
        f"Record: {times.min():%Y-%m-%dT%H:%M:%SZ} to {times.max():%Y-%m-%dT%H:%M:%SZ}",
        f"Gaps: {intervals.gaps}; late intervals: {intervals.late}",
        f"Daily health score: {health['score'].min():g} to {health['score'].max():g} "
        f"over {len(health)} days",
    ]
    if intervals.between_exports:
        lines.append(
            f"Exports do not meet {intervals.between_exports} time(s); "
            "days no export covers are not scored"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
