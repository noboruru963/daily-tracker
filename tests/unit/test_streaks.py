from datetime import date, datetime, timedelta

from app.models.habit import Habit
from app.models.record import Record

TODAY = date(2026, 10, 21)


def make_habit(*days_ago):
    """Habit (not saved) with one record per given offset, in days before TODAY."""
    habit = Habit(name='t', visual_model_type='graph')
    for n in days_ago:
        day = TODAY - timedelta(days=n)
        habit.records.append(Record(numerical_value=1, date=datetime(day.year, day.month, day.day, 9)))
    return habit


def test_no_records():
    h = make_habit()
    assert h.get_streak(TODAY) == 0
    assert h.get_best_streak(TODAY) == 0
    assert h.get_total_days(TODAY) == 0
    assert not h.is_done_today(TODAY)


def test_first_record_today_starts_streak():
    h = make_habit(0)
    assert h.get_streak(TODAY) == 1
    assert h.is_done_today(TODAY)


def test_each_new_day_adds_one():
    assert make_habit(0, 1).get_streak(TODAY) == 2
    assert make_habit(0, 1, 2).get_streak(TODAY) == 3


def test_same_day_records_count_once():
    h = make_habit(0, 0, 0, 1)
    assert h.get_streak(TODAY) == 2
    assert h.get_total_days(TODAY) == 2


def test_streak_survives_until_end_of_today():
    # Logged yesterday and the day before, nothing yet today
    h = make_habit(1, 2)
    assert h.get_streak(TODAY) == 2
    assert not h.is_done_today(TODAY)


def test_missed_a_full_day_resets():
    h = make_habit(2, 3, 4)
    assert h.get_streak(TODAY) == 0
    assert h.get_best_streak(TODAY) == 3


def test_gap_splits_streaks():
    h = make_habit(0, 1, 3, 4, 5, 6)
    assert h.get_streak(TODAY) == 2
    assert h.get_best_streak(TODAY) == 4


def test_future_records_are_ignored():
    h = make_habit(-1, -2)  # tomorrow and the day after
    assert h.get_streak(TODAY) == 0
    assert h.get_best_streak(TODAY) == 0
    assert h.get_total_days(TODAY) == 0


def test_backfilled_day_bridges_gap():
    # Yesterday was missing, then backfilled
    assert make_habit(0, 2).get_streak(TODAY) == 1
    assert make_habit(0, 1, 2).get_streak(TODAY) == 3
