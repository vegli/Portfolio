from uuid import uuid4

import pytest

from app.domain.question import AnswerOption, Question, QuestionCategory


@pytest.fixture
def question() -> Question:
    options = tuple(AnswerOption(uuid4(), f"Option {i}") for i in range(4))
    return Question(
        id=uuid4(), text="Example question?",
        category=QuestionCategory.BACKEND_ENGINEERING,
        difficulty=3, options=options, correct_answer_id=options[0].id,
    )
