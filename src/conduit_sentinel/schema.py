"""Column map, channel groups and flag codes (spec sections 3 and 7)."""

from dataclasses import dataclass
from enum import IntEnum


class Flag(IntEnum):
    GOOD = 0
    SUSPECT = 1
    BAD = 2
    MISSING = 3
    FILLED = 4


@dataclass(frozen=True)
class Column:
    geocsv: str
    short: str
    unit: str
    name: str


TIME = Column("Time", "", "ISO 8601 UTC", "time_utc")

VARIABLE_COLUMNS: tuple[Column, ...] = (
    Column("Health", "hth", "code", "health_code"),
    Column("Battery Voltage", "bv", "%", "battery_voltage"),
    Column("Battery charge status", "bcs", "code", "battery_status"),
    Column("Cell signal strength", "css", "%", "cell_signal"),
    Column("Rain Gauge 1", "rg", "mm", "rain1_mm"),
    Column("Rain Gauge 2", "rg2", "mm", "rain2_mm"),
    Column("Rain Gauge 1 Total Today", "rgt", "mm", "rain1_today_mm"),
    Column("Rain Gauge 2 Total Today", "rgt2", "mm", "rain2_today_mm"),
    Column("Rain Gauge 1 Total Prior", "rgp", "mm", "rain1_prior_mm"),
    Column("Rain Gauge 2 Total Prior", "rgp2", "mm", "rain2_prior_mm"),
    Column("BMX Temperature 1", "bt1", "°C", "t_bmx_c"),
    Column("BMX Pressure 1", "bp1", "hPa", "p_station_hpa"),
    Column("MCP Temperature 1", "mt1", "°C", "t_mcp_c"),
    Column("SHT Temperature", "st1", "°C", "t_sht_c"),
    Column("SHT Humidity", "sh1", "%", "rh_pct"),
    Column("SI1145 Visible 1", "sv1", "counts", "light_vis_counts"),
    Column("SI1145 Infrared 1", "si1", "counts", "light_ir_counts"),
    Column("SI1145 Ultraviolet 1", "su1", "index", "uv_index"),
    Column("Wind Speed", "ws", "m/s", "wind_speed_ms"),
    Column("Wind Direction", "wd", "degrees", "wind_dir_deg"),
    Column("Wind Gust", "wg", "m/s", "wind_gust_ms"),
    Column("Wind Gust Direction", "wgd", "degrees", "wind_gust_dir_deg"),
    Column("Heat Index", "hi", "°C", "heat_index_fw_c"),
    Column("Wet Bulb Temperature", "wbt", "°C", "wet_bulb_fw_c"),
    Column("Wet Bulb Globe Temperature", "wbgt", "°C", "wbgt_fw_c"),
)

VARIABLES: tuple[str, ...] = tuple(c.name for c in VARIABLE_COLUMNS)
OBS_RAW_COLUMNS: tuple[str, ...] = ("station_id", "time_utc", *VARIABLES, "source_file")
CANONICAL_NAMES: dict[str, str] = {c.geocsv: c.name for c in (TIME, *VARIABLE_COLUMNS)}
GEOCSV_NAMES: dict[str, str] = {name: geocsv for geocsv, name in CANONICAL_NAMES.items()}

# Device codes are identifiers, not measurements: never averaged.
CODE_VARIABLES: tuple[str, ...] = ("health_code", "battery_status")

THERMOMETERS: tuple[str, ...] = ("t_bmx_c", "t_mcp_c", "t_sht_c")

CHANNEL_GROUPS: dict[str, tuple[str, ...]] = {
    "thermometers": THERMOMETERS,
    "humidity": ("rh_pct",),
    "pressure": ("p_station_hpa",),
    "rain_gauge_1": ("rain1_mm", "rain1_today_mm", "rain1_prior_mm"),
    "rain_gauge_2": ("rain2_mm", "rain2_today_mm", "rain2_prior_mm"),
    "light": ("light_vis_counts", "light_ir_counts", "uv_index"),
    "wind": ("wind_speed_ms", "wind_dir_deg", "wind_gust_ms"),
    "wind_gust_dir": ("wind_gust_dir_deg",),
    "battery": ("battery_voltage", "battery_status"),
    "comms": ("cell_signal",),
    "derived_fw": ("heat_index_fw_c", "wet_bulb_fw_c", "wbgt_fw_c"),
}

# Firmware-derived values are judged by the audit, not the health score (spec section 8).
SCORED_GROUPS: tuple[str, ...] = tuple(g for g in CHANNEL_GROUPS if g != "derived_fw")

GROUP_OF: dict[str, str] = {
    variable: group for group, members in CHANNEL_GROUPS.items() for variable in members
}


def qc_column(variable: str) -> str:
    return f"qc_{variable}"
