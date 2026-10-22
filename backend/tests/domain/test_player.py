from dataclasses import FrozenInstanceError

import pytest

from app.domain.player import PlayerState


def test_defaults() -> None:
    assert PlayerState() == PlayerState(hp=100, score=0, correct_streak=0)


@pytest.mark.parametrize("hp", [-20, 0, 150])
def test_hp_and_score_are_not_capped(hp: int) -> None:
    assert PlayerState(hp=hp, score=-50).hp == hp


def test_streak_cannot_be_negative() -> None:
    with pytest.raises(ValueError):
        PlayerState(correct_streak=-1)


@pytest.mark.parametrize("field", ["hp", "score", "correct_streak"])
@pytest.mark.parametrize("value", [True, 1.5, "1"])
def test_integer_values(field: str, value: object) -> None:
    with pytest.raises(TypeError):
        PlayerState(**{field: value})


def test_player_is_immutable() -> None:
    player = PlayerState()
    with pytest.raises(FrozenInstanceError):
        player.hp = 50
