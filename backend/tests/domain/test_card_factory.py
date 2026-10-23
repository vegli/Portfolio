from dataclasses import replace
from datetime import UTC, datetime
from random import Random
from uuid import UUID, uuid4

import pytest

from app.domain.card import CardRarity, CardTemplate
from app.domain.card_factory import CardFactory
from app.domain.effect import Effect, EffectDefinition, EffectRarity, EffectTrigger, EffectType
from app.domain.game_session import GamePhase, GameSession
from app.domain.question import Question


class ScriptedRandom(Random):
    def __init__(self, tickets=(), choices=(), counts=()):
        super().__init__(0)
        self.tickets = iter(tickets)
        self.choices = iter(choices)
        self.counts = iter(counts)
        self.ranges = []
        self.choice_sizes = []
        self.count_bounds = []

    def randrange(self, stop):
        self.ranges.append(stop)
        value = next(self.tickets)
        assert 0 <= value < stop
        return value

    def choice(self, seq):
        self.choice_sizes.append(len(seq))
        return seq[next(self.choices)]

    def randint(self, a, b):
        self.count_bounds.append((a, b))
        value = next(self.counts)
        assert a <= value <= b
        return value


def template(rarity=CardRarity.COMMON, positive=0, negative=0):
    return CardTemplate(uuid4(), rarity, 1, 5, positive, negative)


def definition(kind=EffectType.HP, rarity=EffectRarity.COMMON,
               trigger=EffectTrigger.CORRECT, cost=1, weight=1, value=10):
    return EffectDefinition(uuid4(), kind, value if trigger is EffectTrigger.CORRECT else -value,
                            trigger, rarity, cost, weight)


@pytest.mark.parametrize("ticket,expected", [
    (0, CardRarity.COMMON), (69, CardRarity.COMMON),
    (70, CardRarity.RARE), (89, CardRarity.RARE),
    (90, CardRarity.EPIC), (99, CardRarity.EPIC),
])
def test_rarity_boundaries(question: Question, ticket: int, expected: CardRarity) -> None:
    rng = ScriptedRandom([ticket], [0, 0])
    card = CardFactory(rng).draw([question], [template(r) for r in CardRarity], [], set())
    assert card.template.rarity is expected
    assert rng.ranges == [100]


@pytest.mark.parametrize("rarities,ticket,total,expected", [
    ((CardRarity.COMMON, CardRarity.EPIC), 69, 80, CardRarity.COMMON),
    ((CardRarity.COMMON, CardRarity.EPIC), 70, 80, CardRarity.EPIC),
    ((CardRarity.RARE, CardRarity.EPIC), 19, 30, CardRarity.RARE),
    ((CardRarity.RARE, CardRarity.EPIC), 20, 30, CardRarity.EPIC),
    ((CardRarity.COMMON, CardRarity.RARE), 70, 90, CardRarity.RARE),
    ((CardRarity.EPIC,), 9, 10, CardRarity.EPIC),
])
def test_rarity_renormalization(question, rarities, ticket, total, expected):
    rng = ScriptedRandom([ticket], [0, 0])
    card = CardFactory(rng).draw([question], [template(r) for r in rarities], [], frozenset())
    assert card.template.rarity is expected
    assert rng.ranges == [total]


@pytest.mark.parametrize("template_index", [0, 1, 2])
@pytest.mark.parametrize("question_index", [0, 1])
def test_uniform_template_and_question_choice(question, template_index, question_index):
    questions = [question, replace(question, id=uuid4())]
    templates = [template() for _ in range(3)] + [template(CardRarity.RARE)]
    rng = ScriptedRandom([0], [template_index, question_index])
    card = CardFactory(rng).draw(questions, templates, [], set())
    assert card.template is templates[template_index]
    assert card.question is questions[question_index]
    assert rng.choice_sizes == [3, 2]
    assert rng.ranges == [90]


def test_used_and_incompatible_questions_and_templates_excluded(question):
    used = replace(question, id=uuid4(), difficulty=1)
    compatible = replace(question, id=uuid4(), difficulty=4)
    common = replace(template(), min_difficulty=1, max_difficulty=1)
    rare = replace(template(CardRarity.RARE), min_difficulty=4, max_difficulty=4)
    rng = ScriptedRandom([0], [0, 0])
    card = CardFactory(rng).draw([used, question, compatible], [common, rare], [], {used.id})
    assert card.template is rare
    assert card.question is compatible
    assert rng.ranges == [20]


@pytest.mark.parametrize("mode", ["empty_questions", "empty_templates", "used", "incompatible"])
def test_no_card_without_consuming_randomness(question, mode):
    questions = [] if mode == "empty_questions" else [question]
    templates = [] if mode == "empty_templates" else [template()]
    if mode == "incompatible":
        templates = [replace(templates[0], min_difficulty=5, max_difficulty=5)]
    rng = ScriptedRandom()
    assert CardFactory(rng).draw(questions, templates, [], {question.id} if mode == "used" else set()) is None
    assert rng.ranges == []


@pytest.mark.parametrize("rarity,allowed", [
    (CardRarity.COMMON, (EffectRarity.COMMON,)),
    (CardRarity.RARE, (EffectRarity.RARE,)),
    (CardRarity.EPIC, (EffectRarity.RARE, EffectRarity.EPIC)),
])
def test_effect_rarity_restrictions(question, rarity, allowed):
    definitions = [definition(rarity=r, value=10 + i) for i, r in enumerate(EffectRarity)]
    for ticket, expected in enumerate(d for d in definitions if d.rarity in allowed):
        rng = ScriptedRandom([0, ticket], [0, 0], [1])
        card = CardFactory(rng).draw([question], [template(rarity, positive=10)], definitions, set())
        assert card.effects == (Effect(expected.type, expected.value, expected.trigger),)
        assert rng.ranges[-1] == len(allowed)


@pytest.mark.parametrize("ticket,expected_value", [(0, 10), (6, 10), (7, 20), (9, 20)])
def test_weighted_effect_boundaries(question, ticket, expected_value):
    definitions = [definition(weight=7), definition(weight=3, value=20)]
    rng = ScriptedRandom([0, ticket], [0, 0], [1])
    card = CardFactory(rng).draw([question], [template(positive=2)], definitions, set())
    assert card.effects[0].value == expected_value
    assert rng.ranges == [70, 10]
    assert rng.count_bounds == [(1, 1)]


def test_independent_budgets_distinct_types_and_remaining_cost_filter(question):
    definitions = [
        definition(cost=2), definition(cost=1, value=20),
        definition(EffectType.SCORE, cost=2), definition(EffectType.TIME, cost=1),
        definition(trigger=EffectTrigger.INCORRECT, cost=2),
        definition(EffectType.TIME, trigger=EffectTrigger.INCORRECT, cost=3),
    ]
    rng = ScriptedRandom([0, 0, 0, 0], [0, 0], [3, 1])
    card = CardFactory(rng).draw([question], [template(positive=3, negative=2)], definitions, set())
    assert [(e.type, e.trigger) for e in card.effects] == [
        (EffectType.HP, EffectTrigger.CORRECT), (EffectType.TIME, EffectTrigger.CORRECT),
        (EffectType.HP, EffectTrigger.INCORRECT),
    ]
    assert rng.ranges == [70, 4, 1, 1]
    assert rng.count_bounds == [(1, 3), (1, 1)]


@pytest.mark.parametrize("count", [1, 2, 3])
def test_uniform_target_count_and_unspent_budget(question, count):
    definitions = [definition(kind) for kind in EffectType]
    rng = ScriptedRandom([0] * (count + 1), [0, 0], [count])
    card = CardFactory(rng).draw([question], [template(positive=10)], definitions, set())
    assert len(card.effects) == count
    assert len({e.type for e in card.effects}) == count
    assert rng.count_bounds == [(1, 3)]


def test_zero_budgets_ignore_catalog_and_roll_nothing(question):
    rng = ScriptedRandom([0], [0, 0])
    card = CardFactory(rng).draw([question], [template()], [definition()], set())
    assert card.effects == ()
    assert rng.count_bounds == []


@pytest.mark.parametrize("trigger", list(EffectTrigger))
@pytest.mark.parametrize("reason", ["missing", "wrong_rarity", "too_expensive", "wrong_trigger"])
def test_infeasible_configuration_fails_before_randomness(question, trigger, reason):
    funded = template(positive=1 if trigger is EffectTrigger.CORRECT else 0,
                      negative=1 if trigger is EffectTrigger.INCORRECT else 0)
    effect = definition(trigger=trigger)
    definitions = {
        "missing": [], "wrong_rarity": [replace(effect, rarity=EffectRarity.EPIC)],
        "too_expensive": [replace(effect, cost=2)],
        "wrong_trigger": [definition(trigger=EffectTrigger.INCORRECT if trigger is EffectTrigger.CORRECT
                                     else EffectTrigger.CORRECT)],
    }[reason]
    rng = ScriptedRandom()
    with pytest.raises(ValueError, match=f"{funded.id}.*{trigger.value}"):
        CardFactory(rng).draw([question], [template(), funded], definitions, set())
    assert rng.ranges == []


def test_infeasible_but_question_ineligible_template_is_ignored(question):
    invalid = replace(template(positive=1), min_difficulty=5, max_difficulty=5)
    card = CardFactory(Random(0)).draw([question], [invalid, template()], [], set())
    assert card is not None


def test_seed_reproducibility_fresh_uuid_and_input_immutability(question):
    questions = [question, replace(question, id=uuid4()), replace(question, id=uuid4())]
    templates = [template(r, 3, 3) for r in CardRarity]
    definitions = [definition(kind, rarity, trigger) for kind in EffectType
                   for rarity in EffectRarity for trigger in EffectTrigger]
    used = {questions[0].id}
    snapshot = (questions.copy(), templates.copy(), definitions.copy(), used.copy())
    first, second = CardFactory(Random(42)), CardFactory(Random(42))
    for _ in range(10):
        a = first.draw(questions, templates, definitions, used)
        b = second.draw(questions, templates, definitions, used)
        assert (a.template, a.question, a.effects) == (b.template, b.question, b.effects)
        assert isinstance(a.id, UUID) and a.id.version == 4
        assert a.id != b.id
    assert (questions, templates, definitions, used) == snapshot


@pytest.mark.parametrize("catalog", ["questions", "templates", "effects"])
def test_duplicate_catalog_ids_rejected(question, catalog):
    questions, templates, effects = [question], [template()], [definition()]
    target = {"questions": questions, "templates": templates, "effects": effects}[catalog]
    target.append(target[0])
    with pytest.raises(ValueError, match="duplicate"):
        CardFactory(Random(0)).draw(questions, templates, effects, set())


@pytest.mark.parametrize("args", [
    (None, [], [], set()), ([None], [], [], set()),
    ([], None, [], set()), ([], [None], [], set()),
    ([], [], None, set()), ([], [], [None], set()),
    ([], [], [], []), ([], [], [], {"id"}),
])
def test_invalid_inputs(args):
    with pytest.raises(TypeError):
        CardFactory(Random(0)).draw(*args)


def test_invalid_rng():
    with pytest.raises(TypeError):
        CardFactory(None)


def test_generated_cards_integrate_with_session(question):
    questions = (question, replace(question, id=uuid4()))
    templates = (template(),)
    factory = CardFactory(Random(0))
    now = datetime(2026, 10, 23, tzinfo=UTC)
    session = GameSession(uuid4(), now)
    card = factory.draw(questions, templates, (), session.used_question_ids)
    active = session.activate(card, now=now)
    evaluated = active.submit_answer(card.id, card.question.correct_answer_id, now=now)
    next_card = factory.draw(questions, templates, (), evaluated.used_question_ids)
    assigned = evaluated.assign_next_card(next_card, now=now)
    assert assigned.phase is GamePhase.AWAITING_ANSWER
    assert len(assigned.used_question_ids) == 2
    assert assigned.last_answer_result is None
    assert factory.draw(questions, templates, (), assigned.used_question_ids) is None
