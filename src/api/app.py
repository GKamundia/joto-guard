"""FastAPI service over the Sentinel and Joto Guard outputs: the Station Health Report, its
tables, the station's WBGT and the heat guidance."""

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

from .store import (
    DOWNLOADS,
    CachedFile,
    OutputsMissing,
    OutputStore,
    SentinelOutputs,
    read_json,
    records,
)

DEFAULT_DATA_DIR = Path("data/processed")
DEFAULT_CONFIG_DIR = Path("config")
JOTO_ADVICE = "Run 'python -m joto_guard wbgt' and 'python -m joto_guard forecast' first."
WBGT_COLUMNS = [
    "hour_utc",
    "t_air_c",
    "rh_pct",
    "wind_2m_ms",
    "ghi_wm2",
    "tg_c",
    "tnwb_c",
    "wbgt_c",
    "wbgt_fw_c",
]

# The forecast table, minus the intermediate solar terms the page has no use for.
FORECAST_COLUMNS = [
    "hour_utc",
    "t_air_c",
    "rh_pct",
    "wind_2m_ms",
    "ghi_wm2",
    "tg_c",
    "tnwb_c",
    "wbgt_c",
    "wbgt_corrected_c",
    "wbgt_low_c",
    "wbgt_high_c",
]
# Vite moves to the next port when 5173 is taken, so a second dev server lands on 5174.
DEFAULT_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
)

UNITS = {column.name: column.unit for column in VARIABLE_COLUMNS}

DESCRIPTION = """
Quality-controlled observations from the Conduit@Empathy1 weather station
(CHORDS instrument 61, attribution 3d-fewsnet.icdp.ucar.edu).

Every endpoint reads what `python -m conduit_sentinel` last wrote, so re-running the
pipeline refreshes the API without a restart.
"""


def create_app(
    data_dir: str | Path | None = None,
    origins: Sequence[str] | None = None,
    config_dir: str | Path | None = None,
) -> FastAPI:
    allowed = origins if origins is not None else _origins_from_environment()
    store = OutputStore(data_dir or os.environ.get("SENTINEL_DATA_DIR", DEFAULT_DATA_DIR))
    configs = Path(config_dir or os.environ.get("JOTO_CONFIG_DIR", DEFAULT_CONFIG_DIR))
    guidance_file = CachedFile(store.directory / "heat_guidance.json", read_json, JOTO_ADVICE)
    wbgt_file = CachedFile(store.directory / "wbgt_hourly.csv", pd.read_csv, JOTO_ADVICE)
    forecast_file = CachedFile(store.directory / "wbgt_forecast.csv", pd.read_csv, JOTO_ADVICE)
    verification_file = CachedFile(
        configs / "forecast_verification.json",
        read_json,
        "Run 'python -m joto_guard verify --past-forecasts <file>'.",
    )
    season_file = CachedFile(
        configs / "hot_season.json", read_json, "Run 'python -m joto_guard hot-season'."
    )
    correction_file = CachedFile(
        configs / "forecast_correction.json",
        read_json,
        "Run 'python -m joto_guard fit-correction'.",
    )
    firmware_file = CachedFile(
        store.directory / "wbgt_firmware_by_hour.csv", pd.read_csv, JOTO_ADVICE
    )
    calibration_file = CachedFile(
        configs / "solar_calibration.json", read_json, "Run 'python -m joto_guard calibrate-light'."
    )
    app = FastAPI(
        title="Conduit Sentinel API",
        version=__version__,
        description=DESCRIPTION,
        contact={"name": "Hack The Weather 2026 entry"},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed),
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.state.store = store

    def outputs() -> SentinelOutputs:
        try:
            return store.read()
        except OutputsMissing as missing:
            raise HTTPException(status_code=503, detail=str(missing)) from missing

    def cached(file: CachedFile) -> Any:
        try:
            return file.read()
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
                "/v1/wbgt?days=7",
                "/v1/forecast",
                "/v1/hot-season",
                "/v1/heat-guidance",
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

    @app.get(
        "/v1/wbgt",
        summary="The station's hourly WBGT, and the firmware's column compared with it",
        description="Liljegren WBGT from the station's quality-controlled inputs (decision "
        "0007), the firmware WBGT minus it by local hour, and the light-sensor calibration.",
    )
    def wbgt(
        days: Annotated[int, Query(ge=1, le=400, description="how many days back")] = 7,
    ) -> dict[str, Any]:
        table = cached(wbgt_file)
        hours = pd.to_datetime(table["hour_utc"], utc=True)
        recent = table[hours > hours.max() - pd.Timedelta(days=days)]
        calibration = cached(calibration_file)
        return to_json_ready(
            {
                "method": "Liljegren et al. (2008), J. Occup. Environ. Hyg. 5, 645-655",
                "n_hours": len(recent),
                "hours": records(recent, WBGT_COLUMNS),
                "firmware_by_local_hour": records(cached(firmware_file)),
                "light_calibration": {
                    "formula": calibration["formula"],
                    "a": calibration["a"],
                    "b": calibration["b"],
                    "dark_floor_counts": calibration["dark_floor_counts"],
                    "reference": calibration["reference"],
                    "held_out": calibration["held_out"],
                },
            }
        )

    @app.get(
        "/v1/forecast",
        summary="The WBGT forecast, raw and corrected, with the weather behind it",
        description="What python -m joto_guard forecast last wrote: the forecast weather, the "
        "WBGT computed from it, the correction towards the station and its band (decisions "
        "0009 and 0010), plus how well the correction did on days left out of its fit.",
    )
    def forecast() -> dict[str, Any]:
        correction = cached(correction_file)
        return to_json_ready(
            {
                "model": correction["model"],
                "method": correction["method"],
                "timezone": correction["timezone"],
                "hours": records(cached(forecast_file), FORECAST_COLUMNS),
                "correction": {
                    "offsets_c": correction["offsets_c"],
                    "fitted_on": {
                        "first_day": correction["first_day"],
                        "last_day": correction["last_day"],
                        "n_days": correction["n_days"],
                        "n_pairs": correction["n_pairs"],
                    },
                    "held_out": correction["held_out"],
                },
                # Whether the level it implies was the right one, not only how many degrees
                # out it was. Optional: the forecast serves without it.
                "verification": _optional(verification_file),
            }
        )

    @app.get(
        "/v1/hot-season",
        summary="How often each limit is crossed in every month, not just the weeks on record",
        description="ERA5 since 2016 at the station's grid cell, run through the same WBGT "
        "model and corrected towards the station. `at_least` is raw ERA5, which reads cool; "
        "`likely` is corrected. Working hours only.",
    )
    def hot_season() -> dict[str, Any]:
        return cached(season_file)

    @app.get(
        "/v1/heat-guidance",
        summary="Heat guidance by type of work for each forecast hour",
        description="What python -m joto_guard forecast last wrote: WBGT with its band, NIOSH "
        "levels and allowed work minutes per hour for each type of work (decision 0011).",
        response_model=None,
    )
    def heat_guidance() -> dict[str, Any]:
        return cached(guidance_file)

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


def _origins_from_environment() -> Sequence[str]:
    """The deployed web app's origin, which is not known until it is deployed.

    JOTO_ALLOWED_ORIGINS is a comma-separated list; without it only the local Vite server
    may call the API.
    """
    setting = os.environ.get("JOTO_ALLOWED_ORIGINS", "").strip()
    if not setting:
        return DEFAULT_ORIGINS
    return tuple(origin.strip() for origin in setting.split(",") if origin.strip())


def _optional(file: CachedFile) -> Any:
    """A file the response is better with and can do without."""
    try:
        return file.read()
    except OutputsMissing:
        return None


def _as_utc(moment: datetime) -> pd.Timestamp:
    stamp = pd.Timestamp(moment)
    return stamp.tz_localize(UTC) if stamp.tzinfo is None else stamp.tz_convert(UTC)


app = create_app()
