"""Does the forecast get the level right, not just the temperature?

A mean absolute error in degrees says nothing about the decision a supervisor makes. What
matters is whether the level the forecast implies is the level the station turned out to
justify, and in particular how often the forecast said an hour was safer than it was. That
error, an under-warning, is the one that can hurt somebody; an over-warning only costs work.

Everything here is measured on days left out of the correction's fit, so none of it is
scored on data the correction had seen.
"""

from typing import Any

import numpy as np
import pandas as pd

from . import bands, bias

#: An hour counts as near a limit when the station's WBGT is within this of one.
NEAR_LIMIT_C = 1.0


def _rank(values: np.ndarray, work_type: str, guidance: bands.HeatGuidance) -> np.ndarray:
    """Each WBGT as its position in `bands.LEVELS`, so two levels can be compared."""
    levels = bands.levels(values, work_type, guidance)
    return np.array([bands.LEVELS.index(level) for level in levels])


def agreement(
    predicted: np.ndarray, station: np.ndarray, work_type: str, guidance: bands.HeatGuidance
) -> dict[str, Any]:
    """How the predicted level compares with the one the station justified."""
    said = _rank(predicted, work_type, guidance)
    was = _rank(station, work_type, guidance)
    return {
        "n_hours": len(said),
        "exact_pct": round(100 * float((said == was).mean()), 1),
        "under_warned_pct": round(100 * float((said < was).mean()), 1),
        "over_warned_pct": round(100 * float((said > was).mean()), 1),
        "worst_under_warning_levels": int(max(0, (was - said).max())),
    }


def verify(pairs: pd.DataFrame, guidance: bands.HeatGuidance) -> dict[str, Any]:
    """Error, level agreement and what the band's upper edge would change."""
    residuals = bias.held_out_residuals(pairs)
    _, high = bias.band_from_residuals(residuals)
    hours = residuals["local_hour"].to_numpy()
    upper = residuals["corrected_c"].to_numpy() + high[hours]
    station = residuals["station_c"].to_numpy()

    error = residuals["station_c"] - residuals["corrected_c"]
    by_hour = error.abs().groupby(residuals["local_hour"]).mean()
    limits = {name: guidance.acclimatized.at(rate) for name, rate in guidance.work_types.items()}
    near = {
        name: round(100 * float((np.abs(station - limit) <= NEAR_LIMIT_C).mean()), 1)
        for name, limit in limits.items()
    }

    return {
        "n_hours": len(residuals),
        "n_days": int(residuals["local_day"].nunique()),
        "error_c": {
            "mae": round(float(error.abs().mean()), 2),
            "rmse": round(float(np.sqrt((error**2).mean())), 2),
            "bias": round(float(error.mean()), 2),
            "p90_abs": round(float(error.abs().quantile(0.9)), 2),
            "worst_abs": round(float(error.abs().max()), 2),
        },
        "mae_by_local_hour_c": {
            str(hour): round(float(value), 2) for hour, value in by_hour.items()
        },
        "levels": {
            work_type: agreement(residuals["corrected_c"].to_numpy(), station, work_type, guidance)
            for work_type in guidance.work_types
        },
        "levels_from_band_top": {
            work_type: agreement(upper, station, work_type, guidance)
            for work_type in guidance.work_types
        },
        "hours_near_a_limit_pct": near,
    }
