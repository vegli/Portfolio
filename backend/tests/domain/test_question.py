from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest

from app.domain.question import Question, QuestionCategory


@pytest.mark.parametrize("difficulty", [1, 5])
def test_difficulty_boundaries(question: Question, difficulty: int) -> None:
    assert replace(question, difficulty=difficulty).difficulty == difficulty


@pytest.mark.parametrize("difficulty", [0, 6])
def test_invalid_difficulty(question: Question, difficulty: int) -> None:
    with pytest.raises(ValueError):
        replace(question, difficulty=difficulty)


@pytest.mark.parametrize("difficulty", [True, 2.5, "3"])
def test_difficulty_requires_integer(question: Question, difficulty: object) -> None:
    with pytest.raises(TypeError):
        replace(question, difficulty=difficulty)


def test_options_and_correct_answer(question: Question) -> None:
    for options in (question.options[:3], question.options + question.options[:1],
                    question.options[:3] + question.options[:1]):
        with pytest.raises(ValueError):
            replace(question, options=options)
    with pytest.raises(ValueError):
        replace(question, correct_answer_id=uuid4())


def test_question_owns_immutable_options(question: Question) -> None:
    options = list(question.options)
    copied = replace(question, options=options)
    options.clear()
    assert len(copied.options) == 4
    with pytest.raises(FrozenInstanceError):
        question.options[0].text = "Changed"
    with pytest.raises(FrozenInstanceError):
        question.difficulty = 4


def test_categories(question: Question) -> None:
    assert len(QuestionCategory) == 7
    for category in QuestionCategory:
        assert replace(question, category=category).category is category
    with pytest.raises(TypeError):
        replace(question, category="networking")
