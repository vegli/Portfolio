from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class QuestionCategory(StrEnum):
    BACKEND_ENGINEERING = "backend_engineering"
    DATABASES = "databases"
    NETWORKING = "networking"
    SYSTEM_DESIGN = "system_design"
    SECURITY = "security"
    DDD = "ddd"
    PERFORMANCE = "performance"


@dataclass(frozen=True)
class AnswerOption:
    id: UUID
    text: str


@dataclass(frozen=True)
class Question:
    id: UUID
    text: str
    category: QuestionCategory
    difficulty: int
    options: tuple[AnswerOption, ...]
    correct_answer_id: UUID

    def __post_init__(self) -> None:
        self._validate_category_and_difficulty()
        object.__setattr__(self, "options", tuple(self.options))
        self._validate_options()

    def _validate_category_and_difficulty(self) -> None:
        if not isinstance(self.category, QuestionCategory):
            raise TypeError("category must be a QuestionCategory")
        if type(self.difficulty) is not int:
            raise TypeError("difficulty must be an integer")
        if not 1 <= self.difficulty <= 5:
            raise ValueError("difficulty must be between 1 and 5")

    def _validate_options(self) -> None:
        if len(self.options) != 4:
            raise ValueError("a question must have exactly four options")
        option_ids = {option.id for option in self.options}
        if len(option_ids) != 4:
            raise ValueError("answer option IDs must be distinct")
        if self.correct_answer_id not in option_ids:
            raise ValueError("correct answer must belong to the question")
