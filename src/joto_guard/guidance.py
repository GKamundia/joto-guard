"""The heat guidance the API and the Telegram bot serve, as one JSON-ready document."""

from datetime import datetime
from typing import Any

import pandas as pd

from conduit_sentinel.report import to_json_ready

from . import bands

SOURCES = [
    "NIOSH (2016). Criteria for a Recommended Standard: Occupational Exposure to Heat and Hot "
    "Environments. DHHS (NIOSH) Publication No. 2016-106.",
    "Herrmann, S. D. et al. (2024). 2024 Adult Compendium of Physical Activities. Journal of "
    "Sport and Health Science 13, 6-12.",
    "Liljegren, J. C. et al. (2008). Modeling the wet bulb globe temperature using standard "
    "meteorological measurements. J. Occup. Environ. Hyg. 5, 645-655.",
    "Forecast: ECMWF IFS through Open-Meteo.com (CC BY 4.0).",
]


def forecast_guidance(
    table: pd.DataFrame,
    guidance: bands.HeatGuidance,
    station: dict[str, Any],
    timezone: str,
    model: str,
    generated_at: datetime,
) -> dict[str, Any]:
    """Guidance for every forecast hour and a summary for every local day.

    Uses the corrected WBGT and its band when the table has them, the raw WBGT otherwise.
    """
    corrected = "wbgt_corrected_c" in table
    value, high = ("wbgt_corrected_c", "wbgt_high_c") if corrected else ("wbgt_c", None)
    by_hour = bands.guidance_by_hour(table, guidance, value=value, high=high)
    days = bands.day_summaries(by_hour, timezone)

    per_hour = dict(tuple(by_hour.groupby("hour_utc")))
    hours = []
    for row in table.to_dict(orient="records"):
        at_hour = per_hour[row["hour_utc"]]
        hours.append(
            {
                "hour_utc": row["hour_utc"],
                "local_time": f"{row['hour_utc'].tz_convert(timezone):%Y-%m-%d %H:%M}",
                "wbgt_c": _rounded(row[value]),
                "wbgt_low_c": _rounded(row["wbgt_low_c"]) if corrected else None,
                "wbgt_high_c": _rounded(row["wbgt_high_c"]) if corrected else None,
                "by_work_type": {
                    item["work_type"]: {
                        "level": item["level"],
                        "level_if_high": item["level_if_high"],
                        "work_minutes_acclimatized": _minutes(item["work_minutes_acclimatized"]),
                        "work_minutes_new_workers": _minutes(item["work_minutes_new_workers"]),
                    }
                    for item in at_hour.to_dict(orient="records")
                },
            }
        )

    summaries = []
    for date, day in days.groupby("date", sort=True):
        summaries.append(
            {
                "date": date,
                "by_work_type": {
                    item.pop("work_type"): {k: v for k, v in item.items() if k != "date"}
                    for item in day.to_dict(orient="records")
                },
            }
        )

    return to_json_ready(
        {
            "generated_at_utc": generated_at,
            "station": station,
            "timezone": timezone,
            "forecast": {"model": model, "corrected_towards_station": corrected},
            "work_types": {
                name: {
                    "metabolic_rate_w": rate,
                    "limit_acclimatized_c": round(float(guidance.acclimatized.at(rate)), 1),
                    "limit_new_workers_c": round(float(guidance.new_workers.at(rate)), 1),
                    "examples": list(guidance.examples.get(name, ())),
                }
                for name, rate in guidance.work_types.items()
            },
            "levels": bands.LEVEL_TEXT,
            "advice": guidance.advice,
            "swahili": guidance.swahili,
            "hours": hours,
            "days": summaries,
            "sources": SOURCES,
        }
    )


def _minutes(value: float) -> int | None:
    return None if pd.isna(value) else int(value)


def _rounded(value: float) -> float | None:
    return None if pd.isna(value) else round(float(value), 1)
