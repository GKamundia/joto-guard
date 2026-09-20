import json

from joto_guard.subscriptions import Subscriptions

LEVELS = ("normal", "acclimatized_only", "work_rest", "reschedule")


def test_a_new_file_starts_empty(tmp_path):
    people = Subscriptions.load(tmp_path / "subscriptions.json")

    assert people.all() == []


def test_subscribing_writes_the_file_straight_away(tmp_path):
    path = tmp_path / "subscriptions.json"
    people = Subscriptions.load(path)

    people.subscribe(42, "heavy")

    assert json.loads(path.read_text())["subscribers"][0]["work_type"] == "heavy"
    assert Subscriptions.load(path).get(42).work_type == "heavy"


def test_subscribing_again_changes_the_work_type_rather_than_adding_a_second(tmp_path):
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(42, "heavy")

    people.subscribe(42, "light")

    assert len(people.all()) == 1
    assert people.get(42).work_type == "light"


def test_unsubscribing_says_whether_there_was_anything_to_remove(tmp_path):
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(42, "heavy")

    assert people.unsubscribe(42) is True
    assert people.unsubscribe(42) is False
    assert people.all() == []


def test_the_first_alert_of_a_day_is_always_sent(tmp_path):
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(42, "heavy")

    assert people.needs_alert(42, "2026-09-20", "work_rest", LEVELS)


def test_the_same_warning_is_not_repeated_the_same_day(tmp_path):
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(42, "heavy")
    people.record_alert(42, "2026-09-20", "work_rest")

    assert not people.needs_alert(42, "2026-09-20", "work_rest", LEVELS)


def test_a_worsening_forecast_is_worth_saying_again(tmp_path):
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(42, "heavy")
    people.record_alert(42, "2026-09-20", "work_rest")

    assert people.needs_alert(42, "2026-09-20", "reschedule", LEVELS)


def test_an_easing_forecast_is_not(tmp_path):
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(42, "heavy")
    people.record_alert(42, "2026-09-20", "reschedule")

    assert not people.needs_alert(42, "2026-09-20", "work_rest", LEVELS)


def test_the_next_day_starts_again(tmp_path):
    people = Subscriptions.load(tmp_path / "s.json")
    people.subscribe(42, "heavy")
    people.record_alert(42, "2026-09-20", "work_rest")

    assert people.needs_alert(42, "2026-09-21", "work_rest", LEVELS)


def test_somebody_who_never_subscribed_is_never_alerted(tmp_path):
    people = Subscriptions.load(tmp_path / "s.json")

    assert not people.needs_alert(99, "2026-09-20", "reschedule", LEVELS)


def test_alerts_recorded_for_a_stranger_are_ignored(tmp_path):
    people = Subscriptions.load(tmp_path / "s.json")

    people.record_alert(99, "2026-09-20", "work_rest")

    assert people.all() == []


def test_the_file_survives_a_round_trip_with_its_alert_history(tmp_path):
    path = tmp_path / "s.json"
    people = Subscriptions.load(path)
    people.subscribe(1, "heavy")
    people.subscribe(2, "light")
    people.record_alert(1, "2026-09-20", "reschedule")

    again = Subscriptions.load(path)

    assert {person.chat_id for person in again.all()} == {1, 2}
    assert again.get(1).last_alert_level == "reschedule"
    assert again.get(2).last_alert_date is None
