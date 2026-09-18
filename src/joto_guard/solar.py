"""Where the sun is: the cosine of the solar zenith angle at a place and time.

The equations are NOAA's solar calculator (after Meeus, Astronomical Algorithms), good to
a fraction of a degree, which is far finer than an hourly calibration needs.
"""

import numpy as np
import pandas as pd


def cos_zenith(times: pd.DatetimeIndex, latitude: float, longitude: float) -> np.ndarray:
    """Cosine of the solar zenith angle; negative when the sun is below the horizon."""
    times = pd.DatetimeIndex(times)
    if times.tz is not None:
        times = times.tz_convert("UTC")
    century = (times.to_julian_date().to_numpy() - 2451545.0) / 36525.0

    mean_longitude = np.radians((280.46646 + century * (36000.76983 + century * 0.0003032)) % 360)
    mean_anomaly = np.radians(357.52911 + century * (35999.05029 - 0.0001537 * century))
    eccentricity = 0.016708634 - century * (0.000042037 + 0.0000001267 * century)
    centre = (
        np.sin(mean_anomaly) * (1.914602 - century * (0.004817 + 0.000014 * century))
        + np.sin(2 * mean_anomaly) * (0.019993 - 0.000101 * century)
        + np.sin(3 * mean_anomaly) * 0.000289
    )
    omega = np.radians(125.04 - 1934.136 * century)
    apparent_longitude = np.radians(
        np.degrees(mean_longitude) + centre - 0.00569 - 0.00478 * np.sin(omega)
    )
    obliquity = np.radians(
        23
        + (26 + (21.448 - century * (46.815 + century * (0.00059 - century * 0.001813))) / 60) / 60
        + 0.00256 * np.cos(omega)
    )
    declination = np.arcsin(np.sin(obliquity) * np.sin(apparent_longitude))

    y = np.tan(obliquity / 2) ** 2
    equation_of_time = 4 * np.degrees(
        y * np.sin(2 * mean_longitude)
        - 2 * eccentricity * np.sin(mean_anomaly)
        + 4 * eccentricity * y * np.sin(mean_anomaly) * np.cos(2 * mean_longitude)
        - 0.5 * y * y * np.sin(4 * mean_longitude)
        - 1.25 * eccentricity * eccentricity * np.sin(2 * mean_anomaly)
    )
    minutes = (times.hour * 60 + times.minute + times.second / 60).to_numpy()
    solar_minutes = (minutes + equation_of_time + 4 * longitude) % 1440
    hour_angle = np.radians(solar_minutes / 4 - 180)

    lat = np.radians(latitude)
    return np.sin(lat) * np.sin(declination) + np.cos(lat) * np.cos(declination) * np.cos(
        hour_angle
    )


def hourly_mean_cos_zenith(
    hours: pd.DatetimeIndex, latitude: float, longitude: float, steps: int = 12
) -> np.ndarray:
    """Mean of max(cos zenith, 0) over each hour starting at `hours`.

    Averaging within the hour, rather than taking the value at half past, keeps the
    sunrise and sunset hours right: the sun is up for only part of them.
    """
    hours = pd.DatetimeIndex(hours)
    step = pd.Timedelta(hours=1) / steps
    samples = [
        np.clip(cos_zenith(hours + step * (i + 0.5), latitude, longitude), 0, None)
        for i in range(steps)
    ]
    return np.mean(samples, axis=0)
