class ApplicationError(Exception):
    """Expected application failure; transport mapping belongs to the API layer."""


class SessionUnavailable(ApplicationError):
    pass


class NoPlayableQuestions(ApplicationError):
    pass


class InvalidGamePhase(ApplicationError):
    pass


class GameAlreadyFinished(ApplicationError):
    pass


class StaleCard(ApplicationError):
    pass


class InvalidAnswerOption(ApplicationError):
    pass


class ConcurrentUpdate(ApplicationError):
    pass


class CatalogFailure(ApplicationError):
    pass


class PersistenceFailure(ApplicationError):
    pass
