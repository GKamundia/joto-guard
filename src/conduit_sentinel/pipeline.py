"""Run ingest, QC, aggregation, health scoring, audits and the report in one call."""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .aggregate import hourly
from .audit import run_audits
from .config import Config
from .health import group_status, health_daily
from .ingest import IngestResult, ingest
from .qc import QCResult, apply_qc
from .report import build_report


@dataclass(frozen=True)
class SentinelRun:
    ingest: IngestResult
    qc: QCResult
    hourly: pd.DataFrame
    group_status: pd.DataFrame
    health: pd.DataFrame
    audits: pd.DataFrame
    report: dict[str, Any]


def run(
    paths: Iterable[str | Path], config: Config, *, generated_at: datetime | None = None
) -> SentinelRun:
    ingested = ingest(paths)
    qc = apply_qc(ingested.obs, config, ingested.coverage)
    status = group_status(qc, config)
    health = health_daily(qc, status, config)
    audits = run_audits(qc.obs, config)
    report = build_report(ingested, qc, health, status, audits, config, generated_at=generated_at)
    return SentinelRun(
        ingest=ingested,
        qc=qc,
        hourly=hourly(qc.obs, config),
        group_status=status,
        health=health,
        audits=audits,
        report=report,
    )


def write_outputs(result: SentinelRun, out_dir: str | Path) -> list[Path]:
    """Write the tables as CSV and the report as JSON; returns the paths written."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tables = {
        "obs_qc.csv": result.qc.obs,
        "gaps.csv": result.qc.gaps,
        "rule_hits.csv": result.qc.rule_hits,
        "obs_hourly.csv": result.hourly,
        "channel_status_daily.csv": result.group_status,
        "health_daily.csv": result.health,
        "audit_results.csv": result.audits,
    }
    written = []
    for name, table in tables.items():
        path = out / name
        csv_ready(table).to_csv(path, index=False)
        written.append(path)

    report_path = out / "report.json"
    text = json.dumps(result.report, indent=2, ensure_ascii=False, allow_nan=False)
    report_path.write_text(text + "\n", encoding="utf-8")
    written.append(report_path)
    return written


def csv_ready(table: pd.DataFrame) -> pd.DataFrame:
    """Times as ISO 8601 with Z, and list cells joined with semicolons."""
    out = table.copy()
    for column in out.columns:
        values = out[column]
        if isinstance(values.dtype, pd.DatetimeTZDtype):
            out[column] = values.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif values.dtype == object and values.map(lambda v: isinstance(v, list)).any():
            out[column] = values.map(lambda v: ";".join(v) if isinstance(v, list) else v)
    return out
