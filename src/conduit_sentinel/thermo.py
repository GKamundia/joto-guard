"""Humidity and heat formulas used to check the firmware's derived columns."""

import numpy as np
from numpy.typing import ArrayLike


def stull_wet_bulb_c(t_c: ArrayLike, rh_pct: ArrayLike) -> np.ndarray:
    """Wet-bulb temperature from air temperature and relative humidity.

    Stull (2011), J. Appl. Meteor. Climatol. 50, 2267-2269. Fitted for RH 5 to 99 % and
    -20 to 50 °C at standard sea-level pressure.
    """
    t = np.asarray(t_c, dtype=float)
    rh = np.asarray(rh_pct, dtype=float)
    return (
        t * np.arctan(0.151977 * np.sqrt(rh + 8.313659))
        + np.arctan(t + rh)
        - np.arctan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * np.arctan(0.023101 * rh)
        - 4.686035
    )


def nws_heat_index_c(t_c: ArrayLike, rh_pct: ArrayLike) -> np.ndarray:
    """Heat index following the US National Weather Service algorithm.

    Steadman's simple formula comes first; when its average with the air temperature
    reaches 80 °F, the Rothfusz regression and its humidity adjustments are used instead.
    https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml
    """
    t = np.asarray(t_c, dtype=float) * 9 / 5 + 32
    rh = np.asarray(rh_pct, dtype=float)

    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    regression = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * rh
        - 0.22475541 * t * rh
        - 6.83783e-3 * t**2
        - 5.481717e-2 * rh**2
        + 1.22874e-3 * t**2 * rh
        + 8.5282e-4 * t * rh**2
        - 1.99e-6 * t**2 * rh**2
    )
    with np.errstate(invalid="ignore"):
        dry = (rh < 13) & (t >= 80) & (t <= 112)
        dry_adjustment = (13 - rh) / 4 * np.sqrt((17 - np.abs(t - 95)) / 17)
        regression = np.where(dry, regression - dry_adjustment, regression)
    humid = (rh > 85) & (t >= 80) & (t <= 87)
    regression = np.where(humid, regression + (rh - 85) / 10 * (87 - t) / 5, regression)

    heat_index_f = np.where((simple + t) / 2 >= 80, regression, simple)
    return (heat_index_f - 32) * 5 / 9
