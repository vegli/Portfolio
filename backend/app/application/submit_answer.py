from uuid import UUID

from app.application.errors import InvalidAnswerOption, StaleCard
from app.application.models import AnswerSubmission, ExpiryPolicy, GameState
from app.application.ports import Clock, SessionRepository, SessionTokens
from app.application.session_access import require_phase, update_attempts
from app.domain.game_session import GamePhase, GameStatus


class SubmitAnswer:
    def __init__(self, sessions: SessionRepository, clock: Clock, tokens: SessionTokens) -> None:
        self.sessions, self.clock, self.tokens = sessions, clock, tokens

    async def execute(
        self, session_id: UUID, token: str, *, card_id: UUID, answer_option_id: UUID,
    ) -> AnswerSubmission:
        if not isinstance(card_id, UUID) or not isinstance(answer_option_id, UUID):
            raise TypeError("card and answer option IDs must be UUID values")
        async for stored in update_attempts(self.sessions, self.tokens, session_id, token):
            now = self.clock.now()
            session = stored.session.refresh(now=now)
            newly_finished = (stored.session.status is GameStatus.ACTIVE
                              and session.status is GameStatus.FINISHED)
            accepted = False
            if not newly_finished:
                require_phase(session, GamePhase.AWAITING_ANSWER)
                card = session.current_card
                assert card is not None
                if card.id != card_id:
                    raise StaleCard("Submitted card is not current")
                if answer_option_id not in {o.id for o in card.question.options}:
                    raise InvalidAnswerOption("Option does not belong to the current question")
                session = session.submit_answer(card_id, answer_option_id, now=now)
                accepted = True
            expiry = ExpiryPolicy.RENEW_ACTIVITY if accepted else ExpiryPolicy.PRESERVE
            if await self.sessions.compare_and_swap(
                session, expected_version=stored.version, expiry=expiry,
            ):
                return AnswerSubmission(GameState.from_session(session), accepted)
        raise AssertionError("update_attempts must raise after exhaustion")
