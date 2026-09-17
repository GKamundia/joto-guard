"""Hourly aggregation with coverage (spec section 4, obs_hourly)."""

import numpy as np
import pandas as pd

from .config import Config
from .qc import EPS, usable

# How each variable becomes an hourly value. Device codes, the station's running rain
# totals and the duplicated gust-direction column have no meaningful hourly value.
HOURLY_AGGREGATION: dict[str, str] = {
    "battery_voltage": "mean",
    "cell_signal": "mean",
    "rain1_mm": "sum",
    "rain2_mm": "sum",
    "t_bmx_c": "mean",
    "p_station_hpa": "mean",
    "t_mcp_c": "mean",
    "t_sht_c": "mean",
    "rh_pct": "mean",
    "light_vis_counts": "mean",
    "light_ir_counts": "mean",
    "uv_index": "mean",
    "wind_speed_ms": "mean",
    "wind_dir_deg": "circular_mean",
    "wind_gust_ms": "max",
    "heat_index_fw_c": "mean",
    "wet_bulb_fw_c": "mean",
    "wbgt_fw_c": "mean",
}

HOURLY_COLUMNS = ("station_id", "hour_utc", "n_obs", "coverage_pct", *HOURLY_AGGREGATION)


def hourly(obs_qc: pd.DataFrame, config: Config) -> pd.DataFrame:
    """One row per UTC hour from the first to the last observation, empty hours included.

    Only values flagged good or suspect are used. A value is null when the hour's
    coverage_pct is below hourly.min_coverage_pct, or when the usable values of that
    variable cover less than hourly.min_variable_coverage_pct of the expected count.
    """
    if obs_qc.empty:
        return pd.DataFrame(columns=list(HOURLY_COLUMNS))

    expected = 3600 / config.station.expected_interval_s
    hour = obs_qc["time_utc"].dt.floor("h")
    hours = pd.date_range(hour.min(), hour.max(), freq="h", name="hour_utc")
    n_obs = hour.value_counts().reindex(hours, fill_value=0)
    coverage = n_obs / expected * 100
    enough_rows = coverage >= config.hourly.min_coverage_pct - EPS

    out = pd.DataFrame(index=hours)
    out["station_id"] = int(obs_qc["station_id"].iloc[0])
    out["n_obs"] = n_obs
    out["coverage_pct"] = coverage.round(1)
    for variable, how in HOURLY_AGGREGATION.items():
        values = usable(obs_qc, variable).astype("float64")
        grouped = values.groupby(hour)
        if how == "circular_mean":
            aggregated = _circular_mean_deg(values, hour)
        elif how == "sum":
            aggregated = grouped.sum(min_count=1)
        else:
            aggregated = grouped.agg(how)
        usable_pct = grouped.count().reindex(hours, fill_value=0) / expected * 100
        keep = enough_rows & (usable_pct >= config.hourly.min_variable_coverage_pct - EPS)
        out[variable] = aggregated.reindex(hours).where(keep).round(2)

    return out.reset_index()[list(HOURLY_COLUMNS)]


def _circular_mean_deg(degrees: pd.Series, hour: pd.Series) -> pd.Series:
    radians = np.deg2rad(degrees)
    sin = np.sin(radians).groupby(hour).mean()
    cos = np.cos(radians).groupby(hour).mean()
    return np.rad2deg(np.arctan2(sin, cos)).round(2) % 360
