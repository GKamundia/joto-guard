"""Daily station health score (spec section 8)."""

import pandas as pd

from .config import Config
from .qc import EPS, RULES, QCResult
from .schema import CHANNEL_GROUPS, GROUP_OF, SCORED_GROUPS, Flag, qc_column

STATUS_COLUMNS = ("station_id", "date_utc", "group", "status", "rules")
HEALTH_COLUMNS = (
    "station_id",
    "date_utc",
    "score",
    "bad_groups",
    "suspect_groups",
    "missing_minutes",
    "n_obs",
)


def record_days(obs: pd.DataFrame) -> pd.DatetimeIndex:
    """Every UTC day from the first to the last observation, as midnight timestamps."""
    if obs.empty:
        return pd.DatetimeIndex([], tz="UTC")
    times = obs["time_utc"]
    return pd.date_range(times.min().floor("D"), times.max().floor("D"), freq="D")


def group_status(qc: QCResult, config: Config) -> pd.DataFrame:
    """Status of every scored channel group on every day of the record.

    A group is bad when one of its channels is empty for the day (R12, which also covers
    days without any observations), when more than health.max_flagged_share of its rows
    are flagged bad, or when R13 fired. Otherwise it is suspect when that share of rows is
    flagged suspect or R11 fired. `rules` lists the rule ids behind the status.
    """
    obs = qc.obs
    days = record_days(obs)
    if days.empty:
        return pd.DataFrame(columns=list(STATUS_COLUMNS))

    day = obs["time_utc"].dt.floor("D")
    n_rows = day.value_counts().reindex(days, fill_value=0)
    fired = _rules_fired_by_group(qc.rule_hits)
    max_share = config.health.max_flagged_share
    station_id = int(obs["station_id"].iloc[0])

    records = []
    for group in SCORED_GROUPS:
        variables = list(CHANNEL_GROUPS[group])
        flags = obs[[qc_column(v) for v in variables]]
        bad_rows = (flags == Flag.BAD).any(axis=1).groupby(day).sum().reindex(days, fill_value=0)
        suspect_rows = (
            (flags == Flag.SUSPECT).any(axis=1).groupby(day).sum().reindex(days, fill_value=0)
        )
        present = obs[variables].notna().groupby(day).sum().reindex(days, fill_value=0)

        for moment in days:
            rows = n_rows[moment]
            rules = fired.get((group, moment.date()), set())

            bad = set()
            if rows == 0 or (present.loc[moment] == 0).any():
                bad.add("R12")
            if rows and bad_rows[moment] / rows > max_share + EPS:
                bad |= {r for r in rules if RULES[r].flag == Flag.BAD}
            if "R13" in rules:
                bad.add("R13")

            suspect = set()
            if not bad:
                if rows and suspect_rows[moment] / rows > max_share + EPS:
                    suspect |= {r for r in rules if RULES[r].flag == Flag.SUSPECT}
                if "R11" in rules:
                    suspect.add("R11")

            status = "bad" if bad else "suspect" if suspect else "good"
            records.append((station_id, moment.date(), group, status, sorted(bad or suspect)))

    table = pd.DataFrame(records, columns=list(STATUS_COLUMNS))
    return table.sort_values("date_utc", kind="stable", ignore_index=True)


def health_daily(qc: QCResult, status: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Daily health score: 100 minus penalties for bad and suspect groups and missing minutes."""
    obs = qc.obs
    days = record_days(obs)
    if days.empty:
        return pd.DataFrame(columns=list(HEALTH_COLUMNS))

    n_obs = obs["time_utc"].dt.floor("D").value_counts().reindex(days, fill_value=0)
    missing = missing_minutes_by_day(qc.gaps, days, config.station.expected_interval_s)
    groups_by_status = {
        label: status[status["status"] == label].groupby("date_utc")["group"].agg(list)
        for label in ("bad", "suspect")
    }
    weights = config.health
    station_id = int(obs["station_id"].iloc[0])

    records = []
    for moment in days:
        bad = groups_by_status["bad"].get(moment.date(), [])
        suspect = groups_by_status["suspect"].get(moment.date(), [])
        score = (
            100
            - weights.bad_group_penalty * len(bad)
            - weights.suspect_group_penalty * len(suspect)
            - missing[moment] / weights.missing_minutes_per_point
        )
        records.append(
            (
                station_id,
                moment.date(),
                round(max(0.0, score), 1),
                bad,
                suspect,
                round(missing[moment], 2),
                int(n_obs[moment]),
            )
        )
    return pd.DataFrame(records, columns=list(HEALTH_COLUMNS))


def missing_minutes_by_day(
    gaps: pd.DataFrame, days: pd.DatetimeIndex, expected_interval_s: float
) -> pd.Series:
    """Missing minutes charged to each UTC day.

    A gap's missing time runs from one expected interval after the last observation to the
    next observation; the part falling inside each day is charged to that day.
    """
    totals = pd.Series(0.0, index=days)
    one_day = pd.Timedelta(days=1)
    step = pd.Timedelta(seconds=expected_interval_s)
    for start, end in zip(gaps["gap_start_utc"], gaps["gap_end_utc"], strict=True):
        missing_from = start + step
        moment = missing_from.floor("D")
        while moment < end:
            minutes = (min(end, moment + one_day) - max(missing_from, moment)).total_seconds() / 60
            if minutes > 0 and moment in totals.index:
                totals.loc[moment] += minutes
            moment += one_day
    return totals


def _rules_fired_by_group(rule_hits: pd.DataFrame) -> dict[tuple[str, object], set[str]]:
    fired: dict[tuple[str, object], set[str]] = {}
    for rule_id, variable, day in rule_hits[["rule_id", "variable", "date_utc"]].itertuples(
        index=False
    ):
        group = GROUP_OF.get(variable)
        if group is not None:
            fired.setdefault((group, day), set()).add(rule_id)
    return fired
