"""Data models for the game-comprehension quiz.

Quizzes are plain data (dataclasses) so they serialize cleanly to/from JSON.
`JudgeVerdict` is a pydantic model because it is used as a structured-output
schema for the LLM judge.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import BaseModel, Field

# Grading strategies for a question:
#   "auto"       -> try deterministic string match first, fall back to LLM judge
#   "exact_only" -> deterministic string match only (never call the judge)
#   "judge_only" -> always use the LLM judge (for open-ended / paraphrased answers)
GradingMode = str


@dataclass
class QuizQuestion:
    """A single question with its accepted ground-truth answer(s)."""

    id: str
    type: str
    question: str
    acceptable_answers: list[str]
    grading: GradingMode = "auto"
    category: str = "objective"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuizQuestion":
        return cls(
            id=data["id"],
            type=data["type"],
            question=data["question"],
            acceptable_answers=list(data["acceptable_answers"]),
            grading=data.get("grading", "auto"),
            category=data.get("category", "objective"),
        )


@dataclass
class Quiz:
    """All questions about one game situation from one player's perspective.

    `context` is the exact rendered game context the candidate model will be
    shown. Hidden-phase quizzes additionally store the complete `judge_context`
    so answering and grading are fully self-contained and reproducible.
    """

    game_file: str
    game_id: str | None
    player_name: str
    phase_idx: int
    context: str
    quiz_mode: str = "standard"
    hidden_phase_idx: int | None = None
    anchor_phase_idx: int | None = None
    judge_context: str | None = None
    questions: list[QuizQuestion] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_file": self.game_file,
            "game_id": self.game_id,
            "player_name": self.player_name,
            "phase_idx": self.phase_idx,
            "context": self.context,
            "quiz_mode": self.quiz_mode,
            "hidden_phase_idx": self.hidden_phase_idx,
            "anchor_phase_idx": self.anchor_phase_idx,
            "judge_context": self.judge_context,
            "questions": [q.to_dict() for q in self.questions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Quiz":
        return cls(
            game_file=data["game_file"],
            game_id=data.get("game_id"),
            player_name=data["player_name"],
            phase_idx=data["phase_idx"],
            context=data["context"],
            quiz_mode=data.get("quiz_mode", "standard"),
            hidden_phase_idx=data.get("hidden_phase_idx"),
            anchor_phase_idx=data.get("anchor_phase_idx"),
            judge_context=data.get("judge_context"),
            questions=[QuizQuestion.from_dict(q) for q in data.get("questions", [])],
        )


@dataclass
class QuizSet:
    """A collection of quizzes, typically one game across players/phases."""

    source_game_file: str
    game_id: str | None
    quizzes: list[Quiz] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_game_file": self.source_game_file,
            "game_id": self.game_id,
            "quizzes": [q.to_dict() for q in self.quizzes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuizSet":
        return cls(
            source_game_file=data["source_game_file"],
            game_id=data.get("game_id"),
            quizzes=[Quiz.from_dict(q) for q in data.get("quizzes", [])],
        )


@dataclass
class QuestionResult:
    """The outcome of grading one question during a run."""

    id: str
    type: str
    question: str
    acceptable_answers: list[str]
    candidate_answer: str
    correct: bool
    graded_by: str  # "exact" | "judge"
    judge_reason: str = ""
    category: str = "objective"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class JudgeVerdict(BaseModel):
    """Structured-output schema for the LLM judge."""

    correct: bool = Field(
        description="True if the candidate answer matches ANY reference answer in meaning, otherwise false."
    )
    reason: str = Field(
        default="",
        description="A brief (one sentence) justification for the verdict.",
    )
