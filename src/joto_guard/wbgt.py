# The heat-balance equations, constants and property correlations below follow
# WBGT version 1.1 by James C. Liljegren, distributed under this notice:
#
#     Copyright © 2008, UChicago Argonne, LLC
#     All Rights Reserved
#
#     WBGT, Version 1.1
#
#     James C. Liljegren
#     Decision & Information Sciences Division
#
#     OPEN SOURCE LICENSE
#
#     Redistribution and use in source and binary forms, with or without modification,
#     are permitted provided that the following conditions are met:
#
#     1. Redistributions of source code must retain the above copyright notice, this
#        list of conditions and the following disclaimer. Software changes,
#        modifications, or derivative works, should be noted with comments and the
#        author and organization's name.
#     2. Redistributions in binary form must reproduce the above copyright notice, this
#        list of conditions and the following disclaimer in the documentation and/or
#        other materials provided with the distribution.
#     3. Neither the names of UChicago Argonne, LLC or the Department of Energy nor the
#        names of its contributors may be used to endorse or promote products derived
#        from this software without specific prior written permission.
#     4. The software and the end-user documentation included with the redistribution,
#        if any, must include the following acknowledgment:
#
#        "This product includes software produced by UChicago Argonne, LLC under
#        Contract No. DE-AC02-06CH11357 with the Department of Energy."
#
#     DISCLAIMER
#
#     THE SOFTWARE IS SUPPLIED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#
#     NEITHER THE UNITED STATES GOVERNMENT, NOR THE UNITED STATES DEPARTMENT OF ENERGY,
#     NOR UCHICAGO ARGONNE, LLC, NOR ANY OF THEIR EMPLOYEES, MAKES ANY WARRANTY, EXPRESS
#     OR IMPLIED, OR ASSUMES ANY LEGAL LIABILITY OR RESPONSIBILITY FOR THE ACCURACY,
#     COMPLETENESS, OR USEFULNESS OF ANY INFORMATION, DATA, APPARATUS, PRODUCT, OR
#     PROCESS DISCLOSED, OR REPRESENTS THAT ITS USE WOULD NOT INFRINGE PRIVATELY OWNED
#     RIGHTS.
#
# Changes, September 2026, GKamundia for Joto Guard (Hack The Weather 2026 entry):
# rewritten in Python and numpy to work on whole arrays; the globe and wick balances are
# solved by bisection instead of relaxed fixed-point iteration; for hourly inputs the
# top-of-atmosphere irradiance and the sun angle are averaged over the hour (see
# `wbgt_for_hours`); the sun's position comes from `solar.py` (NOAA equations).

"""Wet bulb globe temperature from standard weather measurements (Liljegren et al. 2008).

    WBGT = 0.7 × natural wet bulb + 0.2 × globe temperature + 0.1 × air temperature

A weather station measures neither the natural wet bulb (a wet wick in the open air,
warmed by the sun and cooled by evaporation) nor the globe temperature (a black sphere in
the sun). Both are modelled here from air temperature, humidity, pressure, wind speed and
solar irradiance: each is the temperature at which the heat the globe or wick gains from
sunlight and the sky balances the heat it loses to the air.

The original solves each balance by relaxed fixed-point iteration to 0.02 K. Bisection on
the same balance always converges and finds the root to far better than that, so results
agree with the original to within its own tolerance.

Reference: Liljegren, J. C., Carhart, R. A., Lawday, P., Tschopp, S. and Sharp, R. (2008).
Modeling the wet bulb globe temperature using standard meteorological measurements.
Journal of Occupational and Environmental Hygiene 5(10), 645-655.
https://doi.org/10.1080/15459620802310770
"""

from collections.abc import Callable

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from .solar import hourly_sun

SOLAR_CONSTANT = 1367.0  # W/m²
STEFAN_BOLTZMANN = 5.6696e-8  # W/(m² K⁴)
CP_AIR = 1003.5  # J/(kg K)
M_AIR = 28.97  # g/mol
M_H2O = 18.015
R_AIR = 8314.34 / M_AIR  # J/(kg K)
RATIO = CP_AIR * M_AIR / M_H2O
PRANDTL = CP_AIR / (CP_AIR + 1.25 * R_AIR)

WICK_EMISSIVITY = 0.95
WICK_ALBEDO = 0.4
WICK_DIAMETER = 0.007  # m
WICK_LENGTH = 0.0254  # m
GLOBE_EMISSIVITY = 0.95
GLOBE_ALBEDO = 0.05
GLOBE_DIAMETER = 0.0508  # m, the standard 2-inch globe
SURFACE_EMISSIVITY = 0.999
SURFACE_ALBEDO = 0.45

# Below this cos zenith the sun is not clear of the horizon and all sunlight counts as diffuse.
MIN_COS_ZENITH = 0.00873
# Surface irradiance above this share of the top-of-atmosphere value is taken as a sensor error.
MAX_CLEARNESS = 0.85
REFERENCE_HEIGHT_M = 2.0
MIN_WIND_MS = 0.13

# Wind-profile exponents by stability class 1 (very unstable) to 6 (stable).
URBAN_EXPONENTS = np.array([0.15, 0.15, 0.20, 0.25, 0.30, 0.30])
RURAL_EXPONENTS = np.array([0.07, 0.07, 0.10, 0.15, 0.35, 0.55])

OUTPUT_COLUMNS = ["tg_c", "tnwb_c", "tpsy_c", "wbgt_c"]


def saturation_vapour_pressure(t_k: ArrayLike) -> np.ndarray:
    """Over liquid water, hPa: Buck (1981), times 1.004 for moist air above 800 hPa."""
    t_k = np.asarray(t_k, dtype=float)
    return 1.004 * 6.1121 * np.exp(17.502 * (t_k - 273.15) / (t_k - 32.18))


def _viscosity(t_k: np.ndarray) -> np.ndarray:
    """Of air, kg/(m s)."""
    omega = (t_k / 97.0 - 2.9) / 0.4 * -0.034 + 1.048
    return 2.6693e-6 * np.sqrt(M_AIR * t_k) / (3.617**2 * omega)


def _conductivity(t_k: np.ndarray) -> np.ndarray:
    """Of air, W/(m K)."""
    return (CP_AIR + 1.25 * R_AIR) * _viscosity(t_k)


def _diffusivity(t_k: np.ndarray, p_hpa: np.ndarray) -> np.ndarray:
    """Of water vapour in air, m²/s."""
    critical = (
        (36.4 * 218.0) ** (1 / 3) * (132.0 * 647.3) ** (5 / 12) * np.sqrt(1 / M_AIR + 1 / M_H2O)
    )
    return 3.640e-4 * (t_k / np.sqrt(132.0 * 647.3)) ** 2.334 * critical / (p_hpa / 1013.25) * 1e-4


def _latent_heat(t_k: np.ndarray) -> np.ndarray:
    """Of evaporation, J/kg."""
    return (313.15 - t_k) / 30.0 * -71100.0 + 2.4073e6


def _density(t_k: np.ndarray, p_hpa: np.ndarray) -> np.ndarray:
    return p_hpa * 100.0 / (R_AIR * t_k)


def _sky_emissivity(t_k: np.ndarray, rh: np.ndarray) -> np.ndarray:
    return 0.575 * (rh * saturation_vapour_pressure(t_k)) ** 0.143


def _reynolds(diameter: float, t_k: np.ndarray, p_hpa: np.ndarray, wind: np.ndarray):
    return np.maximum(wind, MIN_WIND_MS) * _density(t_k, p_hpa) * diameter / _viscosity(t_k)


def _globe_convection(t_k: np.ndarray, p_hpa: np.ndarray, wind: np.ndarray) -> np.ndarray:
    """Heat transfer coefficient of a sphere, W/(m² K)."""
    nusselt = 2.0 + 0.6 * np.sqrt(_reynolds(GLOBE_DIAMETER, t_k, p_hpa, wind)) * PRANDTL**0.3333
    return nusselt * _conductivity(t_k) / GLOBE_DIAMETER


def _wick_convection(t_k: np.ndarray, p_hpa: np.ndarray, wind: np.ndarray) -> np.ndarray:
    """Heat transfer coefficient of a cylinder in cross flow, W/(m² K)."""
    nusselt = 0.281 * _reynolds(WICK_DIAMETER, t_k, p_hpa, wind) ** 0.6 * PRANDTL**0.44
    return nusselt * _conductivity(t_k) / WICK_DIAMETER


def _bisect(
    residual: Callable[[np.ndarray], np.ndarray],
    low: np.ndarray,
    high: np.ndarray,
    iterations: int = 48,
) -> np.ndarray:
    """Root of an increasing function between `low` and `high`, element by element.

    NaN wherever the bracket holds no root, which includes any missing input.
    """
    low, high = low.astype(float), high.astype(float)
    bracketed = (residual(low) <= 0) & (residual(high) >= 0)
    for _ in range(iterations):
        middle = 0.5 * (low + high)
        above = residual(middle) > 0
        high = np.where(above, middle, high)
        low = np.where(above, low, middle)
    return np.where(bracketed, 0.5 * (low + high), np.nan)


def direct_beam(solar_wm2: ArrayLike, toa_wm2: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    """Irradiance capped at 85 % of the top-of-atmosphere value, and its direct-beam share.

    The share rises with the clearness of the sky (surface over top-of-atmosphere
    irradiance) and stays within 0 to 0.9. Where the top-of-atmosphere value is zero the
    irradiance is kept as it is and treated as all diffuse.
    """
    solar = np.asarray(solar_wm2, dtype=float)
    toa = np.asarray(toa_wm2, dtype=float)
    sun_up = toa > 0
    clearness = np.where(sun_up, np.minimum(solar / np.where(sun_up, toa, 1.0), MAX_CLEARNESS), 0)
    capped = np.where(sun_up, clearness * toa, solar)
    positive = clearness > 0
    share = np.exp(3 - 1.34 * clearness - 1.65 / np.where(positive, clearness, 1.0))
    return capped, np.where(positive, np.clip(share, 0, 0.9), 0.0)


def globe_temperature(
    t_air_k: np.ndarray,
    rh: np.ndarray,
    p_hpa: np.ndarray,
    wind: np.ndarray,
    solar: np.ndarray,
    fdir: np.ndarray,
    cos_zenith: np.ndarray,
) -> np.ndarray:
    """Black globe temperature, K.

    Balance: the globe emits σT⁴ and loses h(T − Ta) to the air; it absorbs half the sky's
    and half the ground's long-wave radiation, the diffuse and ground-reflected sunlight,
    and the direct beam on its cross-section.
    """
    long_wave = 0.5 * (_sky_emissivity(t_air_k, rh) + SURFACE_EMISSIVITY) * t_air_k**4
    beam = np.where(fdir > 0, fdir * (1 / (2 * np.where(fdir > 0, cos_zenith, 1.0)) - 1), 0.0)
    short_wave = (
        solar
        / (2 * STEFAN_BOLTZMANN * GLOBE_EMISSIVITY)
        * (1 - GLOBE_ALBEDO)
        * (beam + 1 + SURFACE_ALBEDO)
    )
    gained = long_wave + short_wave

    def residual(t_globe: np.ndarray) -> np.ndarray:
        h = _globe_convection(0.5 * (t_globe + t_air_k), p_hpa, wind)
        return t_globe**4 + h / (STEFAN_BOLTZMANN * GLOBE_EMISSIVITY) * (t_globe - t_air_k) - gained

    return _bisect(residual, t_air_k - 60, t_air_k + 100)


def wet_bulb_temperature(
    t_air_k: np.ndarray,
    rh: np.ndarray,
    p_hpa: np.ndarray,
    wind: np.ndarray,
    solar: np.ndarray,
    fdir: np.ndarray,
    cos_zenith: np.ndarray,
    radiative: bool = True,
) -> np.ndarray:
    """Wet-wick temperature, K: the natural wet bulb, or with `radiative=False` the
    psychrometric wet bulb (the same wick, shaded and exchanging no radiation).

    Balance: evaporation cools the wick below the air; convection from the air and, for
    the natural wet bulb, sunlight and long-wave radiation warm it.
    """
    e_air = rh * saturation_vapour_pressure(t_air_k)
    shape = 0.25 * WICK_DIAMETER / WICK_LENGTH
    tan_zenith = np.where(fdir > 0, np.tan(np.arccos(np.where(fdir > 0, cos_zenith, 1.0))), 0.0)
    sunlight = (
        (1 - WICK_ALBEDO)
        * solar
        * ((1 - fdir) * (1 + shape) + fdir * (tan_zenith / np.pi + shape) + SURFACE_ALBEDO)
    )
    sky_and_ground = (
        STEFAN_BOLTZMANN
        * WICK_EMISSIVITY
        * 0.5
        * (_sky_emissivity(t_air_k, rh) + SURFACE_EMISSIVITY)
        * t_air_k**4
    )

    def residual(t_wick: np.ndarray) -> np.ndarray:
        t_film = 0.5 * (t_wick + t_air_k)
        e_wick = saturation_vapour_pressure(t_wick)
        schmidt = _viscosity(t_film) / (_density(t_film, p_hpa) * _diffusivity(t_film, p_hpa))
        cooling = (
            _latent_heat(t_film)
            / RATIO
            * (e_wick - e_air)
            / (p_hpa - e_wick)
            * (PRANDTL / schmidt) ** 0.56
        )
        warming = 0.0
        if radiative:
            absorbed = sky_and_ground - STEFAN_BOLTZMANN * WICK_EMISSIVITY * t_wick**4 + sunlight
            warming = absorbed / _wick_convection(t_film, p_hpa, wind)
        return t_wick - (t_air_k - cooling + warming)

    return _bisect(residual, t_air_k - 60, t_air_k + 40)


def liljegren(
    air_temp_c: ArrayLike,
    rh_pct: ArrayLike,
    pressure_hpa: ArrayLike,
    wind_ms: ArrayLike,
    solar_wm2: ArrayLike,
    fdir: ArrayLike,
    cos_zenith: ArrayLike,
) -> pd.DataFrame:
    """Globe, natural wet bulb, psychrometric wet bulb and WBGT, all in °C.

    `solar_wm2` and `fdir` are the capped irradiance and its direct-beam share from
    `direct_beam`; `wind_ms` is at 2 m. A missing input gives missing outputs for that row.
    """
    t_air_k, rh, p_hpa, wind, solar, beam, cza = (
        np.atleast_1d(np.asarray(values, dtype=float))
        for values in (air_temp_c, rh_pct, pressure_hpa, wind_ms, solar_wm2, fdir, cos_zenith)
    )
    t_air_k = t_air_k + 273.15
    rh = np.clip(rh, 0, 100) / 100
    t_air_k, rh, p_hpa, wind, solar, beam, cza = np.broadcast_arrays(
        t_air_k, rh, p_hpa, wind, solar, beam, cza
    )

    inputs = (t_air_k, rh, p_hpa, wind, solar, beam, cza)
    t_globe = globe_temperature(*inputs) - 273.15
    t_nwb = wet_bulb_temperature(*inputs) - 273.15
    t_psy = wet_bulb_temperature(*inputs, radiative=False) - 273.15
    return pd.DataFrame(
        {
            "tg_c": t_globe,
            "tnwb_c": t_nwb,
            "tpsy_c": t_psy,
            "wbgt_c": 0.1 * (t_air_k - 273.15) + 0.2 * t_globe + 0.7 * t_nwb,
        }
    )


def stability_class(
    daytime: ArrayLike, wind_ms: ArrayLike, solar_wm2: ArrayLike, delta_t_c: ArrayLike = 0.0
) -> np.ndarray:
    """Pasquill-Gifford stability class, 1 (very unstable) to 6 (stable).

    By day from wind speed and solar irradiance; by night from wind speed and the vertical
    temperature difference (upper minus lower, °C), taken as 0 when it is not measured.
    Method: US EPA (2000), Meteorological Monitoring Guidance for Regulatory Modeling
    Applications, section 6.2.5.
    """
    daytime, wind, solar, delta_t = np.broadcast_arrays(
        np.asarray(daytime, dtype=bool),
        np.asarray(wind_ms, dtype=float),
        np.asarray(solar_wm2, dtype=float),
        np.asarray(delta_t_c, dtype=float),
    )
    day_table = np.array([[1, 1, 2, 4], [1, 2, 3, 4], [2, 2, 3, 4], [3, 3, 4, 4], [3, 4, 4, 4]])
    day_row = np.digitize(wind, [2.0, 3.0, 5.0, 6.0])
    day_column = 3 - np.digitize(solar, [175.0, 675.0, 925.0])
    night_table = np.array([[5, 6], [5, 6], [4, 4]])
    night_row = np.digitize(wind, [2.0, 2.5])
    night_column = (delta_t >= 0).astype(int)
    return np.where(
        daytime, day_table[day_row, day_column], night_table[night_row, night_column]
    ).astype(int)


def wind_at_reference_height(
    wind_ms: ArrayLike, height_m: float, stability: ArrayLike, urban: bool = False
) -> np.ndarray:
    """Wind speed at 2 m from a measurement at `height_m`, by a stability-dependent power law."""
    wind = np.asarray(wind_ms, dtype=float)
    if height_m == REFERENCE_HEIGHT_M:
        return wind
    exponents = (URBAN_EXPONENTS if urban else RURAL_EXPONENTS)[np.asarray(stability) - 1]
    return np.maximum(wind * (REFERENCE_HEIGHT_M / height_m) ** exponents, MIN_WIND_MS)


def wbgt_for_hours(
    hours: ArrayLike,
    air_temp_c: ArrayLike,
    rh_pct: ArrayLike,
    pressure_hpa: ArrayLike,
    wind_ms: ArrayLike,
    ghi_wm2: ArrayLike,
    latitude: float,
    longitude: float,
    wind_height_m: float = REFERENCE_HEIGHT_M,
    urban: bool = False,
) -> pd.DataFrame:
    """WBGT for hourly mean inputs, one row per hour starting at `hours`.

    The inputs are hour averages, so the sun is too. The top-of-atmosphere irradiance that
    GHI is compared with is the hour's mean, which keeps the sunrise and sunset hours from
    being read as unusually clear or dull; the direct beam arrives at the hour's mean sun
    angle while the sun is up. The original instead takes the sun angle at the middle of
    the averaging period, which puts the sunset hour's sun on or below the horizon.
    """
    hours = pd.DatetimeIndex(pd.to_datetime(hours, utc=True))
    sun = hourly_sun(hours, latitude, longitude)
    cza = sun["cos_zenith_sunlit"].to_numpy()
    toa = SOLAR_CONSTANT * sun["cos_zenith_hour"] / sun["earth_sun_distance_au"] ** 2
    toa = np.where(cza >= MIN_COS_ZENITH, toa, 0.0)
    solar, fdir = direct_beam(ghi_wm2, toa)

    wind = np.asarray(wind_ms, dtype=float)
    stability = stability_class(cza > 0, wind, solar)
    wind_2m = wind_at_reference_height(wind, wind_height_m, stability, urban)

    result = liljegren(air_temp_c, rh_pct, pressure_hpa, wind_2m, solar, fdir, cza)
    return pd.concat(
        [
            pd.DataFrame(
                {
                    "hour_utc": hours,
                    "cos_zenith": np.round(cza, 4),
                    "solar_wm2": np.round(solar, 1),
                    "fdir": np.round(fdir, 3),
                    "wind_2m_ms": np.round(wind_2m, 2),
                }
            ),
            result.round(2),
        ],
        axis=1,
    )
