"""FastAPI service over the Sentinel outputs: the Station Health Report and its tables."""

import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from conduit_sentinel import __version__
from conduit_sentinel.report import to_json_ready
from conduit_sentinel.schema import VARIABLE_COLUMNS

from .store import DOWNLOADS, OutputsMissing, OutputStore, SentinelOutputs, records

DEFAULT_DATA_DIR = Path("data/processed")
DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")

UNITS = {column.name: column.unit for column in VARIABLE_COLUMNS}

DESCRIPTION = """
Quality-controlled observations from the Conduit@Empathy1 weather station
(CHORDS instrument 61, attribution 3d-fewsnet.icdp.ucar.edu).

Every endpoint reads what `python -m conduit_sentinel` last wrote, so re-running the
pipeline refreshes the API without a restart.
"""


def create_app(data_dir: str | Path | None = None, origins: Sequence[str] | None = None) -> FastAPI:
    store = OutputStore(data_dir or os.environ.get("SENTINEL_DATA_DIR", DEFAULT_DATA_DIR))
    app = FastAPI(
        title="Conduit Sentinel API",
        version=__version__,
        description=DESCRIPTION,
        contact={"name": "Hack The Weather 2026 entry"},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins if origins is not None else DEFAULT_ORIGINS),
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.state.store = store

    def outputs() -> SentinelOutputs:
        try:
            return store.read()
        except OutputsMissing as missing:
            raise HTTPException(status_code=503, detail=str(missing)) from missing

    @app.get("/", summary="What this service offers")
    def index() -> dict[str, Any]:
        return {
            "service": "Conduit Sentinel",
            "version": __version__,
            "documentation": "/docs",
            "endpoints": [
                "/v1/stations",
                "/v1/station-health",
                "/v1/qc?days=7",
                "/v1/history?var=t_sht_c",
                "/v1/dataset/{name}",
            ],
        }

    @app.get("/v1/stations", summary="The stations this service holds data for")
    def stations() -> list[dict[str, Any]]:
        data = outputs()
        card = data.report["station"]
        health = data.health
        latest = records(health.tail(1))
        return to_json_ready(
            [
                {
                    "station_id": card["station_id"],
                    "name": card["name"],
                    "site": card["site"],
                    "latitude": card["latitude"],
                    "longitude": card["longitude"],
                    "elevation_m": card["elevation_m"],
                    "attribution": card["attribution"],
                    "record_start_utc": card["record_start_utc"],
                    "record_end_utc": card["record_end_utc"],
                    "n_obs": card["n_obs"],
                    "export_windows": data.report["coverage"]["export_windows"],
                    "latest_health": latest[0] if latest else None,
                }
            ]
        )

    @app.get(
        "/v1/station-health",
        summary="The Station Health Report",
        description="Everything in section 10 of docs/SENTINEL_SPEC.md, as the web page uses it.",
        response_model=None,
    )
    def station_health() -> dict[str, Any]:
        return outputs().report

    @app.get("/v1/qc", summary="Quality control over the most recent days")
    def qc(
        days: Annotated[int, Query(ge=1, le=400, description="how many covered days")] = 7,
    ) -> dict[str, Any]:
        data = outputs()
        wanted = list(data.health["date_utc"].tail(days))
        if not wanted:
            return {"days": [], "health": [], "channel_status": [], "rule_hits": [], "gaps": []}
        first = min(wanted)
        hits = data.rule_hits[data.rule_hits["date_utc"] >= first]
        empty_channels = hits.loc[hits["rule_id"] == "R12", "variable"]
        return to_json_ready(
            {
                "days": wanted,
                "health": records(data.health[data.health["date_utc"] >= first]),
                "channel_status": records(
                    data.channel_status[data.channel_status["date_utc"] >= first]
                ),
                "rule_hits": records(hits),
                "gaps": records(data.gaps[data.gaps["gap_end_utc"] >= f"{first}T00:00:00Z"]),
                "empty_channels": sorted(set(empty_channels)),
                "rules": data.report["rules"],
            }
        )

    @app.get("/v1/history", summary="One hourly variable over time")
    def history(
        var: Annotated[str, Query(description="canonical variable name, e.g. t_sht_c")],
        start: Annotated[datetime | None, Query(description="from this time (UTC)")] = None,
        end: Annotated[datetime | None, Query(description="to this time (UTC)")] = None,
        limit: Annotated[int, Query(ge=1, le=20000)] = 5000,
    ) -> dict[str, Any]:
        data = outputs()
        hourly = data.hourly
        if var not in hourly.columns or var in {"station_id", "hour_utc", "n_obs", "coverage_pct"}:
            available = [c for c in hourly.columns if c in UNITS]
            raise HTTPException(
                status_code=404,
                detail={"message": f"no hourly variable {var!r}", "available": available},
            )
        rows = hourly
        if start is not None:
            rows = rows[rows["hour_utc"] >= _as_utc(start)]
        if end is not None:
            rows = rows[rows["hour_utc"] <= _as_utc(end)]
        selected = rows.tail(limit)
        return to_json_ready(
            {
                "variable": var,
                "unit": UNITS.get(var),
                "n_hours": len(selected),
                "truncated": len(rows) > len(selected),
                "series": records(selected, ["hour_utc", var, "n_obs", "coverage_pct"]),
            }
        )

    @app.get("/v1/dataset/{name}", summary="Download a quality-controlled table")
    def dataset(
        name: Annotated[str, PathParam(description="file name, e.g. obs_qc.csv")],
    ) -> FileResponse:
        try:
            path = store.download_path(name)
        except FileNotFoundError as unknown:
            raise HTTPException(
                status_code=404, detail={"message": "unknown file", "available": sorted(DOWNLOADS)}
            ) from unknown
        except OutputsMissing as missing:
            raise HTTPException(status_code=503, detail=str(missing)) from missing
        return FileResponse(path, filename=name)

    return app


def _as_utc(moment: datetime) -> pd.Timestamp:
    stamp = pd.Timestamp(moment)
    return stamp.tz_localize(UTC) if stamp.tzinfo is None else stamp.tz_convert(UTC)


app = create_app()
