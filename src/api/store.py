"""Read the Sentinel outputs from disk and keep them until the files change."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

REPORT_FILE = "report.json"

TABLE_FILES = {
    "hourly": "obs_hourly.csv",
    "health": "health_daily.csv",
    "channel_status": "channel_status_daily.csv",
    "rule_hits": "rule_hits.csv",
    "gaps": "gaps.csv",
    "audits": "audit_results.csv",
}

# What /v1/dataset will hand out: everything the pipeline writes.
DOWNLOADS = frozenset({REPORT_FILE, "obs_qc.csv", *TABLE_FILES.values()})


class OutputsMissing(RuntimeError):
    """The pipeline has not written its outputs to this folder yet."""


@dataclass(frozen=True)
class SentinelOutputs:
    report: dict[str, Any]
    hourly: pd.DataFrame
    health: pd.DataFrame
    channel_status: pd.DataFrame
    rule_hits: pd.DataFrame
    gaps: pd.DataFrame
    audits: pd.DataFrame


class OutputStore:
    """Loads the outputs once, then again whenever the files on disk change.

    Re-running the pipeline is enough to refresh the API; nothing needs restarting.
    """

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self._outputs: SentinelOutputs | None = None
        self._fingerprint: tuple | None = None

    def read(self) -> SentinelOutputs:
        fingerprint = self._current_fingerprint()
        if self._outputs is None or fingerprint != self._fingerprint:
            self._outputs = self._load()
            self._fingerprint = fingerprint
        return self._outputs

    def download_path(self, name: str) -> Path:
        if name not in DOWNLOADS:
            raise FileNotFoundError(name)
        path = self.directory / name
        if not path.is_file():
            raise OutputsMissing(self._advice())
        return path

    def _load(self) -> SentinelOutputs:
        report_path = self.directory / REPORT_FILE
        if not report_path.is_file():
            raise OutputsMissing(self._advice())
        tables = {name: self._read_table(file_name) for name, file_name in TABLE_FILES.items()}
        if "hour_utc" in tables["hourly"]:
            tables["hourly"]["hour_utc"] = pd.to_datetime(tables["hourly"]["hour_utc"], utc=True)
        return SentinelOutputs(report=json.loads(report_path.read_text(encoding="utf-8")), **tables)

    def _read_table(self, file_name: str) -> pd.DataFrame:
        path = self.directory / file_name
        if not path.is_file():
            raise OutputsMissing(f"{path} is missing. {self._advice()}")
        return pd.read_csv(path)

    def _current_fingerprint(self) -> tuple:
        stamps = []
        for name in (REPORT_FILE, *TABLE_FILES.values()):
            path = self.directory / name
            stat = path.stat() if path.is_file() else None
            stamps.append(
                (name, stat.st_mtime_ns if stat else None, stat.st_size if stat else None)
            )
        return tuple(stamps)

    def _advice(self) -> str:
        return (
            f"No Sentinel outputs in {self.directory}. Run "
            f"'python -m conduit_sentinel data/raw/organiser --out {self.directory}' first."
        )


def records(frame: pd.DataFrame, columns: list[str] | None = None) -> list[dict]:
    """Rows as dictionaries, keeping the column order."""
    if columns:
        frame = frame[[c for c in columns if c in frame.columns]]
    return frame.to_dict(orient="records")
