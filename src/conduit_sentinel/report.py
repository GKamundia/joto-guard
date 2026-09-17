"""Assemble the Station Health Report payload (spec section 10)."""

import math
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
import pandas as pd

from . import __version__
from .audit import THERMOMETER_PAIRS, is_night
from .config import Config
from .ingest import IngestResult
from .qc import EPS, RULES, QCResult, usable
from .schema import GEOCSV_NAMES, VARIABLES

DEFAULT_LINKS = {"qc_dataset": "obs_qc.csv", "api_docs": "/docs"}


def build_report(
    ingested: IngestResult,
    qc: QCResult,
    health: pd.DataFrame,
    status: pd.DataFrame,
    audits: pd.DataFrame,
    config: Config,
    *,
    generated_at: datetime | None = None,
    links: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The report as JSON-ready data: dicts, lists, strings, numbers and None.

    Times are ISO 8601 UTC strings ending in Z; dates are YYYY-MM-DD in UTC.
    """
    obs = qc.obs
    report = {
        "sentinel_version": __version__,
        "generated_at_utc": generated_at or datetime.now(UTC),
        "station": _station_card(ingested, qc),
        "coverage": _coverage(health, qc, config),
        "health": {
            "rule": score_rule_text(config),
            "daily": _records(health.drop(columns="station_id")),
        },
        "channel_status": _records(status.drop(columns="station_id")),
        "thermometer_agreement": _thermometer_agreement(obs, config),
        "rain": _rain_check(obs, qc.rule_hits, health),
        "light": _light_summary(obs, config),
        "audits": _records(audits),
        "device_codes": _device_codes(obs),
        "recommendations": recommendations(qc, health, audits),
        "rules": {rule.id: rule.description for rule in RULES.values()},
        "links": dict(links or DEFAULT_LINKS),
    }
    return to_json_ready(report)


def score_rule_text(config: Config) -> str:
    weights = config.health
    share = f"{weights.max_flagged_share * 100:g} %"
    return (
        f"score = max(0, 100 − {weights.bad_group_penalty:g} × bad groups − "
        f"{weights.suspect_group_penalty:g} × suspect groups − missing minutes ÷ "
        f"{weights.missing_minutes_per_point:g}). A channel group is bad when one of its "
        f"channels is empty for the day, more than {share} of its rows are flagged bad, or "
        f"its column duplicates another. It is suspect when more than {share} of its rows "
        "are flagged suspect, or when one rain gauge recorded rain and the other read zero. "
        "Firmware-derived values are audited separately and not scored."
    )


def recommendations(qc: QCResult, health: pd.DataFrame, audits: pd.DataFrame) -> list[dict]:
    """Suggestions for the station owners, worded by the strength of the evidence.

    Each one appears only when the data in this report triggers it.
    """
    return [
        *_rain_gauge_recommendations(qc),
        *_empty_channel_recommendations(qc.rule_hits, health),
        *_duplicate_column_recommendations(qc),
        *_device_code_recommendations(qc.obs),
        *_wbgt_recommendations(audits),
    ]


def to_json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): to_json_ready(v) for k, v in value.items()}
    if isinstance(value, list | tuple | np.ndarray):
        return [to_json_ready(v) for v in value]
    if value is None or value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, datetime):
        stamp = pd.Timestamp(value)
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
        return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool | np.bool_):
        return bool(value)
    if isinstance(value, int | np.integer):
        return int(value)
    if isinstance(value, float | np.floating):
        return float(value) if math.isfinite(value) else None
    return value


def _station_card(ingested: IngestResult, qc: QCResult) -> dict:
    station, times, intervals = ingested.station, qc.obs["time_utc"], qc.intervals
    return {
        "station_id": station.station_id,
        "name": station.name,
        "site": station.site,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "elevation_m": station.elevation_m,
        "doi": station.doi,
        "record_start_utc": times.min(),
        "record_end_utc": times.max(),
        "n_obs": len(times),
        "interval_s": {
            "median": intervals.median_s,
            "min": intervals.min_s,
            "max": intervals.max_s,
        },
        "duplicates_removed": ingested.duplicates_removed,
        "source_files": [
            {
                "name": f.name,
                "rows": f.rows,
                "first_utc": f.first_utc,
                "last_utc": f.last_utc,
                "measurements_declared": f.measurements_declared,
                "measurements_counted": f.measurements_counted,
            }
            for f in ingested.files
        ],
    }


def _coverage(health: pd.DataFrame, qc: QCResult, config: Config) -> dict:
    expected_per_day = 86400 / config.station.expected_interval_s
    return {
        "daily": [
            {
                "date_utc": row.date_utc,
                "n_obs": row.n_obs,
                "coverage_pct": round(row.n_obs / expected_per_day * 100, 1),
                "missing_minutes": row.missing_minutes,
            }
            for row in health.itertuples(index=False)
        ],
        "gaps": _records(qc.gaps.drop(columns="station_id")),
        "gap_threshold_s": config.qc.gap_interval_s,
        "late_threshold_s": config.qc.late_interval_s,
        "late_intervals": qc.intervals.late,
    }


def _thermometer_agreement(obs: pd.DataFrame, config: Config) -> dict:
    day = obs["time_utc"].dt.floor("D")
    pairs = []
    for first, second in THERMOMETER_PAIRS:
        diff = (usable(obs, first) - usable(obs, second)).abs()
        daily = diff.groupby(day).agg(["mean", "max"]).round(3)
        pairs.append(
            {
                "pair": f"{first}-{second}",
                "mean_abs_diff_c": round(diff.mean(), 3),
                "max_abs_diff_c": round(diff.max(), 3),
                "daily": [
                    {
                        "date_utc": moment.date(),
                        "mean_abs_diff_c": row["mean"],
                        "max_abs_diff_c": row["max"],
                    }
                    for moment, row in daily.iterrows()
                ],
            }
        )
    return {"flag_threshold_c": config.qc.max_thermometer_spread_c, "pairs": pairs}


def _rain_check(obs: pd.DataFrame, rule_hits: pd.DataFrame, health: pd.DataFrame) -> dict:
    day = obs["time_utc"].dt.floor("D")
    totals = pd.DataFrame(
        {
            gauge: usable(obs, gauge).groupby(day).sum(min_count=1)
            for gauge in ("rain1_mm", "rain2_mm")
        }
    ).round(2)
    totals.index = totals.index.date
    totals = totals.reindex(list(health["date_utc"]))
    disagreement = rule_hits[
        (rule_hits["rule_id"] == "R11") & rule_hits["variable"].isin(["rain1_mm", "rain2_mm"])
    ]
    return {
        "daily": [
            {"date_utc": moment, "rain1_mm": row["rain1_mm"], "rain2_mm": row["rain2_mm"]}
            for moment, row in totals.iterrows()
        ],
        "gauge_read_zero": [
            {"date_utc": row.date_utc, "gauge": row.variable}
            for row in disagreement.itertuples(index=False)
        ],
    }


def _light_summary(obs: pd.DataFrame, config: Config) -> dict:
    local_hour = obs["time_utc"].dt.tz_convert(config.station.display_timezone).dt.hour
    night = is_night(local_hour, config.audit.night_start_hour, config.audit.night_end_hour)
    day = obs["time_utc"].dt.floor("D")
    counts = ("light_vis_counts", "light_ir_counts")

    daily_max = pd.DataFrame({v: usable(obs, v).groupby(day).max() for v in (*counts, "uv_index")})
    return {
        "calibrated": False,
        "note": "Raw SI1145 counts, not W/m². UV is an index.",
        "dark_floor_threshold_counts": config.qc.light_dark_floor_counts,
        "night_counts": {
            v: {"median": usable(obs, v)[night].median(), "min": usable(obs, v)[night].min()}
            for v in counts
        },
        "daily_max": [
            {"date_utc": moment.date(), **row.to_dict()} for moment, row in daily_max.iterrows()
        ],
    }


def _device_codes(obs: pd.DataFrame) -> dict:
    code = obs["health_code"]
    interval_s = obs["time_utc"].diff().dt.total_seconds()
    codes = []
    for value, rows in obs[_nonzero(code)].groupby("health_code"):
        before = interval_s[rows.index].dropna()
        codes.append(
            {
                "code": int(value),
                "rows": len(rows),
                "first_utc": rows["time_utc"].min(),
                "last_utc": rows["time_utc"].max(),
                "days_seen": rows["time_utc"].dt.floor("D").nunique(),
                "median_interval_before_s": before.median() if len(before) else None,
                "meaning": "undocumented",
            }
        )
    return {"rows_with_code_zero": int((code == 0).sum()), "codes": codes}


def _rain_gauge_recommendations(qc: QCResult) -> list[dict]:
    hits, obs = qc.rule_hits, qc.obs
    day = obs["time_utc"].dt.floor("D")
    names = {"rain1_mm": "Rain Gauge 1", "rain2_mm": "Rain Gauge 2"}
    found = []
    for dry, wet in (("rain2_mm", "rain1_mm"), ("rain1_mm", "rain2_mm")):
        days = sorted(hits.loc[(hits["rule_id"] == "R11") & (hits["variable"] == dry), "date_utc"])
        if not days:
            continue
        wet_totals = usable(obs, wet).groupby(day).sum()
        wet_totals.index = wet_totals.index.date
        wet_mm = round(float(wet_totals.reindex(days).sum()), 2)
        found.append(
            {
                "title": f"Confirm {names[dry]} during the next rain",
                "detail": (
                    f"{names[dry]} read 0 mm on {_plural(len(days), 'day')} "
                    f"({_date_list(days)}) while {names[wet]} recorded {wet_mm:g} mm. "
                    "Check it in the next rain before treating it as failed."
                ),
                "evidence_level": "suspected fault",
                "rules": ["R11"],
            }
        )
    return found


def _empty_channel_recommendations(hits: pd.DataFrame, health: pd.DataFrame) -> list[dict]:
    empty = hits[hits["rule_id"] == "R12"]
    days_with_data = int((health["n_obs"] > 0).sum())
    found = []
    for variable in VARIABLES:
        n_days = int((empty["variable"] == variable).sum())
        if not n_days:
            continue
        name = GEOCSV_NAMES[variable]
        found.append(
            {
                "title": f"Check the {name} export",
                "detail": (
                    f"{name} was empty on {n_days} of {_plural(days_with_data, 'day')} with data. "
                    "An empty channel can be an export setting rather than a failed sensor."
                ),
                "evidence_level": "channel empty",
                "rules": ["R12"],
            }
        )
    return found


def _duplicate_column_recommendations(qc: QCResult) -> list[dict]:
    if not (qc.rule_hits["rule_id"] == "R13").any():
        return []
    direction, gust = qc.obs["wind_gust_dir_deg"], qc.obs["wind_gust_ms"]
    both = direction.notna() & gust.notna()
    identical = both & ((direction - gust).abs() <= EPS)
    pct = identical.sum() / both.sum() * 100
    return [
        {
            "title": "Fix the Wind Gust Direction export",
            "detail": (
                f"Wind Gust Direction repeated the Wind Gust value on {pct:.1f} % of rows, "
                "so it carries no direction information. Sentinel excludes it."
            ),
            "evidence_level": "duplicated export column",
            "rules": ["R13"],
        }
    ]


def _device_code_recommendations(obs: pd.DataFrame) -> list[dict]:
    codes = obs.loc[_nonzero(obs["health_code"]), "health_code"]
    if codes.empty:
        return []
    listed = ", ".join(str(int(v)) for v in sorted(codes.unique()))
    return [
        {
            "title": "Document the Health codes",
            "detail": (
                f"Health codes {listed} appeared on {_plural(len(codes), 'row')}. "
                "Their meaning is not published, so Sentinel records them without judging them."
            ),
            "evidence_level": "undocumented device code",
            "rules": ["R15"],
        }
    ]


def _wbgt_recommendations(audits: pd.DataFrame) -> list[dict]:
    a03 = audits[audits["audit_id"] == "A03"]
    if a03.empty or a03["verdict"].iloc[0] != "non-standard":
        return []
    value = a03.set_index("metric")["value"]
    return [
        {
            "title": "Consider a black-globe thermometer",
            "detail": (
                f"The firmware WBGT was below the firmware wet bulb on "
                f"{value['pct_below_wet_bulb']:g} % of rows "
                f"({value['pct_below_wet_bulb_night']:g} % at night), which a standard WBGT "
                "does not do. A black-globe sensor would let WBGT be measured, not estimated."
            ),
            "evidence_level": "non-standard firmware value",
            "rules": ["A03", "R16"],
        }
    ]


def _records(frame: pd.DataFrame) -> list[dict]:
    return frame.to_dict(orient="records")


def _nonzero(code: pd.Series) -> np.ndarray:
    return (code.notna() & (code != 0)).to_numpy(dtype=bool, na_value=False)


def _plural(count: int, word: str) -> str:
    return f"{count:,} {word}" if count == 1 else f"{count:,} {word}s"


def _date_list(days: Iterable[date], limit: int = 5) -> str:
    days = list(days)
    shown = ", ".join(d.isoformat() for d in days[:limit])
    return shown if len(days) <= limit else f"{shown} and {len(days) - limit} more"
