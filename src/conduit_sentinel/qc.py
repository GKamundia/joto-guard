"""Quality-control rules R01 to R16 and the gaps table (spec sections 6 and 7)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config
from .schema import CHANNEL_GROUPS, THERMOMETERS, VARIABLES, Flag, qc_column

# Sensor values have 0.1 resolution, so float noise such as 1.6000000000000014 must
# not push a value over a limit. Every threshold comparison allows this much slack.
EPS = 1e-9


@dataclass(frozen=True)
class Rule:
    id: str
    flag: Flag | None
    description: str


RULES: dict[str, Rule] = {
    rule.id: rule
    for rule in (
        Rule("R01", Flag.BAD, "Temperature outside the plausible range"),
        Rule("R02", Flag.BAD, "Humidity outside the valid range"),
        Rule("R03", Flag.BAD, "Station pressure outside the site range"),
        Rule("R04", Flag.BAD, "Wind speed or gust outside the plausible range"),
        Rule("R05", Flag.BAD, "Rain per observation outside the plausible range"),
        Rule("R06", Flag.SUSPECT, "Light counts below the dark floor"),
        Rule("R07", Flag.SUSPECT, "Temperature changed too fast between observations"),
        Rule("R08", Flag.SUSPECT, "Flat line in temperature or humidity"),
        Rule("R08b", Flag.SUSPECT, "Flat line in station pressure"),
        Rule("R08c", Flag.SUSPECT, "Flat line in non-zero wind speed"),
        Rule("R09", Flag.SUSPECT, "Thermometers disagree"),
        Rule("R10", Flag.SUSPECT, "Gust below wind speed"),
        Rule("R11", Flag.SUSPECT, "One rain gauge recorded rain while the other read zero"),
        Rule("R12", Flag.MISSING, "Channel empty for the whole day"),
        Rule("R13", Flag.BAD, "Gust direction column duplicates gust speed"),
        Rule("R14", None, "Late report or gap before this observation"),
        Rule("R15", None, "Non-zero device health code"),
        Rule("R16", Flag.SUSPECT, "Firmware WBGT below the firmware wet bulb"),
    )
}

FLAT_LINE_RULES = {
    "t_sht_c": "R08",
    "rh_pct": "R08",
    "p_station_hpa": "R08b",
    "wind_speed_ms": "R08c",
}

GAP_COLUMNS = ("station_id", "gap_start_utc", "gap_end_utc", "interval_s", "missing_minutes")
RULE_HIT_COLUMNS = ("rule_id", "variable", "date_utc", "n_rows")


@dataclass(frozen=True)
class IntervalSummary:
    median_s: float | None
    min_s: float | None
    max_s: float | None
    late: int
    gaps: int


@dataclass(frozen=True)
class QCResult:
    obs: pd.DataFrame
    gaps: pd.DataFrame
    rule_hits: pd.DataFrame
    intervals: IntervalSummary


def apply_qc(obs: pd.DataFrame, config: Config) -> QCResult:
    """Flag obs_raw and build the gaps table.

    Returns obs_qc (obs_raw plus one qc_<variable> flag column per variable and qc_notes),
    the gaps table, and rule_hits: how many rows each rule fired on, per variable and UTC day.
    """
    _check_obs(obs)
    obs = obs.reset_index(drop=True)
    day = obs["time_utc"].dt.floor("D")
    interval_s = obs["time_utc"].diff().dt.total_seconds()
    flags = _Flags(len(obs))

    _check_ranges(obs, config, flags)
    _check_light(obs, config, flags)
    _check_steps(obs, interval_s, config, flags)
    _check_flat_lines(obs, config, flags)
    _check_thermometer_spread(obs, config, flags)
    flags.mark("R10", "wind_gust_ms", obs["wind_gust_ms"] < obs["wind_speed_ms"] - EPS)
    _check_rain_gauges(obs, day, config, flags)
    _check_empty_channels(obs, day, flags)
    _check_duplicate_gust_direction(obs, day, config, flags)
    gaps, intervals = _check_intervals(obs, interval_s, config, flags)
    code = obs["health_code"]
    flags.mark("R15", "health_code", code.notna() & (code != 0))
    flags.mark("R16", "wbgt_fw_c", obs["wbgt_fw_c"] < obs["wet_bulb_fw_c"] - EPS)

    obs_qc = obs.copy()
    for variable in VARIABLES:
        missing = obs[variable].isna().to_numpy()
        levels = np.where(missing, Flag.MISSING, flags.level(variable))
        obs_qc[qc_column(variable)] = levels.astype(np.int8)
    obs_qc["qc_notes"] = flags.notes()

    return QCResult(
        obs=obs_qc,
        gaps=gaps,
        rule_hits=flags.hits_by_day(day),
        intervals=intervals,
    )


def usable(obs_qc: pd.DataFrame, variable: str) -> pd.Series:
    """Values flagged good or suspect; bad, missing and filled values become null."""
    return obs_qc[variable].where(obs_qc[qc_column(variable)] <= Flag.SUSPECT)


def run_lengths(values: pd.Series) -> np.ndarray:
    """For each row, the length of the run of identical consecutive values it belongs to.

    Nulls break runs and get 0.
    """
    starts = values.ne(values.shift()) | values.isna()
    lengths = values.groupby(starts.cumsum()).transform("size").to_numpy()
    return np.where(values.isna().to_numpy(), 0, lengths)


class _Flags:
    """Accumulates flag levels per variable and the rows each rule fired on."""

    def __init__(self, n_rows: int):
        self._n_rows = n_rows
        self._levels = {variable: np.zeros(n_rows, dtype=np.int8) for variable in VARIABLES}
        self._hits: dict[tuple[str, str], np.ndarray] = {}

    def mark(self, rule_id: str, variable: str, mask: pd.Series | np.ndarray) -> None:
        if isinstance(mask, pd.Series):
            mask = mask.to_numpy(dtype=bool, na_value=False)
        if not mask.any():
            return
        flag = RULES[rule_id].flag
        if flag in (Flag.SUSPECT, Flag.BAD):
            level = self._levels[variable]
            level[mask] = np.maximum(level[mask], flag)
        key = (rule_id, variable)
        self._hits[key] = self._hits[key] | mask if key in self._hits else mask

    def level(self, variable: str) -> np.ndarray:
        return self._levels[variable]

    def notes(self) -> np.ndarray:
        by_rule: dict[str, np.ndarray] = {}
        for (rule_id, _), mask in self._hits.items():
            by_rule[rule_id] = by_rule[rule_id] | mask if rule_id in by_rule else mask
        notes = np.full(self._n_rows, "", dtype=object)
        for rule_id in sorted(by_rule):
            mask = by_rule[rule_id]
            current = notes[mask]
            notes[mask] = np.where(current == "", rule_id, current + ";" + rule_id)
        return notes

    def hits_by_day(self, day: pd.Series) -> pd.DataFrame:
        frames = []
        for (rule_id, variable), mask in self._hits.items():
            counts = pd.Series(mask, index=day.index).groupby(day).sum()
            counts = counts[counts > 0]
            frames.append(
                pd.DataFrame(
                    {
                        "rule_id": rule_id,
                        "variable": variable,
                        "date_utc": counts.index.date,
                        "n_rows": counts.to_numpy(dtype=int),
                    }
                )
            )
        if not frames:
            return pd.DataFrame(columns=list(RULE_HIT_COLUMNS))
        hits = pd.concat(frames, ignore_index=True)
        return hits.sort_values(["date_utc", "rule_id", "variable"], ignore_index=True)


def _check_obs(obs: pd.DataFrame) -> None:
    missing = [c for c in ("station_id", "time_utc", *VARIABLES) if c not in obs.columns]
    if missing:
        raise ValueError(f"observations are missing columns: {missing}")
    times = obs["time_utc"]
    if not times.is_monotonic_increasing or times.duplicated().any():
        raise ValueError("observations must be sorted by time_utc with unique timestamps")
    if obs["station_id"].nunique() > 1:
        raise ValueError("quality control runs on one station at a time")


def _outside(values: pd.Series, bounds: tuple[float, float]) -> pd.Series:
    low, high = bounds
    return (values < low - EPS) | (values > high + EPS)


def _check_ranges(obs: pd.DataFrame, config: Config, flags: _Flags) -> None:
    ranges = config.ranges
    for variable in THERMOMETERS:
        flags.mark("R01", variable, _outside(obs[variable], ranges.temperature_c))
    low, high = ranges.humidity_pct
    rh = obs["rh_pct"]
    flags.mark("R02", "rh_pct", (rh <= low + EPS) | (rh > high + EPS))
    flags.mark("R03", "p_station_hpa", _outside(obs["p_station_hpa"], ranges.pressure_hpa))
    flags.mark("R04", "wind_speed_ms", _outside(obs["wind_speed_ms"], ranges.wind_speed_ms))
    flags.mark("R04", "wind_gust_ms", _outside(obs["wind_gust_ms"], ranges.wind_gust_ms))
    for variable in ("rain1_mm", "rain2_mm"):
        flags.mark("R05", variable, _outside(obs[variable], ranges.rain_mm))


def _check_light(obs: pd.DataFrame, config: Config, flags: _Flags) -> None:
    floor = config.qc.light_dark_floor_counts
    for variable in ("light_vis_counts", "light_ir_counts"):
        flags.mark("R06", variable, obs[variable] < floor - EPS)


def _check_steps(obs: pd.DataFrame, interval_s: pd.Series, config: Config, flags: _Flags) -> None:
    close = interval_s <= config.qc.step_max_interval_s + EPS
    for variable in THERMOMETERS:
        rate_per_min = obs[variable].diff().abs() / (interval_s / 60)
        flags.mark("R07", variable, close & (rate_per_min > config.qc.max_step_c_per_min + EPS))


def _check_flat_lines(obs: pd.DataFrame, config: Config, flags: _Flags) -> None:
    for variable, rule_id in FLAT_LINE_RULES.items():
        values = obs[variable]
        mask = run_lengths(values) >= config.qc.flat_line_rows[variable]
        if rule_id == "R08c":
            # Calm nights hold wind speed at zero for hours; only non-zero runs are suspect.
            mask &= values.abs().to_numpy() > EPS
        flags.mark(rule_id, variable, mask)


def _check_thermometer_spread(obs: pd.DataFrame, config: Config, flags: _Flags) -> None:
    temperatures = obs[list(THERMOMETERS)]
    spread = temperatures.max(axis=1) - temperatures.min(axis=1)
    disagree = spread > config.qc.max_thermometer_spread_c + EPS
    for variable in THERMOMETERS:
        flags.mark("R09", variable, disagree)


def _check_rain_gauges(obs: pd.DataFrame, day: pd.Series, config: Config, flags: _Flags) -> None:
    gauges = {"rain_gauge_1": "rain1_mm", "rain_gauge_2": "rain2_mm"}
    totals, reporting = {}, {}
    for gauge, variable in gauges.items():
        values = obs[variable].where(flags.level(variable) < Flag.BAD)
        totals[gauge] = values.groupby(day).transform("sum")
        reporting[gauge] = values.notna().groupby(day).transform("any")

    threshold = config.qc.rain_disagreement_mm
    for wet, dry in (("rain_gauge_1", "rain_gauge_2"), ("rain_gauge_2", "rain_gauge_1")):
        disagree = (totals[wet] >= threshold - EPS) & (totals[dry].abs() <= EPS) & reporting[dry]
        for variable in CHANNEL_GROUPS[dry]:
            flags.mark("R11", variable, disagree)


def _check_empty_channels(obs: pd.DataFrame, day: pd.Series, flags: _Flags) -> None:
    for variable in VARIABLES:
        flags.mark("R12", variable, obs[variable].isna().groupby(day).transform("all"))


def _check_duplicate_gust_direction(
    obs: pd.DataFrame, day: pd.Series, config: Config, flags: _Flags
) -> None:
    direction, gust = obs["wind_gust_dir_deg"], obs["wind_gust_ms"]
    both = direction.notna() & gust.notna()
    identical = both & ((direction - gust).abs() <= EPS)
    share = identical.groupby(day).transform("sum") / both.groupby(day).transform("sum")
    flags.mark("R13", "wind_gust_dir_deg", share >= config.qc.duplicate_column_share - EPS)


def _check_intervals(
    obs: pd.DataFrame, interval_s: pd.Series, config: Config, flags: _Flags
) -> tuple[pd.DataFrame, IntervalSummary]:
    late_s, gap_s = config.qc.late_interval_s, config.qc.gap_interval_s
    late = (interval_s >= late_s - EPS) & (interval_s <= gap_s + EPS)
    gap = interval_s > gap_s + EPS
    flags.mark("R14", "time_utc", late | gap)

    expected_s = config.station.expected_interval_s
    gaps = pd.DataFrame(
        {
            "station_id": obs["station_id"][gap],
            "gap_start_utc": obs["time_utc"].shift()[gap],
            "gap_end_utc": obs["time_utc"][gap],
            "interval_s": interval_s[gap],
            "missing_minutes": ((interval_s[gap] - expected_s) / 60).round(2),
        },
        columns=list(GAP_COLUMNS),
    ).reset_index(drop=True)

    measured = interval_s.dropna()
    summary = IntervalSummary(
        median_s=float(measured.median()) if len(measured) else None,
        min_s=float(measured.min()) if len(measured) else None,
        max_s=float(measured.max()) if len(measured) else None,
        late=int(late.sum()),
        gaps=int(gap.sum()),
    )
    return gaps, summary
