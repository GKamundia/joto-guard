from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conduit_sentinel.config import load_config
from conduit_sentinel.schema import CODE_VARIABLES, OBS_RAW_COLUMNS, VARIABLES

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def config_path():
    return ROOT / "config" / "qc_rules.yaml"


@pytest.fixture(scope="session")
def config(config_path):
    return load_config(config_path)


@pytest.fixture(scope="session")
def fixtures_dir():
    return ROOT / "tests" / "fixtures"


def build_obs(n=60, start="2026-08-28T00:00:00Z", interval_s=60, offsets_s=None, **columns):
    """obs_raw rows that pass every QC rule. Keyword arguments replace whole columns.

    Temperature, humidity, pressure and wind vary slightly from row to row so that long
    tables do not trip the flat-line rules.
    """
    if offsets_s is None:
        offsets_s = np.arange(n) * interval_s
    step = np.arange(len(offsets_s))
    obs = pd.DataFrame(
        {
            "station_id": 61,
            "time_utc": pd.Timestamp(start) + pd.to_timedelta(offsets_s, unit="s"),
            "health_code": 0,
            "battery_voltage": 95.0,
            "battery_status": 3,
            "cell_signal": 100.0,
            "rain1_mm": 0.0,
            "rain2_mm": 0.0,
            "rain1_today_mm": 0.0,
            "rain2_today_mm": 0.0,
            "rain1_prior_mm": 0.0,
            "rain2_prior_mm": 0.0,
            "t_bmx_c": 20.0 + 0.1 * (step % 7),
            "p_station_hpa": 852.0 + 0.1 * (step % 3),
            "t_mcp_c": 20.2 + 0.1 * (step % 7),
            "t_sht_c": 20.4 + 0.1 * (step % 7),
            "rh_pct": 60.0 + 0.1 * (step % 5),
            "light_vis_counts": 300.0,
            "light_ir_counts": 300.0,
            "uv_index": 0.0,
            "wind_speed_ms": 1.0 + 0.1 * (step % 4),
            "wind_dir_deg": 90.0,
            "wind_gust_ms": 2.0 + 0.1 * (step % 4),
            "wind_gust_dir_deg": 180.0,
            "heat_index_fw_c": 20.4,
            "wet_bulb_fw_c": 15.0,
            "wbgt_fw_c": 16.0,
            "source_file": "fixture.csv",
        }
    )
    for name, values in columns.items():
        obs[name] = values
    for name in VARIABLES:
        dtype = "Int64" if name in CODE_VARIABLES else "float64"
        obs[name] = obs[name].astype(dtype)
    return obs[list(OBS_RAW_COLUMNS)]


@pytest.fixture
def make_obs():
    return build_obs
