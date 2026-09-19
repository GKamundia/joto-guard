"""Heat limits and work/rest advice by type of work (NIOSH 2016; decision 0011).

NIOSH sets two WBGT limits for each metabolic rate M, in W, both applying to 1-hour
averages of WBGT and of M:

- workers acclimatized to heat (the REL): 56.7 − 11.5 log10 M
- workers not yet acclimatized (the RAL): 59.9 − 14.1 log10 M

Rest lowers the hour's average metabolic rate, which is how a work/rest schedule lets work
go on at a higher WBGT. For each hour this module finds the longest spell of work in the
hour (60, 45, 30 or 15 minutes, as in NIOSH's figures) that keeps the hourly average
within the limit, taking the rest to be in the same heat.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from numpy.typing import ArrayLike

EPS = 1e-9

# From least to most restrictive.
LEVELS = ("normal", "acclimatized_only", "work_rest", "reschedule")
LEVEL_TEXT = {
    "normal": "Normal work, for new workers too.",
    "acclimatized_only": "Only workers used to the heat should work without breaks.",
    "work_rest": "Work in spells with rest in the shade.",
    "reschedule": "Too hot for this work: move it to a cooler hour.",
}

BY_HOUR_COLUMNS = [
    "hour_utc",
    "work_type",
    "wbgt_c",
    "level",
    "level_if_high",
    "work_minutes_acclimatized",
    "work_minutes_new_workers",
]


@dataclass(frozen=True)
class Limit:
    intercept_c: float
    slope_c: float

    def at(self, metabolic_rate_w: ArrayLike) -> np.ndarray:
        """The WBGT limit, °C, at a metabolic rate in W."""
        return self.intercept_c - self.slope_c * np.log10(np.asarray(metabolic_rate_w, float))


@dataclass(frozen=True)
class HeatGuidance:
    acclimatized: Limit
    new_workers: Limit
    work_types: dict[str, float]
    rest_metabolic_rate_w: float
    work_minutes_per_hour: tuple[int, ...]
    examples: dict[str, tuple[str, ...]]
    advice: dict[str, str]
    swahili: dict[str, dict[str, str]]


def load_guidance(path: str | Path) -> HeatGuidance:
    with open(path, encoding="utf-8") as fh:
        return guidance_from_dict(yaml.safe_load(fh))


def guidance_from_dict(data: Mapping[str, Any]) -> HeatGuidance:
    limits = data["limits"]
    guidance = HeatGuidance(
        acclimatized=Limit(**limits["acclimatized"]),
        new_workers=Limit(**limits["new_workers"]),
        work_types={name: float(rate) for name, rate in data["work_types"].items()},
        rest_metabolic_rate_w=float(data["rest_metabolic_rate_w"]),
        work_minutes_per_hour=tuple(int(m) for m in data["work_minutes_per_hour"]),
        examples={name: tuple(items) for name, items in data.get("examples", {}).items()},
        advice=dict(data.get("advice", {})),
        swahili={part: dict(strings) for part, strings in data.get("swahili", {}).items()},
    )
    if not guidance.work_types or min(guidance.work_types.values()) <= 0:
        raise ValueError("every work type needs a positive metabolic rate")
    if 60 not in guidance.work_minutes_per_hour or not all(
        0 < m <= 60 for m in guidance.work_minutes_per_hour
    ):
        raise ValueError("work minutes per hour must lie in 1 to 60 and include 60")
    unknown = sorted(set(guidance.examples) - set(guidance.work_types))
    if unknown:
        raise ValueError(f"examples for unknown work types: {', '.join(unknown)}")
    _check_swahili(guidance)
    return guidance


def _check_swahili(guidance: HeatGuidance) -> None:
    """Every English string a reader can be shown needs its Kiswahili twin, or none do."""
    if not guidance.swahili:
        return
    expected = {
        "work_types": set(guidance.work_types),
        "levels": set(LEVELS),
        "advice": set(guidance.advice),
    }
    for part, keys in expected.items():
        missing = sorted(keys - set(guidance.swahili.get(part, {})))
        if missing:
            raise ValueError(f"no Kiswahili for {part}: {', '.join(missing)}")


def hourly_rate_w(work_w: float, work_minutes: float, rest_w: float) -> float:
    """The hour's average metabolic rate when `work_minutes` of it are work and the rest is rest."""
    return (work_minutes * work_w + (60 - work_minutes) * rest_w) / 60


def allowed_minutes(
    wbgt_c: ArrayLike, work_w: float, limit: Limit, guidance: HeatGuidance
) -> np.ndarray:
    """The longest spell of work in each hour whose hourly average stays within `limit`:
    one of the configured minutes per hour, 0 if none is, NaN if WBGT is missing."""
    wbgt = np.atleast_1d(np.asarray(wbgt_c, dtype=float))
    minutes = np.zeros(len(wbgt))
    for spell in sorted(guidance.work_minutes_per_hour):
        rate = hourly_rate_w(work_w, spell, guidance.rest_metabolic_rate_w)
        minutes = np.where(wbgt <= limit.at(rate) + EPS, spell, minutes)
    return np.where(np.isnan(wbgt), np.nan, minutes)


def levels(wbgt_c: ArrayLike, work_type: str, guidance: HeatGuidance) -> np.ndarray:
    """One of LEVELS for each hour, or None where WBGT is missing."""
    wbgt = np.atleast_1d(np.asarray(wbgt_c, dtype=float))
    work_w = guidance.work_types[work_type]
    new = allowed_minutes(wbgt, work_w, guidance.new_workers, guidance)
    used_to_heat = allowed_minutes(wbgt, work_w, guidance.acclimatized, guidance)
    return np.select(
        [np.isnan(wbgt), new == 60, used_to_heat == 60, used_to_heat > 0],
        [None, "normal", "acclimatized_only", "work_rest"],
        default="reschedule",
    )


def guidance_by_hour(
    table: pd.DataFrame,
    guidance: HeatGuidance,
    value: str = "wbgt_corrected_c",
    high: str | None = "wbgt_high_c",
) -> pd.DataFrame:
    """One row per hour and work type. `level_if_high` is the level at the top of the
    uncertainty band, when the table has one."""
    frames = []
    for work_type, work_w in guidance.work_types.items():
        wbgt = table[value].to_numpy(dtype=float)
        top = table[high].to_numpy(dtype=float) if high else wbgt
        frames.append(
            pd.DataFrame(
                {
                    "hour_utc": table["hour_utc"].reset_index(drop=True),
                    "work_type": work_type,
                    "wbgt_c": wbgt,
                    "level": levels(wbgt, work_type, guidance),
                    "level_if_high": levels(top, work_type, guidance),
                    "work_minutes_acclimatized": allowed_minutes(
                        wbgt, work_w, guidance.acclimatized, guidance
                    ),
                    "work_minutes_new_workers": allowed_minutes(
                        wbgt, work_w, guidance.new_workers, guidance
                    ),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)[BY_HOUR_COLUMNS]


def day_summaries(by_hour: pd.DataFrame, timezone: str) -> pd.DataFrame:
    """For each local day and work type: the hottest hour, how many hours reach each level,
    and the first and last hour when acclimatized workers need breaks or a later start."""
    rows = by_hour.dropna(subset=["wbgt_c"]).assign(
        local=lambda d: pd.to_datetime(d["hour_utc"], utc=True).dt.tz_convert(timezone)
    )
    rows["date"] = rows["local"].dt.date
    summaries = []
    for (date, work_type), day in rows.groupby(["date", "work_type"], sort=True):
        peak = day.loc[day["wbgt_c"].idxmax()]
        limited = day[day["level"].isin(["work_rest", "reschedule"])]
        counts = day["level"].value_counts()
        summaries.append(
            {
                "date": date,
                "work_type": work_type,
                "hours": len(day),
                "peak_wbgt_c": round(float(peak["wbgt_c"]), 1),
                "peak_time": f"{peak['local']:%H:%M}",
                **{f"hours_{level}": int(counts.get(level, 0)) for level in LEVELS[1:]},
                "limited_from": f"{limited['local'].min():%H:%M}" if len(limited) else None,
                "limited_until": (
                    f"{limited['local'].max() + pd.Timedelta(hours=1):%H:%M}"
                    if len(limited)
                    else None
                ),
                "worst_level": max(day["level"], key=LEVELS.index),
            }
        )
    return pd.DataFrame(summaries)
