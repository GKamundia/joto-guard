"""The station's hourly WBGT, and how the firmware's own WBGT column compares with it.

Inputs are Sentinel's quality-controlled hourly means and the light calibration (decision
0006). Air temperature and humidity both come from the SHT sensor: its humidity is relative
to its own temperature, so the pair gives the right vapour pressure, and it is the sensor
the firmware's derived columns are computed from. The station's three thermometers disagree
by up to 0.44 °C on average (audit A05), which moves WBGT by about 0.25 °C.
"""

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from .solar_calibration import Calibration, ghi_hourly
from .wbgt import REFERENCE_HEIGHT_M, wbgt_for_hours

# The station's own values, carried alongside for comparison.
FIRMWARE_COLUMNS = ["wbgt_fw_c", "wet_bulb_fw_c"]


def wbgt_hourly(
    hourly: pd.DataFrame,
    calibration: Calibration,
    latitude: float,
    longitude: float,
    wind_height_m: float = REFERENCE_HEIGHT_M,
) -> pd.DataFrame:
    """One row per station hour: the inputs used, the modelled temperatures, and the
    firmware's values. WBGT is missing wherever an input is."""
    hourly = hourly.reset_index(drop=True)
    ghi = ghi_hourly(hourly, calibration, latitude, longitude)["ghi_wm2"]
    inputs = pd.DataFrame(
        {
            "t_air_c": hourly["t_sht_c"],
            "rh_pct": hourly["rh_pct"],
            "p_station_hpa": hourly["p_station_hpa"],
            "wind_ms": hourly["wind_speed_ms"],
            "ghi_wm2": ghi,
        }
    )
    modelled = wbgt_for_hours(
        hourly["hour_utc"],
        inputs["t_air_c"],
        inputs["rh_pct"],
        inputs["p_station_hpa"],
        inputs["wind_ms"],
        inputs["ghi_wm2"],
        latitude,
        longitude,
        wind_height_m=wind_height_m,
    )
    return pd.concat(
        [
            modelled[["hour_utc"]],
            inputs,
            modelled.drop(columns="hour_utc"),
            hourly[FIRMWARE_COLUMNS],
        ],
        axis=1,
    )


def firmware_by_local_hour(table: pd.DataFrame, timezone: str) -> pd.DataFrame:
    """Firmware WBGT minus modelled WBGT, by local hour of day, over hours that have both."""
    rows = table.dropna(subset=["wbgt_c", "wbgt_fw_c"])
    local_hour = rows["hour_utc"].dt.tz_convert(timezone).dt.hour.rename("local_hour")
    difference = (rows["wbgt_fw_c"] - rows["wbgt_c"]).groupby(local_hour)
    summary = pd.DataFrame(
        {
            "n_hours": difference.size(),
            "wbgt_c": rows["wbgt_c"].groupby(local_hour).mean(),
            "wbgt_fw_c": rows["wbgt_fw_c"].groupby(local_hour).mean(),
            "fw_minus_model_c": difference.mean(),
            "fw_minus_model_min_c": difference.min(),
            "fw_minus_model_max_c": difference.max(),
        }
    )
    return summary.round(2).reset_index()


def mean_difference(by_hour: pd.DataFrame, hours: ArrayLike) -> float:
    """Firmware minus model over the given local hours, weighted by hours of data."""
    rows = by_hour[by_hour["local_hour"].isin(hours)]
    if rows.empty:
        return float("nan")
    return float(np.average(rows["fw_minus_model_c"], weights=rows["n_hours"]))
