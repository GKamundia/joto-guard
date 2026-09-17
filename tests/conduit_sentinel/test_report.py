import json
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest

from conduit_sentinel.audit import run_audits
from conduit_sentinel.health import group_status, health_daily
from conduit_sentinel.ingest import IngestResult, Station
from conduit_sentinel.qc import apply_qc
from conduit_sentinel.report import build_report, score_rule_text, to_json_ready

STATION = Station(
    station_id=61,
    name="Kenya Kiambu JKUAT IOT AWS - Conduti@Empathy1",
    site="JKUAT",
    latitude=-1.099736,
    longitude=37.014528,
    elevation_m=1523.0,
    doi="10.5065/d6v1236q",
)

SECTIONS = [
    "sentinel_version",
    "generated_at_utc",
    "station",
    "coverage",
    "health",
    "channel_status",
    "thermometer_agreement",
    "rain",
    "light",
    "audits",
    "device_codes",
    "recommendations",
    "rules",
    "links",
]


def report_for(obs, config):
    ingested = IngestResult(
        obs=obs, station=STATION, files=(), duplicates_removed=0, conflicting_duplicates=0
    )
    qc = apply_qc(obs, config)
    status = group_status(qc, config)
    health = health_daily(qc, status, config)
    audits = run_audits(qc.obs, config)
    generated = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    return build_report(ingested, qc, health, status, audits, config, generated_at=generated)


@pytest.fixture
def troubled_station(make_obs):
    """A day and a bit of data showing every finding the report can recommend on."""
    n = 1500
    gust = [2.0 + 0.1 * (i % 4) for i in range(n)]
    return make_obs(
        n=n,
        battery_voltage=np.nan,
        rain1_mm=[0.2, 0.2] + [0.0] * (n - 2),
        wind_gust_ms=gust,
        wind_gust_dir_deg=gust,
        health_code=[33501705] + [0] * (n - 1),
        wbgt_fw_c=10.0,
    )


def test_report_has_every_section_and_is_plain_json(make_obs, config):
    report = report_for(make_obs(n=50), config)

    assert list(report) == SECTIONS
    assert report["generated_at_utc"] == "2026-09-17T12:00:00Z"
    json.dumps(report, allow_nan=False)


def test_station_card(make_obs, config):
    card = report_for(make_obs(n=50), config)["station"]

    assert card["station_id"] == 61
    assert card["doi"] == "10.5065/d6v1236q"
    assert card["record_start_utc"] == "2026-08-28T00:00:00Z"
    assert card["record_end_utc"] == "2026-08-28T00:49:00Z"
    assert card["n_obs"] == 50
    assert card["interval_s"] == {"median": 60.0, "min": 60.0, "max": 60.0}


def test_clean_station_gets_no_recommendations(make_obs, config):
    assert report_for(make_obs(n=50), config)["recommendations"] == []


def test_recommendations_follow_the_findings(troubled_station, config):
    recommendations = report_for(troubled_station, config)["recommendations"]

    assert [(r["evidence_level"], r["rules"]) for r in recommendations] == [
        ("suspected fault", ["R11"]),
        ("channel empty", ["R12"]),
        ("duplicated export column", ["R13"]),
        ("undocumented device code", ["R15"]),
        ("non-standard firmware value", ["A03", "R16"]),
    ]
    rain = recommendations[0]
    assert rain["title"] == "Confirm Rain Gauge 2 during the next rain"
    assert "on 1 day (2026-08-28)" in rain["detail"]
    assert "0.4 mm" in rain["detail"]
    assert "empty on 2 of 2 days with data" in recommendations[1]["detail"]


def test_health_section_prints_the_scoring_rule(troubled_station, config):
    report = report_for(troubled_station, config)

    assert report["health"]["rule"] == score_rule_text(config)
    assert report["health"]["daily"][0]["bad_groups"] == ["wind_gust_dir", "battery"]
    assert report["health"]["daily"][0]["suspect_groups"] == ["rain_gauge_2"]


def test_score_rule_text_uses_the_configured_weights(config):
    text = score_rule_text(config)

    assert "100 − 10 × bad groups − 2 × suspect groups − missing minutes ÷ 14.4" in text
    assert "more than 5 % of its rows" in text


def test_device_codes_are_listed_as_undocumented(troubled_station, config):
    codes = report_for(troubled_station, config)["device_codes"]

    assert codes["rows_with_code_zero"] == 1499
    assert codes["codes"] == [
        {
            "code": 33501705,
            "rows": 1,
            "first_utc": "2026-08-28T00:00:00Z",
            "last_utc": "2026-08-28T00:00:00Z",
            "days_seen": 1,
            "median_interval_before_s": None,
            "meaning": "undocumented",
        }
    ]


def test_rain_and_light_sections(troubled_station, config):
    report = report_for(troubled_station, config)

    assert report["rain"]["daily"][0] == {
        "date_utc": "2026-08-28",
        "rain1_mm": 0.4,
        "rain2_mm": 0.0,
    }
    assert report["rain"]["gauge_read_zero"] == [{"date_utc": "2026-08-28", "gauge": "rain2_mm"}]
    assert report["light"]["calibrated"] is False
    assert report["light"]["night_counts"]["light_vis_counts"] == {"median": 300.0, "min": 300.0}


def test_to_json_ready_converts_pandas_and_numpy_values():
    value = {
        "stamp": pd.Timestamp("2026-08-28T03:45:32Z"),
        "naive": datetime(2026, 8, 28, 3, 0),
        "day": date(2026, 8, 28),
        "count": np.int64(3),
        "share": np.float64(0.5),
        "nan": float("nan"),
        "missing": pd.NA,
        "flag": np.bool_(True),
        "list": (np.int8(1), None),
    }
    assert to_json_ready(value) == {
        "stamp": "2026-08-28T03:45:32Z",
        "naive": "2026-08-28T03:00:00Z",
        "day": "2026-08-28",
        "count": 3,
        "share": 0.5,
        "nan": None,
        "missing": None,
        "flag": True,
        "list": [1, None],
    }
