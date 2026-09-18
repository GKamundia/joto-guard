"""Turn the SI1145 light sensor's raw counts into solar irradiance (GHI, W/m²).

The sensor reports counts, not W/m², and its response is not proportional: against
ERA5 it gives about half as many counts per W/m² at 07:00 as at noon, the usual sign of
a cheap sensor under a housing that sees less of a low sun. So the infrared counts are
scaled by a factor that depends on the height of the sun:

    GHI = (IR counts − dark floor) × (a + b × (1 − μ))

where μ is the hour's mean cosine of the solar zenith angle. a and b are fitted by least
squares against a reference. The skill figures come from leaving each day out of the fit
in turn and predicting it, so they describe days the fit has not seen.

Judge them by sky. The station sees its own clouds and a reanalysis sees a grid cell's
average, so under cloud the two disagree whatever the calibration; hours the reference
itself calls clear are the fairer test, and are reported separately when the reference
carries cloud cover.

The visible channel is not used: across the record it is a near-constant 9 % of the
infrared one, so it adds no information.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from .solar import hourly_mean_cos_zenith

FORMULA = "GHI = (IR counts - dark floor) * (a + b * (1 - mu)), mu = hourly mean cos(solar zenith)"

# Hours whose mean cos zenith is below this hold only a sliver of sunrise or sunset.
MIN_COS_ZENITH = 0.05

# "High sun" is the sun more than 30 degrees up, when heat stress can matter.
HIGH_SUN_COS_ZENITH = 0.5

# A reference hour counts as clear when it reports less cloud than this, in percent.
CLEAR_SKY_CLOUD_PCT = 25


@dataclass(frozen=True)
class Calibration:
    dark_floor_counts: float
    a: float
    b: float
    reference: str
    first_day: str
    last_day: str
    n_days: int
    n_hours: int
    held_out: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {"formula": FORMULA, **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Calibration":
        return cls(**{key: value for key, value in data.items() if key != "formula"})


def reference_from_open_meteo(payload: dict[str, Any]) -> pd.DataFrame:
    """Hourly GHI from an Open-Meteo response, stamped at the start of each hour.

    Open-Meteo gives an hour's shortwave radiation as the mean over the preceding hour,
    so the value stamped 10:00 belongs to the station hour that starts at 09:00.
    """
    if payload.get("timezone") not in {"GMT", "UTC"}:
        raise ValueError("request the reference with timezone=GMT so its hours are UTC")
    hourly = payload["hourly"]
    frame = pd.DataFrame(
        {
            "hour_utc": pd.to_datetime(hourly["time"], utc=True) - pd.Timedelta(hours=1),
            "ghi_ref_wm2": pd.to_numeric(pd.Series(hourly["shortwave_radiation"]), errors="coerce"),
        }
    )
    if "cloud_cover" in hourly:
        frame["cloud_cover_pct"] = pd.to_numeric(pd.Series(hourly["cloud_cover"]), errors="coerce")
    return frame.dropna(subset=["ghi_ref_wm2"]).reset_index(drop=True)


def training_table(
    hourly: pd.DataFrame,
    reference: pd.DataFrame,
    latitude: float,
    longitude: float,
    dark_floor_counts: float,
) -> pd.DataFrame:
    """Daylight station hours joined to the reference, with net counts and sun height."""
    station = hourly[["hour_utc", "light_ir_counts"]].assign(
        hour_utc=pd.to_datetime(hourly["hour_utc"], utc=True)
    )
    table = (
        station.merge(reference, on="hour_utc")
        .dropna(subset=["light_ir_counts", "ghi_ref_wm2"])
        .reset_index(drop=True)
    )
    table["ir_net"] = (table["light_ir_counts"] - dark_floor_counts).clip(lower=0)
    table["mu"] = hourly_mean_cos_zenith(table["hour_utc"], latitude, longitude)
    table["day"] = table["hour_utc"].dt.floor("D")
    return table[table["mu"] > MIN_COS_ZENITH].reset_index(drop=True)


def fit(table: pd.DataFrame) -> tuple[float, float]:
    design = np.column_stack([table["ir_net"], table["ir_net"] * (1 - table["mu"])])
    (a, b), *_ = np.linalg.lstsq(design, table["ghi_ref_wm2"].to_numpy(), rcond=None)
    return float(a), float(b)


def estimate_ghi(
    ir_counts: ArrayLike, cos_zenith: ArrayLike, calibration: Calibration
) -> np.ndarray:
    """GHI in W/m².

    Zero whenever the sun is down, since that needs no sensor; in daylight, missing counts
    give a missing estimate.
    """
    net = np.clip(np.asarray(ir_counts, dtype=float) - calibration.dark_floor_counts, 0, None)
    mu = np.asarray(cos_zenith, dtype=float)
    ghi = np.clip(net * (calibration.a + calibration.b * (1 - mu)), 0, None)
    return np.where(mu > 0, ghi, 0.0)


def held_out_errors(table: pd.DataFrame) -> pd.Series:
    """Each hour's error when the whole of its day is left out of the fit."""
    errors = []
    for day in table["day"].unique():
        a, b = fit(table[table["day"] != day])
        test = table[table["day"] == day]
        predicted = test["ir_net"] * (a + b * (1 - test["mu"]))
        errors.append(predicted - test["ghi_ref_wm2"])
    return pd.concat(errors)


def skill(errors: pd.Series, observed: pd.Series) -> dict[str, float]:
    spread = ((observed - observed.mean()) ** 2).sum()
    return {
        "n_hours": len(errors),
        "rmse_wm2": round(float(np.sqrt((errors**2).mean())), 1),
        "mae_wm2": round(float(errors.abs().mean()), 1),
        "bias_wm2": round(float(errors.mean()), 1),
        "r2": round(float(1 - (errors**2).sum() / spread), 3) if spread else float("nan"),
    }


def calibrate(
    hourly: pd.DataFrame,
    reference: pd.DataFrame,
    latitude: float,
    longitude: float,
    dark_floor_counts: float,
    reference_name: str,
) -> Calibration:
    table = training_table(hourly, reference, latitude, longitude, dark_floor_counts)
    if table["day"].nunique() < 2:
        raise ValueError("calibration needs at least two days that overlap the reference")

    a, b = fit(table)
    errors = held_out_errors(table)
    high_sun = table["mu"] >= HIGH_SUN_COS_ZENITH
    held_out = {
        "daylight": skill(errors, table["ghi_ref_wm2"]),
        "high_sun": skill(errors[high_sun], table.loc[high_sun, "ghi_ref_wm2"]),
    }
    if "cloud_cover_pct" in table:
        clear = table["cloud_cover_pct"] < CLEAR_SKY_CLOUD_PCT
        if clear.any():
            held_out["clear_reference_sky"] = skill(errors[clear], table.loc[clear, "ghi_ref_wm2"])
    return Calibration(
        dark_floor_counts=float(dark_floor_counts),
        a=round(a, 6),
        b=round(b, 6),
        reference=reference_name,
        first_day=str(table["day"].min().date()),
        last_day=str(table["day"].max().date()),
        n_days=int(table["day"].nunique()),
        n_hours=len(table),
        held_out=held_out,
    )


def ghi_hourly(
    hourly: pd.DataFrame, calibration: Calibration, latitude: float, longitude: float
) -> pd.DataFrame:
    """Estimated GHI for every station hour."""
    hours = pd.to_datetime(hourly["hour_utc"], utc=True)
    mu = hourly_mean_cos_zenith(hours, latitude, longitude)
    return pd.DataFrame(
        {
            "hour_utc": hours,
            "cos_zenith": np.round(mu, 4),
            "ghi_wm2": np.round(estimate_ghi(hourly["light_ir_counts"], mu, calibration), 1),
        }
    )


def save(calibration: Calibration, path: str | Path) -> None:
    Path(path).write_text(json.dumps(calibration.to_dict(), indent=2) + "\n", encoding="utf-8")


def load(path: str | Path) -> Calibration:
    return Calibration.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
