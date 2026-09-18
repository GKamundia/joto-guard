"""Where the sun is: the cosine of the solar zenith angle at a place and time.

The equations are NOAA's solar calculator (after Meeus, Astronomical Algorithms), good to
a fraction of a degree, which is far finer than an hourly calibration needs.
"""

import numpy as np
import pandas as pd


def _sun(times: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Declination (radians), equation of time and UTC time of day (minutes), and the
    Earth-Sun distance (astronomical units)."""
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

    true_anomaly = mean_anomaly + np.radians(centre)
    distance = 1.000001018 * (1 - eccentricity**2) / (1 + eccentricity * np.cos(true_anomaly))
    return declination, equation_of_time, minutes, distance


def cos_zenith(times: pd.DatetimeIndex, latitude: float, longitude: float) -> np.ndarray:
    """Cosine of the solar zenith angle; negative when the sun is below the horizon."""
    declination, equation_of_time, minutes, _ = _sun(times)
    solar_minutes = (minutes + equation_of_time + 4 * longitude) % 1440
    hour_angle = np.radians(solar_minutes / 4 - 180)

    lat = np.radians(latitude)
    return np.sin(lat) * np.sin(declination) + np.cos(lat) * np.cos(declination) * np.cos(
        hour_angle
    )


def earth_sun_distance(times: pd.DatetimeIndex) -> np.ndarray:
    """Distance from the Earth to the Sun in astronomical units (0.983 to 1.017)."""
    return _sun(times)[3]


def _within_hours(
    hours: pd.DatetimeIndex, latitude: float, longitude: float, steps: int
) -> np.ndarray:
    """cos zenith at the middle of each of `steps` equal slices of every hour; one row per
    slice, one column per hour."""
    hours = pd.DatetimeIndex(hours)
    step = pd.Timedelta(hours=1) / steps
    return np.array(
        [cos_zenith(hours + step * (i + 0.5), latitude, longitude) for i in range(steps)]
    )


def hourly_mean_cos_zenith(
    hours: pd.DatetimeIndex, latitude: float, longitude: float, steps: int = 12
) -> np.ndarray:
    """Mean of max(cos zenith, 0) over each hour starting at `hours`.

    Averaging within the hour, rather than taking the value at half past, keeps the
    sunrise and sunset hours right: the sun is up for only part of them.
    """
    return np.clip(_within_hours(hours, latitude, longitude, steps), 0, None).mean(axis=0)


def hourly_sun(
    hours: pd.DatetimeIndex, latitude: float, longitude: float, steps: int = 60
) -> pd.DataFrame:
    """The sun over each hour starting at `hours`, as an hourly energy balance needs it.

    - `cos_zenith_hour`: mean of max(cos zenith, 0) over the whole hour. Sunlight at the
      top of the atmosphere, averaged the same way as an hourly mean irradiance.
    - `cos_zenith_sunlit`: mean cos zenith over only the part of the hour when the sun is
      up, 0 when it never is. The angle at which that hour's direct beam arrives: the
      midpoint's angle would put the sunset hour's sun below the horizon, or on it.
    - `earth_sun_distance_au`: at the middle of the hour.

    The sunlit mean follows Hogan and Hirahara (2016), as used for hourly WBGT by Kong and
    Huber (2022).
    """
    hours = pd.DatetimeIndex(hours)
    samples = _within_hours(hours, latitude, longitude, steps)
    sunlit = samples > 0
    sunlit_steps = sunlit.sum(axis=0)
    sunlit_total = np.where(sunlit, samples, 0.0).sum(axis=0)
    return pd.DataFrame(
        {
            "cos_zenith_hour": sunlit_total / steps,
            "cos_zenith_sunlit": np.divide(
                sunlit_total,
                sunlit_steps,
                out=np.zeros(len(hours)),
                where=sunlit_steps > 0,
            ),
            "earth_sun_distance_au": earth_sun_distance(hours + pd.Timedelta(minutes=30)),
        }
    )
