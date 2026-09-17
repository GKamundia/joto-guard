"""Behaviour on the whole organiser folder, where the exports leave 5 to 10 Sep uncovered.

Spec section 11 covers the two overlapping exports; these checks cover the third one and
the space between them. They are skipped until the exports are in data/raw/organiser.
"""

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from conduit_sentinel.pipeline import run
from conduit_sentinel.qc import BETWEEN_EXPORTS, REPORTING_GAP

ORGANISER_DIR = Path(
    os.environ.get(
        "CONDUIT_ORGANISER_DIR",
        Path(__file__).resolve().parents[2] / "data" / "raw" / "organiser",
    )
)
EXPORTS = sorted(ORGANISER_DIR.glob("*.csv"))

pytestmark = pytest.mark.skipif(
    len(EXPORTS) < 3,
    reason="the three organiser exports are not in data/raw/organiser",
)

COVERED_DAYS = [date(2026, 8, 28) + timedelta(days=i) for i in range(8)] + [
    date(2026, 9, 11) + timedelta(days=i) for i in range(5)
]


@pytest.fixture(scope="module")
def sentinel(config):
    return run(EXPORTS, config)


def test_three_exports_merge_into_two_covered_periods(sentinel):
    assert len(sentinel.ingest.files) == 3
    assert len(sentinel.qc.obs) == 18364
    assert sentinel.ingest.coverage == (
        (pd.Timestamp("2026-08-28T00:00:25Z"), pd.Timestamp("2026-09-04T23:58:18Z")),
        (pd.Timestamp("2026-09-11T00:00:01Z"), pd.Timestamp("2026-09-15T23:58:29Z")),
    )


def test_days_no_export_covers_are_not_scored(sentinel):
    health = sentinel.health

    assert health["date_utc"].tolist() == COVERED_DAYS
    assert date(2026, 9, 5) not in set(health["date_utc"])
    assert (health["n_obs"] > 1000).all()


def test_the_space_between_exports_costs_nobody_score(sentinel):
    scores = dict(zip(sentinel.health["date_utc"], sentinel.health["score"], strict=True))

    # the last day of one export and the first of the next score like any other day
    assert scores[date(2026, 9, 4)] == 80.0
    assert scores[date(2026, 9, 11)] == 80.0
    assert sorted(set(scores.values())) == [78.0, 79.2, 80.0]


def test_gap_between_exports_is_kept_but_labelled(sentinel):
    gaps = sentinel.qc.gaps
    intervals = sentinel.qc.intervals

    assert gaps["kind"].tolist() == [REPORTING_GAP, BETWEEN_EXPORTS]
    assert gaps.loc[gaps["kind"] == REPORTING_GAP, "interval_s"].item() == 755
    assert (intervals.gaps, intervals.between_exports) == (1, 1)
    # the six days between exports must not pass as the station's reporting cadence
    assert intervals.max_s == 755


def test_report_lists_the_export_windows(sentinel):
    coverage = sentinel.report["coverage"]

    assert coverage["export_windows"] == [
        {"start_utc": "2026-08-28T00:00:25Z", "end_utc": "2026-09-04T23:58:18Z"},
        {"start_utc": "2026-09-11T00:00:01Z", "end_utc": "2026-09-15T23:58:29Z"},
    ]
    assert coverage["reporting_gaps"] == 1
    assert coverage["gaps_between_exports"] == 1
    assert len(coverage["daily"]) == len(COVERED_DAYS)
