from dataclasses import replace

from app.domain.effect import Effect, EffectTrigger, EffectType
from app.domain.player import PlayerState


class EffectApplier:
    @staticmethod
    def apply(
        player: PlayerState,
        remaining_time_ms: int,
        is_correct: bool,
        effects: tuple[Effect, ...] | list[Effect] = (),
    ) -> tuple[PlayerState, int]:
        """Return replacement player state and time after matching HP/TIME effects."""
        if not isinstance(player, PlayerState):
            raise TypeError("player must be a PlayerState")
        if type(remaining_time_ms) is not int:
            raise TypeError("remaining time must be integer milliseconds")
        if remaining_time_ms < 0:
            raise ValueError("remaining time cannot be negative")
        if type(is_correct) is not bool:
            raise TypeError("is_correct must be a boolean")
        if not isinstance(effects, (tuple, list)):
            raise TypeError("effects must be a tuple or list of Effect values")

        trigger = EffectTrigger.CORRECT if is_correct else EffectTrigger.INCORRECT
        hp_delta = 0
        time_delta_seconds = 0
        for effect in effects:
            if not isinstance(effect, Effect):
                raise TypeError("effects must contain only Effect values")
            if effect.trigger is not trigger:
                continue
            if effect.type is EffectType.HP:
                hp_delta += effect.value
            elif effect.type is EffectType.TIME:
                time_delta_seconds += effect.value

        updated_player = replace(player, hp=player.hp + hp_delta)
        updated_time_ms = max(0, remaining_time_ms + time_delta_seconds * 1000)
        return updated_player, updated_time_ms
