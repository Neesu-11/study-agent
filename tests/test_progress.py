from datetime import date

from study_tutor.progress import ReviewState, apply_score, needs_revision


def test_first_success_schedules_a_short_review():
    state = apply_score(ReviewState(), 100, date(2026, 9, 29))
    assert state.status == "review"
    assert state.repetitions == 1
    assert state.interval_days == 1
    assert state.mastery == 100
    assert state.next_review == "2026-09-30"
    assert needs_revision(state, date(2026, 9, 29)) is False


def test_second_success_uses_a_three_day_gap():
    first = apply_score(ReviewState(), 90, date(2026, 9, 29))
    second = apply_score(first, 90, date(2026, 9, 30))
    assert second.repetitions == 2
    assert second.interval_days == 3
    assert second.next_review == "2026-10-03"


def test_low_score_is_due_for_revision():
    state = apply_score(ReviewState(), 40, date(2026, 9, 29))
    assert state.status == "weak"
    assert state.repetitions == 0
    assert state.interval_days == 1
    assert needs_revision(state, date(2026, 9, 29)) is True


def test_unstudied_topic_is_not_revision():
    assert needs_revision(ReviewState(), date(2026, 9, 29)) is False
