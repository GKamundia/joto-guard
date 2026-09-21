"""How often heat limits are crossed across the whole year, not just the weeks on record.

The station's own record is three cool-season weeks in August and September. On its own
it would say Juja is a mild place to work, and anyone reading only that would be right to
ask why a heat warning is needed at all. The answer is in the months the record does not
cover, so this reconstructs them.

ERA5 reanalysis gives every hour since 2016 at the station's grid cell, and the same WBGT
model the rest of the project uses runs on it. Measured against the station over the weeks
they share, ERA5 WBGT reads about 2 degC cool during working hours, cool in most of them.
Two figures follow from that:

- **at least**: raw ERA5, which reads cool, so the true share is higher. No assumptions.
- **likely**: ERA5 corrected towards the station hour of day by hour of day, the same way
  the forecast is corrected. Better, but the correction was measured in the cool season and
  is being applied to the hot one.

Only working hours count, 07:00 to 18:00 local, because a limit crossed at 03:00 changes
nobody's work.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import bands
from .forecast import VARIABLES, fetch_json, forecast_wbgt

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
WORK_START_H = 7
WORK_END_H = 18
HOT_MONTHS = (1, 2, 3)
RECORD_MONTHS = (8, 9)
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def request_params(latitude: float, longitude: float, elevation_m: float, start: str, end: str):
    """The archive request: the forecast's own inputs, from ERA5, in UTC and m/s."""
    return {
        "latitude": f"{latitude:.6f}",
        "longitude": f"{longitude:.6f}",
        "elevation": f"{elevation_m:g}",
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(VARIABLES),
        "models": "era5",
        "wind_speed_unit": "ms",
        "timezone": "GMT",
    }


def fetch(latitude: float, longitude: float, elevation_m: float, start: str, end: str):
    params = request_params(latitude, longitude, elevation_m, start, end)
    return fetch_json(ARCHIVE_URL, params, timeout_s=300)


def hourly_wbgt(payload: dict[str, Any], latitude: float, longitude: float, timezone: str):
    """WBGT for every hour of the reanalysis, with the local time it falls at."""
    table = forecast_wbgt(payload, latitude, longitude)
    table = table.dropna(subset=["wbgt_c"]).copy()
    table["hour_utc"] = pd.to_datetime(table["hour_utc"], utc=True)
    local = table["hour_utc"].dt.tz_convert(timezone)
    table["local_hour"] = local.dt.hour
    table["month"] = local.dt.month
    table["year"] = local.dt.year
    return table[["hour_utc", "local_hour", "month", "year", "wbgt_c"]].reset_index(drop=True)


def working(table: pd.DataFrame) -> pd.DataFrame:
    return table[table["local_hour"].between(WORK_START_H, WORK_END_H - 1)]


def station_offsets(reanalysis: pd.DataFrame, station: pd.DataFrame) -> np.ndarray:
    """Station minus ERA5 WBGT by local hour, over the hours both have.

    Hours of the day the overlap never saw keep the overall mean rather than zero.
    """
    pairs = (
        station[["hour_utc", "wbgt_c"]]
        .rename(columns={"wbgt_c": "station"})
        .merge(
            reanalysis[["hour_utc", "local_hour", "wbgt_c"]].rename(columns={"wbgt_c": "era5"}),
            on="hour_utc",
        )
    )
    pairs = pairs.dropna()
    if pairs.empty:
        raise ValueError("the station and the reanalysis share no hours")
    difference = pairs["station"] - pairs["era5"]
    by_hour = difference.groupby(pairs["local_hour"]).mean()
    return by_hour.reindex(range(24)).fillna(difference.mean()).to_numpy()


def _over(values: np.ndarray, limit: float) -> float:
    return round(100 * float((values > limit + bands.EPS).mean()), 1) if len(values) else 0.0


def shares(table: pd.DataFrame, guidance: bands.HeatGuidance, column: str) -> dict[str, Any]:
    """For each work type, the share of working hours over each limit."""
    values = working(table)[column].to_numpy()
    result = {}
    for work_type, rate in guidance.work_types.items():
        result[work_type] = {
            "over_new_workers_pct": _over(values, guidance.new_workers.at(rate)),
            "over_acclimatized_pct": _over(values, guidance.acclimatized.at(rate)),
        }
    return result


def summarise(
    reanalysis: pd.DataFrame,
    offsets: np.ndarray,
    guidance: bands.HeatGuidance,
    generated_at: datetime,
) -> dict[str, Any]:
    """Everything the page shows: the hot season against the months on record, and the
    whole year month by month, each as a floor and a likely figure."""
    table = reanalysis.assign(corrected_c=reanalysis["wbgt_c"] + offsets[reanalysis["local_hour"]])
    hot = table[table["month"].isin(HOT_MONTHS)]
    record = table[table["month"].isin(RECORD_MONTHS)]

    by_month = []
    for month in range(1, 13):
        rows = table[table["month"] == month]
        by_month.append(
            {
                "month": month,
                "name": MONTH_NAMES[month - 1],
                "peak_wbgt_c": round(float(working(rows)["corrected_c"].quantile(0.99)), 1)
                if len(rows)
                else None,
                "at_least": shares(rows, guidance, "wbgt_c"),
                "likely": shares(rows, guidance, "corrected_c"),
            }
        )

    work_hours = working(table)
    return {
        "generated_at_utc": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "ERA5 reanalysis through Open-Meteo, at the station's grid cell",
        "years": [int(table["year"].min()), int(table["year"].max())],
        "working_hours": f"{WORK_START_H:02d}:00 to {WORK_END_H:02d}:00 local",
        "reanalysis_minus_station_c": round(float(-np.mean(offsets[WORK_START_H:WORK_END_H])), 2),
        "hot_months": [MONTH_NAMES[m - 1] for m in HOT_MONTHS],
        "record_months": [MONTH_NAMES[m - 1] for m in RECORD_MONTHS],
        "limits": {
            work_type: {
                "acclimatized_c": round(float(guidance.acclimatized.at(rate)), 1),
                "new_workers_c": round(float(guidance.new_workers.at(rate)), 1),
            }
            for work_type, rate in guidance.work_types.items()
        },
        "hot_season": {
            "at_least": shares(hot, guidance, "wbgt_c"),
            "likely": shares(hot, guidance, "corrected_c"),
            "n_working_hours": len(working(hot)),
        },
        "record_season": {
            "at_least": shares(record, guidance, "wbgt_c"),
            "likely": shares(record, guidance, "corrected_c"),
            "n_working_hours": len(working(record)),
        },
        "by_month": by_month,
        "n_working_hours": len(work_hours),
    }


def save(summary: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def cache_name(start: str, end: str) -> str:
    return f"open_meteo_era5_wbgt_inputs_{start}_{end}.json"
