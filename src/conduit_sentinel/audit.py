"""Derived-variable audits A01 to A05 (spec section 9)."""

from collections.abc import Iterable

import numpy as np
import pandas as pd

from .config import Config
from .qc import EPS, usable
from .thermo import nws_heat_index_c, stull_wet_bulb_c

AUDIT_COLUMNS = ("audit_id", "variable", "metric", "value", "n_rows", "verdict", "note")

THERMOMETER_PAIRS = (("t_sht_c", "t_mcp_c"), ("t_sht_c", "t_bmx_c"), ("t_bmx_c", "t_mcp_c"))

NO_DATA = "no usable rows"
REPORT_ONLY = "report only"

Metric = tuple[str, float | int | None, int]


def run_audits(obs_qc: pd.DataFrame, config: Config) -> pd.DataFrame:
    """audit_results: one row per audit metric. Rows flagged bad or missing are left out."""
    rows = [
        *audit_wet_bulb(obs_qc, config),
        *audit_heat_index(obs_qc),
        *audit_wbgt_below_wet_bulb(obs_qc, config),
        *audit_wbgt_standard(),
        *audit_thermometers(obs_qc),
    ]
    return pd.DataFrame(rows, columns=list(AUDIT_COLUMNS))


def audit_wet_bulb(obs_qc: pd.DataFrame, config: Config) -> list[dict]:
    """A01: firmware wet bulb against Stull (2011) applied to SHT temperature and humidity."""
    note = "Stull (2011) from SHT temperature and humidity"
    rows = _usable_rows(obs_qc, ("t_sht_c", "rh_pct", "wet_bulb_fw_c"))
    if rows.empty:
        return _results("A01", "wet_bulb_fw_c", [("mae_c", None, 0)], NO_DATA, note)

    diff = np.abs(rows["wet_bulb_fw_c"] - stull_wet_bulb_c(rows["t_sht_c"], rows["rh_pct"]))
    matches = diff.mean() <= config.audit.stull_max_mae_c + EPS
    metrics = [
        ("mae_c", round(diff.mean(), 3), len(rows)),
        ("max_abs_diff_c", round(diff.max(), 3), len(rows)),
    ]
    verdict = "matches Stull" if matches else "does not match Stull"
    return _results("A01", "wet_bulb_fw_c", metrics, verdict, note)


def audit_heat_index(obs_qc: pd.DataFrame) -> list[dict]:
    """A02: firmware heat index against the NWS heat index. Reported, not judged."""
    note = (
        "NWS heat index from SHT temperature and humidity; "
        "the NWS formula is designed for hot conditions"
    )
    rows = _usable_rows(obs_qc, ("t_sht_c", "rh_pct", "heat_index_fw_c"))
    if rows.empty:
        return _results("A02", "heat_index_fw_c", [("mae_c", None, 0)], NO_DATA, note)

    diff = np.abs(rows["heat_index_fw_c"] - nws_heat_index_c(rows["t_sht_c"], rows["rh_pct"]))
    metrics = [
        ("mae_c", round(diff.mean(), 3), len(rows)),
        ("max_abs_diff_c", round(diff.max(), 3), len(rows)),
    ]
    return _results("A02", "heat_index_fw_c", metrics, REPORT_ONLY, note)


def audit_wbgt_below_wet_bulb(obs_qc: pd.DataFrame, config: Config) -> list[dict]:
    """A03: share of rows where firmware WBGT is below the firmware wet bulb, day and night.

    Standard WBGT (0.7 natural wet bulb + 0.2 globe + 0.1 air temperature) stays at or
    above the wet bulb outside unusual radiative conditions, so a share above the
    tolerance points to a non-standard formula.
    """
    settings = config.audit
    start, end = settings.night_start_hour, settings.night_end_hour
    note = f"night is {start:02d}:00 to {end:02d}:59 {config.station.display_timezone}"
    rows = _usable_rows(obs_qc, ("wbgt_fw_c", "wet_bulb_fw_c"))
    if rows.empty:
        return _results("A03", "wbgt_fw_c", [("pct_below_wet_bulb", None, 0)], NO_DATA, note)

    below = rows["wbgt_fw_c"] < rows["wet_bulb_fw_c"] - EPS
    times = obs_qc.loc[rows.index, "time_utc"]
    night = is_night(times.dt.tz_convert(config.station.display_timezone).dt.hour, start, end)
    metrics = [
        ("rows_below_wet_bulb", int(below.sum()), len(below)),
        ("pct_below_wet_bulb", _pct(below), len(below)),
        ("pct_below_wet_bulb_night", _pct(below[night]), int(night.sum())),
        ("pct_below_wet_bulb_day", _pct(below[~night]), int((~night).sum())),
    ]
    non_standard = below.mean() > settings.wbgt_below_wet_bulb_max_share + EPS
    verdict = "non-standard" if non_standard else "within tolerance"
    return _results("A03", "wbgt_fw_c", metrics, verdict, note)


def audit_wbgt_standard() -> list[dict]:
    """A04: firmware WBGT against a standards-grade estimate. Waits for light calibration."""
    note = "needs solar irradiance in W/m²; the SI1145 light counts are not calibrated yet"
    return _results("A04", "wbgt_fw_c", [("diff_by_local_hour_c", None, 0)], "pending", note)


def audit_thermometers(obs_qc: pd.DataFrame) -> list[dict]:
    """A05: pairwise agreement of the SHT, BMX and MCP thermometers."""
    results = []
    for first, second in THERMOMETER_PAIRS:
        rows = _usable_rows(obs_qc, (first, second))
        pair = f"{first}-{second}"
        if rows.empty:
            results += _results("A05", pair, [("mean_abs_diff_c", None, 0)], NO_DATA, "")
            continue
        diff = (rows[first] - rows[second]).abs()
        metrics = [
            ("mean_abs_diff_c", round(diff.mean(), 3), len(rows)),
            ("max_abs_diff_c", round(diff.max(), 3), len(rows)),
        ]
        results += _results("A05", pair, metrics, REPORT_ONLY, "")
    return results


def is_night(local_hour: pd.Series, start: int, end: int) -> pd.Series:
    """True for hours inside [start, end], wrapping past midnight when start > end."""
    if start > end:
        return (local_hour >= start) | (local_hour <= end)
    return (local_hour >= start) & (local_hour <= end)


def _usable_rows(obs_qc: pd.DataFrame, variables: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame({v: usable(obs_qc, v) for v in variables}).dropna()


def _pct(mask: pd.Series) -> float | None:
    return round(float(mask.mean()) * 100, 1) if len(mask) else None


def _results(
    audit_id: str, variable: str, metrics: list[Metric], verdict: str, note: str
) -> list[dict]:
    return [
        {
            "audit_id": audit_id,
            "variable": variable,
            "metric": metric,
            "value": value,
            "n_rows": n_rows,
            "verdict": verdict,
            "note": note,
        }
        for metric, value, n_rows in metrics
    ]
