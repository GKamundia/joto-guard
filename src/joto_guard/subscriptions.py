"""Who has asked to be told, and what work they do.

A lookup tool waits to be opened. A warning has to arrive. This is the small amount of
state that turns one into the other: a chat id, the kind of work that chat cares about, and
the last day it was warned, so nobody is told the same thing twice.

It is a JSON file rather than a database, for the same reason the rest of the project has
no database: the whole service is a handful of files that a rerun rewrites, and one more
file is easier to inspect, back up and delete than a schema.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("data/subscriptions.json")


@dataclass
class Subscriber:
    chat_id: int
    work_type: str
    #: The local date of the last alert sent, so a spell is not reported every few hours.
    last_alert_date: str | None = None
    #: What the alert said, so a worsening forecast can be sent again on the same day.
    last_alert_level: str | None = None


@dataclass
class Subscriptions:
    """Everyone subscribed, kept in one file."""

    path: Path = DEFAULT_PATH
    people: dict[int, Subscriber] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_PATH) -> "Subscriptions":
        file = Path(path)
        if not file.is_file():
            return cls(path=file)
        raw = json.loads(file.read_text(encoding="utf-8"))
        people = {
            int(entry["chat_id"]): Subscriber(**{**entry, "chat_id": int(entry["chat_id"])})
            for entry in raw.get("subscribers", [])
        }
        return cls(path=file, people=people)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"subscribers": [asdict(person) for person in self.people.values()]}
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def subscribe(self, chat_id: int, work_type: str) -> Subscriber:
        """Add a chat, or change the work type of one already there."""
        person = self.people.get(chat_id)
        if person is None:
            person = Subscriber(chat_id=chat_id, work_type=work_type)
            self.people[chat_id] = person
        else:
            person.work_type = work_type
        self.save()
        return person

    def unsubscribe(self, chat_id: int) -> bool:
        """Remove a chat. Returns whether there was one to remove."""
        if self.people.pop(chat_id, None) is None:
            return False
        self.save()
        return True

    def get(self, chat_id: int) -> Subscriber | None:
        return self.people.get(chat_id)

    def all(self) -> list[Subscriber]:
        return list(self.people.values())

    def record_alert(self, chat_id: int, date: str, level: str) -> None:
        person = self.people.get(chat_id)
        if person is None:
            return
        person.last_alert_date = date
        person.last_alert_level = level
        self.save()

    def needs_alert(self, chat_id: int, date: str, level: str, levels: tuple[str, ...]) -> bool:
        """Should this chat be told about `level` on `date`?

        Once a day, unless the forecast has worsened since the last one, which is worth
        saying again.
        """
        person = self.people.get(chat_id)
        if person is None:
            return False
        if person.last_alert_date != date:
            return True
        if person.last_alert_level is None:
            return True
        return levels.index(level) > levels.index(person.last_alert_level)

    def to_dict(self) -> dict[str, Any]:
        return {"subscribers": [asdict(person) for person in self.people.values()]}
