"""Spaced revision from quiz and practice scores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class ReviewState:
    mastery: float = 0.0
    ease: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0
    last_reviewed: str | None = None
    next_review: str | None = None
    status: str = "new"


def quality_from_percent(percent: float) -> int:
    if percent >= 90:
        return 5
    if percent >= 75:
        return 4
    if percent >= 60:
        return 3
    if percent >= 40:
        return 2
    if percent >= 20:
        return 1
    return 0


def apply_score(state: ReviewState, percent: float, today: date) -> ReviewState:
    """Update memory strength after a scored attempt.

    Scores under 60 percent schedule the topic for revision tomorrow.
    Passing scores follow a short SM-2 style interval: 1 day, 3 days,
    then interval times ease.
    """
    bounded = max(0.0, min(100.0, float(percent)))
    quality = quality_from_percent(bounded)
    ease = state.ease
    reps = state.repetitions
    interval = state.interval_days
    lapses = state.lapses

    if quality < 3:
        reps = 0
        interval = 1
        lapses += 1
        status = "weak"
    else:
        if reps <= 0:
            interval = 1
        elif reps == 1:
            interval = 3
        else:
            interval = max(1, round(interval * ease))
        reps += 1
        status = "review"

    ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease = max(1.3, ease)

    if state.last_reviewed is None and state.repetitions == 0:
        mastery = bounded
    else:
        mastery = round(state.mastery * 0.65 + bounded * 0.35, 1)

    if bounded < 60:
        status = "weak"

    return ReviewState(
        mastery=round(mastery, 1),
        ease=round(ease, 2),
        interval_days=interval,
        repetitions=reps,
        lapses=lapses,
        last_reviewed=today.isoformat(),
        next_review=(today + timedelta(days=interval)).isoformat(),
        status=status,
    )


def needs_revision(state: ReviewState, today: date) -> bool:
    if state.last_reviewed is None:
        return False
    if state.status == "weak" or state.mastery < 60:
        return True
    if state.next_review and date.fromisoformat(state.next_review) <= today and state.mastery < 85:
        return True
    return False


def topic_badge(state: ReviewState, today: date) -> str:
    if state.last_reviewed is None:
        return "new"
    label = str(round(state.mastery))
    if needs_revision(state, today):
        return f"{label} · revise"
    return label
