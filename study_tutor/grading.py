"""Score quiz answers without sending multiple-choice keys back to the model."""

from __future__ import annotations

import re

from study_tutor.schemas import QuizQuestion

_LETTERS = "abcdefghij"


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def mcq_is_correct(question: QuizQuestion, given: str) -> bool:
    response = _norm(given)
    if not response:
        return False
    key = _norm(question.answer)
    if response == key:
        return True
    for index, choice in enumerate(question.choices):
        letter = _LETTERS[index]
        choice_norm = _norm(choice)
        accepted = {
            letter,
            f"{letter})",
            f"{letter}.",
            f"{letter}. {choice_norm}",
            f"{letter}) {choice_norm}",
            choice_norm,
        }
        key_matches = key in accepted or key == letter or key == choice_norm
        if response in accepted and key_matches:
            return True
    if len(key) == 1 and key in _LETTERS:
        index = _LETTERS.index(key)
        if index < len(question.choices) and response == _norm(question.choices[index]):
            return True
    return False


def short_is_exact(expected: str, given: str) -> bool:
    answer = _norm(given)
    return bool(answer) and answer == _norm(expected)


def percent_correct(correct: int, total: int) -> int:
    if total <= 0:
        return 0
    return round(100 * correct / total)
