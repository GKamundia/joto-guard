"""Load and validate the thresholds in config/qc_rules.yaml."""

from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

FLAT_LINE_VARIABLES = ("t_sht_c", "rh_pct", "p_station_hpa", "wind_speed_ms")


class ConfigError(ValueError):
    """The configuration is missing a value or holds an invalid one."""


@dataclass(frozen=True)
class StationSettings:
    expected_interval_s: float
    display_timezone: str


@dataclass(frozen=True)
class Ranges:
    temperature_c: tuple[float, float]
    humidity_pct: tuple[float, float]
    pressure_hpa: tuple[float, float]
    wind_speed_ms: tuple[float, float]
    wind_gust_ms: tuple[float, float]
    rain_mm: tuple[float, float]


@dataclass(frozen=True)
class QCThresholds:
    light_dark_floor_counts: float
    max_step_c_per_min: float
    step_max_interval_s: float
    flat_line_rows: dict[str, int]
    max_thermometer_spread_c: float
    rain_disagreement_mm: float
    duplicate_column_share: float
    late_interval_s: float
    gap_interval_s: float


@dataclass(frozen=True)
class HealthWeights:
    bad_group_penalty: float
    suspect_group_penalty: float
    missing_minutes_per_point: float
    max_flagged_share: float


@dataclass(frozen=True)
class HourlySettings:
    min_coverage_pct: float
    min_variable_coverage_pct: float


@dataclass(frozen=True)
class AuditSettings:
    stull_max_mae_c: float
    wbgt_below_wet_bulb_max_share: float
    night_start_hour: int
    night_end_hour: int


@dataclass(frozen=True)
class Config:
    station: StationSettings
    ranges: Ranges
    qc: QCThresholds
    health: HealthWeights
    hourly: HourlySettings
    audit: AuditSettings


def load_config(path: str | Path) -> Config:
    with open(path, encoding="utf-8") as fh:
        return config_from_dict(yaml.safe_load(fh))


def config_from_dict(raw: Any) -> Config:
    data = _mapping(raw, "config")
    _check_keys(data, {f.name for f in fields(Config)}, "config")
    config = Config(
        station=_build(StationSettings, data["station"], "station"),
        ranges=_build_ranges(data["ranges"]),
        qc=_build(QCThresholds, data["qc"], "qc"),
        health=_build(HealthWeights, data["health"], "health"),
        hourly=_build(HourlySettings, data["hourly"], "hourly"),
        audit=_build(AuditSettings, data["audit"], "audit"),
    )
    _validate(config)
    return config


def _build(cls: type, raw: Any, section: str) -> Any:
    data = _mapping(raw, section)
    _check_keys(data, {f.name for f in fields(cls)}, section)
    values = {}
    for field in fields(cls):
        name = f"{section}.{field.name}"
        value = data[field.name]
        if field.type is float:
            values[field.name] = _number(value, name)
        elif field.type is int:
            values[field.name] = _integer(value, name)
        elif field.type is str:
            if not isinstance(value, str):
                raise ConfigError(f"{name} must be text")
            values[field.name] = value
        elif field.name == "flat_line_rows":
            values[field.name] = _flat_line_rows(value, name)
        else:
            raise ConfigError(f"{name} has an unsupported type")
    return cls(**values)


def _build_ranges(raw: Any) -> Ranges:
    data = _mapping(raw, "ranges")
    _check_keys(data, {f.name for f in fields(Ranges)}, "ranges")
    bounds = {}
    for name, value in data.items():
        if not isinstance(value, list | tuple) or len(value) != 2:
            raise ConfigError(f"ranges.{name} must be [min, max]")
        low = _number(value[0], f"ranges.{name}")
        high = _number(value[1], f"ranges.{name}")
        if low >= high:
            raise ConfigError(f"ranges.{name}: min must be below max")
        bounds[name] = (low, high)
    return Ranges(**bounds)


def _flat_line_rows(raw: Any, name: str) -> dict[str, int]:
    data = _mapping(raw, name)
    _check_keys(data, set(FLAT_LINE_VARIABLES), name)
    rows = {variable: _integer(data[variable], f"{name}.{variable}") for variable in data}
    if any(count < 2 for count in rows.values()):
        raise ConfigError(f"{name}: a flat line needs at least 2 rows")
    return rows


def _validate(config: Config) -> None:
    if config.station.expected_interval_s <= 0:
        raise ConfigError("station.expected_interval_s must be positive")
    try:
        ZoneInfo(config.station.display_timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError(f"unknown time zone {config.station.display_timezone!r}") from exc

    qc = config.qc
    if not 0 < qc.late_interval_s < qc.gap_interval_s:
        raise ConfigError("qc.late_interval_s must be positive and below qc.gap_interval_s")
    shares = {
        "qc.duplicate_column_share": qc.duplicate_column_share,
        "health.max_flagged_share": config.health.max_flagged_share,
        "audit.wbgt_below_wet_bulb_max_share": config.audit.wbgt_below_wet_bulb_max_share,
    }
    for name, share in shares.items():
        if not 0 <= share <= 1:
            raise ConfigError(f"{name} must be between 0 and 1")
    if config.health.missing_minutes_per_point <= 0:
        raise ConfigError("health.missing_minutes_per_point must be positive")
    for name in ("min_coverage_pct", "min_variable_coverage_pct"):
        if not 0 <= getattr(config.hourly, name) <= 100:
            raise ConfigError(f"hourly.{name} must be between 0 and 100")
    for name in ("night_start_hour", "night_end_hour"):
        if not 0 <= getattr(config.audit, name) <= 23:
            raise ConfigError(f"audit.{name} must be an hour from 0 to 23")


def _mapping(raw: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{name} must be a mapping")
    return raw


def _check_keys(data: Mapping[str, Any], expected: set[str], name: str) -> None:
    missing = sorted(expected - data.keys())
    unknown = sorted(data.keys() - expected)
    if missing:
        raise ConfigError(f"{name} is missing {', '.join(missing)}")
    if unknown:
        raise ConfigError(f"{name} has unknown keys: {', '.join(unknown)}")


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"{name} must be a number")
    return float(value)


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be a whole number")
    return value
