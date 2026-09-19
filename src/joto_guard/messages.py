"""The guidance as short messages, for Telegram or any other text channel.

These are pure functions over the document `guidance.forecast_guidance` builds, so the bot
holds no heat logic of its own and the wording can be tested without a network or a token.
"""

from datetime import datetime, timedelta
from typing import Any

DEFAULT_WORK_TYPE = "heavy"

WORK_NAMES = {
    "light": "Light work",
    "moderate": "Moderate work",
    "heavy": "Heavy work",
    "very_heavy": "Very heavy work",
}

# What an hour above `normal` means in a list, where there is no room for the full sentence.
SHORT_LEVELS = {
    "acclimatized_only": "new workers need breaks",
    "work_rest": "work in spells",
    "reschedule": "move this work",
}


class NoGuidance(LookupError):
    """The forecast does not cover the hour or day asked for."""


def work_types(document: dict[str, Any]) -> list[str]:
    return list(document["work_types"])


def dates(document: dict[str, Any]) -> list[str]:
    return [day["date"] for day in document["days"]]


def start_message(document: dict[str, Any]) -> str:
    station = document["station"]["name"]
    return "\n".join(
        [
            "Joto Guard tells you when outdoor work around JKUAT, Juja gets too hot.",
            "",
            f"It reads the {station} weather station, rebuilds the wet bulb globe "
            "temperature from its own sensors, forecasts it three days ahead and checks it "
            "against NIOSH's heat limits for the type of work.",
            "",
            "/now — this hour",
            "/today — the rest of today",
            "/tomorrow — tomorrow",
            "",
            f"Add a type of work to any command, for example /today light. "
            f"Without one it answers for {WORK_NAMES[DEFAULT_WORK_TYPE].lower()}: "
            f"{', '.join(work_types(document))}.",
        ]
    )


def now_message(document: dict[str, Any], at: datetime, work_type: str) -> str:
    """Guidance for the forecast hour containing `at`."""
    hour = _hour_containing(document, at)
    advice = hour["by_work_type"][work_type]
    if advice["level"] is None:
        raise NoGuidance(f"no guidance for {hour['local_time']}")

    lines = [
        f"{_heading(document, work_type)} · {hour['local_time'][11:]}",
        "",
        _temperature(hour),
        document["levels"][advice["level"]],
        document["swahili"]["levels"][advice["level"]],
        "",
        f"Used to the heat: {_spell(advice['work_minutes_acclimatized'])}",
        f"New to the heat: {_spell(advice['work_minutes_new_workers'])}",
    ]
    if advice["level_if_high"] != advice["level"]:
        lines.append(f"Could reach: {document['levels'][advice['level_if_high']].lower()}")
    lines += ["", document["advice"]["water"], document["swahili"]["advice"]["water"]]
    return "\n".join(lines)


def day_message(
    document: dict[str, Any], date: str, work_type: str, after: datetime | None = None
) -> str:
    """A day's peak, the window needing breaks, and every hour above `normal`.

    `after` drops hours already past, so /today answers for the rest of the day.
    """
    day = next((item for item in document["days"] if item["date"] == date), None)
    summary = (day or {}).get("by_work_type", {}).get(work_type)
    if summary is None:
        raise NoGuidance(f"the forecast does not cover {date}")

    lines = [
        f"{_heading(document, work_type)} · {date}",
        "",
        f"Highest {summary['peak_wbgt_c']} °C WBGT at {summary['peak_time']}.",
    ]
    if summary["limited_from"]:
        lines.append(
            f"Workers used to the heat need breaks from {summary['limited_from']} "
            f"to {summary['limited_until']}."
        )
    elif summary["hours_acclimatized_only"]:
        lines.append(
            f"New workers need breaks for {summary['hours_acclimatized_only']} "
            f"of the day's {summary['hours']} hours."
        )
    else:
        lines.append("No heat limit is reached.")
    lines.append(document["swahili"]["levels"][summary["worst_level"]])

    watch = _hours_above_normal(document, date, work_type, after)
    if watch:
        lines += ["", "Hour by hour:"]
        lines += [f"  {_watch_line(hour, advice)}" for hour, advice in watch]
    return "\n".join(lines)


def _spell(minutes: int) -> str:
    """Minutes of work allowed in the hour, or that the work should wait when none are."""
    return f"{minutes} min of work in the hour." if minutes else "this work should wait."


def _watch_line(hour: dict[str, Any], advice: dict[str, Any]) -> str:
    """One hour on the watch list: what the level means, and the spell when it is shortened."""
    text = SHORT_LEVELS[advice["level"]]
    minutes = advice["work_minutes_acclimatized"]
    if minutes and minutes < 60:
        text = f"{text}, {minutes} min per hour"
    return f"{hour['local_time'][11:]}  {hour['wbgt_c']} °C  {text}"


def _heading(document: dict[str, Any], work_type: str) -> str:
    swahili = document["swahili"]["work_types"][work_type]
    return f"{WORK_NAMES.get(work_type, work_type)} ({swahili})"


def _temperature(hour: dict[str, Any]) -> str:
    if hour["wbgt_low_c"] is None:
        return f"WBGT {hour['wbgt_c']} °C."
    return f"WBGT {hour['wbgt_c']} °C, likely {hour['wbgt_low_c']} to {hour['wbgt_high_c']}."


def _hour_containing(document: dict[str, Any], at: datetime) -> dict[str, Any]:
    for hour in document["hours"]:
        start = _utc(hour)
        if start <= at < start + timedelta(hours=1):
            return hour
    raise NoGuidance(f"the forecast does not cover {at:%Y-%m-%d %H:%M} UTC")


def _utc(hour: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(hour["hour_utc"].replace("Z", "+00:00"))


def _hours_above_normal(
    document: dict[str, Any], date: str, work_type: str, after: datetime | None
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    watch = []
    for hour in document["hours"]:
        if not hour["local_time"].startswith(date):
            continue
        advice = hour["by_work_type"][work_type]
        if advice["level"] in (None, "normal"):
            continue
        if after is not None and _utc(hour) < after:
            continue
        watch.append((hour, advice))
    return watch
