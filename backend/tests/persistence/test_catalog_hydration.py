from uuid import uuid4

import pytest

from app.persistence.catalog import hydrate_question
from app.persistence.models import AnswerOption, Question


@pytest.fixture
def content():
    question = Question(id=uuid4(), text='Question?', category='databases', difficulty=2)
    options = [AnswerOption(id=uuid4(), question_id=question.id, text=f'Option {i}',
                            position=i, is_correct=i == 2) for i in range(1, 5)]
    return question, options


def test_hydration_maps_correct_answer_and_detaches(content):
    question, options = content
    result = hydrate_question(question, options)
    assert result.correct_answer_id == options[1].id
    assert [o.id for o in result.options] == [o.id for o in options]
    options[0].text = 'Changed'
    question.text = 'Changed'
    assert result.text == 'Question?'
    assert result.options[0].text == 'Option 1'


@pytest.mark.parametrize('case', [
    'missing', 'multiple_correct', 'no_correct', 'duplicate_position', 'wrong_owner',
    'invalid_uuid', 'blank_text', 'invalid_category', 'invalid_difficulty', 'invalid_boolean',
])
def test_hydration_rejects_invalid_rows(content, case):
    question, options = content
    if case == 'missing':
        options.pop()
    elif case == 'multiple_correct':
        options[0].is_correct = True
    elif case == 'no_correct':
        options[1].is_correct = False
    elif case == 'duplicate_position':
        options[0].position = 2
    elif case == 'wrong_owner':
        options[0].question_id = uuid4()
    elif case == 'invalid_uuid':
        question.id = 'bad'
    elif case == 'blank_text':
        options[0].text = ' '
    elif case == 'invalid_category':
        question.category = 'unknown'
    elif case == 'invalid_difficulty':
        question.difficulty = 6
    else:
        options[0].is_correct = 0
    with pytest.raises((ValueError, TypeError)):
        hydrate_question(question, options)
