"""Correcting the WBGT forecast towards the station, by hour of day.

The raw forecast's error against the station follows the clock rather than the lead
time (decision 0009): it reads about 2 °C low at midday and is close at night. The
correction adds, for each local hour, the mean difference between the station and the
forecasts made for that hour 0 to 3 days ahead. Separate offsets for each lead time did
no better on days left out of the fit, so one set serves every lead.

The band around a corrected value spans the 10th to 90th percentile of the corrected
forecast's error at that hour and its two neighbours, on days left out of the fit.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LOW_QUANTILE = 0.1
HIGH_QUANTILE = 0.9
# The band at each hour pools the errors of this many hours either side of it.
BAND_WINDOW_H = 1
# Local hours reported separately, when heat stress matters most.
MIDDAY_HOURS = range(10, 16)

PAIR_COLUMNS = ["hour_utc", "lead_day", "local_day", "local_hour", "station_c", "forecast_c"]


@dataclass(frozen=True)
class Correction:
    model: str
    timezone: str
    offsets_c: tuple[float, ...]
    band_low_c: tuple[float, ...]
    band_high_c: tuple[float, ...]
    first_day: str
    last_day: str
    n_days: int
    n_pairs: int
    held_out: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": "WBGT + offset for the local hour; band from errors on days left out",
            "model": self.model,
            "timezone": self.timezone,
            "offsets_c": list(self.offsets_c),
            "band_low_c": list(self.band_low_c),
            "band_high_c": list(self.band_high_c),
            "first_day": self.first_day,
            "last_day": self.last_day,
            "n_days": self.n_days,
            "n_pairs": self.n_pairs,
            "held_out": self.held_out,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Correction":
        values = {key: value for key, value in data.items() if key != "method"}
        for key in ("offsets_c", "band_low_c", "band_high_c"):
            values[key] = tuple(values[key])
        return cls(**values)


def pair_forecasts(
    station: pd.DataFrame, forecasts: Mapping[int, pd.DataFrame], timezone: str
) -> pd.DataFrame:
    """One row per station hour and lead day with both WBGT values.

    `station` and each forecast need `hour_utc` and `wbgt_c`; forecasts are keyed by how
    many days before the hour they were made. Hours missing either value are dropped.
    """
    observed = station[["hour_utc", "wbgt_c"]].rename(columns={"wbgt_c": "station_c"})
    frames = []
    for lead_day, forecast in sorted(forecasts.items()):
        predicted = forecast[["hour_utc", "wbgt_c"]].rename(columns={"wbgt_c": "forecast_c"})
        frames.append(observed.merge(predicted, on="hour_utc").assign(lead_day=lead_day))
    pairs = pd.concat(frames, ignore_index=True).dropna(subset=["station_c", "forecast_c"])
    local = pd.to_datetime(pairs["hour_utc"], utc=True).dt.tz_convert(timezone)
    pairs["local_day"] = local.dt.date
    pairs["local_hour"] = local.dt.hour
    return pairs[PAIR_COLUMNS].reset_index(drop=True)


def hourly_offsets(pairs: pd.DataFrame) -> np.ndarray:
    """Mean of station minus forecast at each local hour, 0 to 23."""
    offsets = (pairs["station_c"] - pairs["forecast_c"]).groupby(pairs["local_hour"]).mean()
    missing = sorted(set(range(24)) - set(offsets.index))
    if missing:
        raise ValueError(f"no forecast and station pairs at local hours {missing}")
    return offsets.sort_index().to_numpy()


def held_out_residuals(pairs: pd.DataFrame) -> pd.DataFrame:
    """Each day's pairs corrected with offsets fitted on the other days.

    Adds `corrected_c`, the corrected forecast; `residual_c`, the station minus it; and
    `climatology_c`, the station's mean WBGT at that hour on the other days, which is the
    forecast to beat.
    """
    days = []
    for day in sorted(pairs["local_day"].unique()):
        train, test = pairs[pairs["local_day"] != day], pairs[pairs["local_day"] == day]
        offsets = hourly_offsets(train)
        usual = train.drop_duplicates("hour_utc").groupby("local_hour")["station_c"].mean()
        test = test.assign(
            corrected_c=test["forecast_c"] + offsets[test["local_hour"]],
            climatology_c=usual.reindex(test["local_hour"]).to_numpy(),
        )
        days.append(test.assign(residual_c=test["station_c"] - test["corrected_c"]))
    return pd.concat(days, ignore_index=True)


def band_from_residuals(
    residuals: pd.DataFrame, window_h: int = BAND_WINDOW_H
) -> tuple[np.ndarray, np.ndarray]:
    """Low and high quantiles of the residuals at each local hour and its neighbours."""
    low, high = np.empty(24), np.empty(24)
    for hour in range(24):
        near = {(hour + step) % 24 for step in range(-window_h, window_h + 1)}
        values = residuals.loc[residuals["local_hour"].isin(near), "residual_c"]
        low[hour], high[hour] = values.quantile([LOW_QUANTILE, HIGH_QUANTILE])
    return low, high


def _errors(predicted: pd.Series, observed: pd.Series) -> dict[str, float]:
    difference = predicted - observed
    return {
        "mae_c": round(float(difference.abs().mean()), 2),
        "bias_c": round(float(difference.mean()), 2),
    }


def evaluate(pairs: pd.DataFrame) -> dict[str, Any]:
    """Skill on days left out of the fit: raw, corrected and the station's usual value,
    over all pairs, at midday and by lead day, and how often the band held the station
    value."""
    residuals = held_out_residuals(pairs)

    def skill(rows: pd.DataFrame) -> dict[str, Any]:
        return {
            "n_pairs": len(rows),
            "raw": _errors(rows["forecast_c"], rows["station_c"]),
            "corrected": _errors(rows["corrected_c"], rows["station_c"]),
            "station_usual": _errors(rows["climatology_c"], rows["station_c"]),
        }

    inside = []
    for day in sorted(pairs["local_day"].unique()):
        train = pairs[pairs["local_day"] != day]
        low, high = band_from_residuals(held_out_residuals(train))
        test = residuals[residuals["local_day"] == day]
        hours = test["local_hour"].to_numpy()
        inside.append((test["residual_c"] >= low[hours]) & (test["residual_c"] <= high[hours]))

    midday = residuals["local_hour"].isin(MIDDAY_HOURS)
    return {
        "all": skill(residuals),
        "midday": skill(residuals[midday]),
        "by_lead_day": {str(lead): skill(rows) for lead, rows in residuals.groupby("lead_day")},
        "band_held_station_pct": round(100 * float(pd.concat(inside).mean()), 1),
    }


def fit(pairs: pd.DataFrame, model: str, timezone: str) -> Correction:
    if pairs["local_day"].nunique() < 3:
        raise ValueError("the correction needs at least three days of forecasts and station data")
    low, high = band_from_residuals(held_out_residuals(pairs))
    return Correction(
        model=model,
        timezone=timezone,
        offsets_c=tuple(round(float(v), 2) for v in hourly_offsets(pairs)),
        band_low_c=tuple(round(float(v), 2) for v in low),
        band_high_c=tuple(round(float(v), 2) for v in high),
        first_day=str(min(pairs["local_day"])),
        last_day=str(max(pairs["local_day"])),
        n_days=int(pairs["local_day"].nunique()),
        n_pairs=len(pairs),
        held_out=evaluate(pairs),
    )


def apply(table: pd.DataFrame, correction: Correction) -> pd.DataFrame:
    """Add the corrected WBGT and its band to a forecast table with `hour_utc` and `wbgt_c`."""
    hours = (
        pd.to_datetime(table["hour_utc"], utc=True).dt.tz_convert(correction.timezone).dt.hour
    ).to_numpy()
    corrected = table["wbgt_c"].to_numpy() + np.asarray(correction.offsets_c)[hours]
    return table.assign(
        wbgt_corrected_c=np.round(corrected, 2),
        wbgt_low_c=np.round(corrected + np.asarray(correction.band_low_c)[hours], 2),
        wbgt_high_c=np.round(corrected + np.asarray(correction.band_high_c)[hours], 2),
    )


def save(correction: Correction, path: str | Path) -> None:
    Path(path).write_text(json.dumps(correction.to_dict(), indent=2) + "\n", encoding="utf-8")


def load(path: str | Path) -> Correction:
    return Correction.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
