"""Hourly WBGT forecasts from Open-Meteo, computed the same way as the station's series.

A weather model's temperature, humidity, pressure, wind and solar radiation go through
the same `wbgt_for_hours` as the station's measurements, so forecast and station WBGT
differ only in their inputs. Two Open-Meteo conventions differ from the station's hourly
means and are converted here:

- Shortwave radiation is stamped at the end of the hour it averages, so the value stamped
  10:00 belongs to the hour starting at 09:00.
- Temperature, humidity, pressure and wind are values at the stamp, so an hour's mean is
  taken as the average of the values at its start and its end.

Wind is forecast at 10 m and brought down to 2 m by the model's stability-dependent power
law. The default model is ECMWF IFS HRES (9 km, hourly for the first 90 hours).
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import pandas as pd

from .wbgt import wbgt_for_hours

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
PAST_FORECASTS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
DEFAULT_MODEL = "ecmwf_ifs"
WIND_HEIGHT_M = 10.0

# Open-Meteo variable -> column name, for the values taken at the stamp.
INSTANT_VARIABLES = {
    "temperature_2m": "t_air_c",
    "relative_humidity_2m": "rh_pct",
    "surface_pressure": "p_hpa",
    "wind_speed_10m": "wind_10m_ms",
}
RADIATION = "shortwave_radiation"
VARIABLES = [*INSTANT_VARIABLES, RADIATION]
INPUT_COLUMNS = ["hour_utc", *INSTANT_VARIABLES.values(), "ghi_wm2"]


def variable_name(variable: str, lead_day: int = 0) -> str:
    """The name of `variable` as forecast `lead_day` days before its valid time."""
    return variable if lead_day == 0 else f"{variable}_previous_day{lead_day}"


def request_params(
    latitude: float,
    longitude: float,
    elevation_m: float,
    model: str = DEFAULT_MODEL,
    lead_days: tuple[int, ...] = (0,),
    **extra: str | int,
) -> dict[str, str]:
    """Query parameters for an hourly request, in UTC and m/s, downscaled to `elevation_m`."""
    hourly = [variable_name(v, day) for day in lead_days for v in VARIABLES]
    params = {
        "latitude": f"{latitude:.6f}",
        "longitude": f"{longitude:.6f}",
        "elevation": f"{elevation_m:g}",
        "hourly": ",".join(hourly),
        "models": model,
        "wind_speed_unit": "ms",
        "timezone": "GMT",
    }
    return params | {key: str(value) for key, value in extra.items()}


def fetch_json(url: str, params: dict[str, str], timeout_s: float = 60) -> dict[str, Any]:
    """GET `url` with `params` and decode the JSON body; an API error raises ValueError."""
    request = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "joto-guard"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read() or b"{}")
        if not payload.get("reason"):
            raise
    if payload.get("error"):
        raise ValueError(f"Open-Meteo refused the request: {payload.get('reason')}")
    return payload


def hourly_inputs(payload: dict[str, Any], lead_day: int = 0) -> pd.DataFrame:
    """Hour-mean WBGT inputs from an Open-Meteo response, one row per hour starting at
    `hour_utc`. Hours at the ends of the response, which lack a neighbour, are left out."""
    if payload.get("timezone") not in {"GMT", "UTC"}:
        raise ValueError("request the forecast with timezone=GMT so its hours are UTC")
    hourly = payload["hourly"]
    names = {variable_name(v, lead_day): v for v in VARIABLES}
    missing = sorted(set(names) - hourly.keys())
    if missing:
        raise ValueError(f"response lacks {', '.join(missing)}")

    stamps = pd.to_datetime(hourly["time"], utc=True)
    values = pd.DataFrame(
        {names[name]: pd.to_numeric(pd.Series(hourly[name]), errors="coerce") for name in names}
    ).set_index(stamps)
    values = values.reindex(pd.date_range(stamps.min(), stamps.max(), freq="h"))

    ends = values.shift(-1)
    inputs = pd.DataFrame(
        {column: (values[v] + ends[v]) / 2 for v, column in INSTANT_VARIABLES.items()}
    )
    inputs["ghi_wm2"] = ends[RADIATION]
    inputs = inputs.iloc[:-1].rename_axis("hour_utc").reset_index()
    return inputs[INPUT_COLUMNS]


def forecast_wbgt(
    payload: dict[str, Any], latitude: float, longitude: float, lead_day: int = 0
) -> pd.DataFrame:
    """WBGT for every forecast hour, with the inputs used. Sun geometry is the station's."""
    inputs = hourly_inputs(payload, lead_day)
    modelled = wbgt_for_hours(
        inputs["hour_utc"],
        inputs["t_air_c"],
        inputs["rh_pct"],
        inputs["p_hpa"],
        inputs["wind_10m_ms"],
        inputs["ghi_wm2"],
        latitude,
        longitude,
        wind_height_m=WIND_HEIGHT_M,
    )
    return pd.concat([inputs, modelled.drop(columns="hour_utc")], axis=1)
