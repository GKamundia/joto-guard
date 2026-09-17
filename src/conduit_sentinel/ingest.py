"""Read CHORDS GeoCSV exports into the obs_raw table (spec sections 2 to 5)."""

import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .schema import (
    CANONICAL_NAMES,
    CODE_VARIABLES,
    OBS_RAW_COLUMNS,
    TIME,
    VARIABLE_COLUMNS,
    VARIABLES,
)

log = logging.getLogger(__name__)

# Sorts after any real time, for files without a single readable row.
NO_TIME = pd.Timestamp.max.tz_localize("UTC")


@dataclass(frozen=True)
class Station:
    station_id: int
    name: str
    site: str | None
    latitude: float
    longitude: float
    elevation_m: float
    doi: str | None


@dataclass(frozen=True)
class SourceFile:
    name: str
    metadata: dict[str, str]
    columns: int
    rows: int
    first_utc: pd.Timestamp | None
    last_utc: pd.Timestamp | None
    measurements_declared: int | None
    measurements_counted: int
    invalid_times: int
    invalid_values: int

    @property
    def measurements_match(self) -> bool | None:
        if self.measurements_declared is None:
            return None
        return self.measurements_declared == self.measurements_counted


@dataclass(frozen=True)
class IngestResult:
    obs: pd.DataFrame
    station: Station
    files: tuple[SourceFile, ...]
    duplicates_removed: int
    conflicting_duplicates: int


def read_geocsv(path: str | Path) -> tuple[dict[str, str], pd.DataFrame]:
    """Split a GeoCSV file into its `# key: value` metadata and the data as text columns.

    Metadata keys are lower-cased with whitespace collapsed, so "Measurements in File"
    becomes "measurements in file". Cells stay as stripped strings; empty means no value.
    """
    path = Path(path)
    metadata: dict[str, str] = {}
    lines_before_header = 0
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            text = line.strip()
            if text and not text.startswith("#"):
                break
            key, sep, value = text.lstrip("#").partition(":")
            if sep and key.strip():
                metadata[" ".join(key.split()).lower()] = value.strip()
            lines_before_header += 1
        else:
            raise ValueError(f"{path.name}: no header row")

    frame = pd.read_csv(
        path,
        skiprows=lines_before_header,
        dtype=str,
        keep_default_na=False,
        skipinitialspace=True,
        encoding="utf-8-sig",
    )
    frame.columns = [str(c).strip() for c in frame.columns]
    return metadata, frame.apply(lambda column: column.str.strip())


def station_from_metadata(metadata: Mapping[str, str], source: str = "input") -> Station:
    try:
        return Station(
            station_id=int(_leading_number(metadata["sensor_id"])),
            name=metadata.get("instrument_name", ""),
            site=metadata.get("data collection site"),
            latitude=_leading_number(metadata["data collection latitude"]),
            longitude=_leading_number(metadata["data collection longitude"]),
            elevation_m=_leading_number(metadata["data collection elevation"]),
            doi=metadata.get("doi"),
        )
    except KeyError as exc:
        raise ValueError(f"{source}: metadata has no {exc.args[0]!r} entry") from None


def ingest(paths: Iterable[str | Path]) -> IngestResult:
    """Parse, map and merge GeoCSV files from one station into obs_raw.

    A timestamp repeated across files is kept once, from the file whose record starts
    earliest, and the number removed is logged. Rows whose time cannot be read are
    dropped and counted.
    """
    paths = [Path(p) for p in paths]
    if not paths:
        raise ValueError("no input files")

    loaded = []
    for path in paths:
        metadata, raw = read_geocsv(path)
        frame, invalid_values = _canonical_frame(raw, path.name)
        invalid_times = int(frame["time_utc"].isna().sum())
        if invalid_times:
            log.warning("%s: dropped %d rows with an unreadable time", path.name, invalid_times)
        frame = frame[frame["time_utc"].notna()].assign(source_file=path.name)
        source = SourceFile(
            name=path.name,
            metadata=metadata,
            columns=raw.shape[1],
            rows=len(raw),
            first_utc=frame["time_utc"].min() if len(frame) else None,
            last_utc=frame["time_utc"].max() if len(frame) else None,
            measurements_declared=_declared_measurements(metadata),
            measurements_counted=_count_measurements(raw),
            invalid_times=invalid_times,
            invalid_values=invalid_values,
        )
        loaded.append((source, frame, station_from_metadata(metadata, path.name)))

    # Earliest record first, so its copy of a repeated timestamp is the one kept.
    loaded.sort(key=lambda item: item[0].first_utc or NO_TIME)
    files = [source for source, _, _ in loaded]
    frames = [frame for _, frame, _ in loaded]
    stations = [station for _, _, station in loaded]

    for file in files:
        if file.measurements_match is False:
            log.warning(
                "%s: header declares %d measurements but the file holds %d",
                file.name,
                file.measurements_declared,
                file.measurements_counted,
            )

    station = _single_station(stations)
    obs = pd.concat(frames, ignore_index=True).sort_values("time_utc", kind="stable")
    duplicated = obs["time_utc"].duplicated(keep="first")
    conflicting = _conflicting_duplicates(obs)
    obs = obs[~duplicated].reset_index(drop=True)
    obs.insert(0, "station_id", station.station_id)

    removed = int(duplicated.sum())
    if removed:
        log.info("removed %d duplicate timestamps", removed)
    if conflicting:
        log.warning("%d duplicated timestamps had different values; kept the first", conflicting)

    return IngestResult(
        obs=obs[list(OBS_RAW_COLUMNS)],
        station=station,
        files=tuple(files),
        duplicates_removed=removed,
        conflicting_duplicates=conflicting,
    )


def _canonical_frame(raw: pd.DataFrame, source: str) -> tuple[pd.DataFrame, int]:
    if TIME.geocsv not in raw.columns:
        raise ValueError(f"{source}: no {TIME.geocsv!r} column")
    unknown = [c for c in raw.columns if c not in CANONICAL_NAMES]
    if unknown:
        log.warning("%s: ignoring unknown columns %s", source, unknown)
    absent = [c.geocsv for c in VARIABLE_COLUMNS if c.geocsv not in raw.columns]
    if absent:
        log.warning("%s: columns not in file, treated as empty: %s", source, absent)

    columns = {
        "time_utc": pd.to_datetime(raw[TIME.geocsv], utc=True, format="ISO8601", errors="coerce")
    }
    invalid_values = 0
    for column in VARIABLE_COLUMNS:
        text = raw.get(column.geocsv, pd.Series("", index=raw.index, dtype=str))
        values = pd.to_numeric(text, errors="coerce")
        if column.name in CODE_VARIABLES:
            values = values.where(values % 1 == 0).astype("Int64")
        else:
            values = values.astype("float64")
        invalid_values += int(((text != "") & values.isna()).sum())
        columns[column.name] = values

    if invalid_values:
        log.warning("%s: %d cells could not be read as numbers", source, invalid_values)
    return pd.DataFrame(columns, index=raw.index), invalid_values


def _count_measurements(raw: pd.DataFrame) -> int:
    variables = [c.geocsv for c in VARIABLE_COLUMNS if c.geocsv in raw.columns]
    return int((raw[variables] != "").to_numpy().sum())


def _declared_measurements(metadata: Mapping[str, str]) -> int | None:
    value = metadata.get("measurements in file")
    if value is None:
        return None
    digits = re.sub(r"[,\s]", "", value)
    return int(digits) if digits.isdigit() else None


def _single_station(stations: list[Station]) -> Station:
    first = stations[0]
    ids = sorted({s.station_id for s in stations})
    if len(ids) > 1:
        raise ValueError(f"files come from different stations: {ids}")
    for other in stations[1:]:
        if (other.latitude, other.longitude, other.elevation_m) != (
            first.latitude,
            first.longitude,
            first.elevation_m,
        ):
            log.warning("station %d location differs between files", first.station_id)
            break
    return first


def _conflicting_duplicates(obs: pd.DataFrame) -> int:
    repeated = obs[obs["time_utc"].duplicated(keep=False)]
    if repeated.empty:
        return 0
    distinct = repeated.groupby("time_utc")[list(VARIABLES)].nunique(dropna=False)
    return int((distinct > 1).any(axis=1).sum())


def _leading_number(text: str) -> float:
    match = re.match(r"\s*([-+]?\d+(?:\.\d+)?)", text)
    if match is None:
        raise ValueError(f"not a number: {text!r}")
    return float(match.group(1))
