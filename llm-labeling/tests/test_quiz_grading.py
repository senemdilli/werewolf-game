from __future__ import annotations

from typing import Any

from wolf_llm_labeling.quiz.grading import (
    answer_question,
    exact_match,
    grade_answer,
    judge,
    normalize,
)
from wolf_llm_labeling.quiz.models import JudgeVerdict, QuizQuestion


class _Resp:
    def __init__(self, content: str) -> None:
        self.content = content


class MockAnswerModel:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[Any] = []

    def invoke(self, messages: Any) -> _Resp:
        self.calls.append(messages)
        return _Resp(self.answer)


class _StructuredJudge:
    def __init__(self, verdict: JudgeVerdict) -> None:
        self.verdict = verdict

    def invoke(self, messages: Any) -> JudgeVerdict:
        return self.verdict


class MockJudgeModel:
    """Mock judge. If `verdict` is set, structured output is used; otherwise the
    plain-text fallback path is exercised via `.invoke`."""

    def __init__(self, verdict: JudgeVerdict | None = None, plain: str = "") -> None:
        self.verdict = verdict
        self.plain = plain
        self.invoked = False

    def with_structured_output(self, schema: Any) -> _StructuredJudge:
        if self.verdict is None:
            raise RuntimeError("structured output unsupported")
        return _StructuredJudge(self.verdict)

    def invoke(self, messages: Any) -> _Resp:
        self.invoked = True
        return _Resp(self.plain)


def test_normalize() -> None:
    assert normalize("  Hello, World! ") == "hello world"
    assert normalize("2. Conversation") == "2 conversation"


def test_exact_match_substring() -> None:
    assert exact_match(
        "It is 2. Conversation among players with role Werewolf",
        ["2. Conversation among players with role Werewolf"],
    )
    assert exact_match("Villager", ["Villager"])
    assert not exact_match("Wolf", ["Villager"])
    assert not exact_match("", ["Villager"])


def test_answer_question_passes_context() -> None:
    model = MockAnswerModel("the answer")
    out = answer_question(model, "sys", "ctx-body", "the question?")
    assert out == "the answer"
    # System + human tuples, with context and question embedded in the human turn.
    (system_role, _), (human_role, human_text) = model.calls[0]
    assert system_role == "system"
    assert human_role == "human"
    assert "ctx-body" in human_text and "the question?" in human_text


def test_judge_structured_output() -> None:
    model = MockJudgeModel(verdict=JudgeVerdict(correct=True, reason="matches"))
    correct, reason = judge(model, "sys", "q", ["Villager"], "villager")
    assert correct is True
    assert reason == "matches"
    assert model.invoked is False  # structured path, no plain fallback


def test_judge_text_fallback() -> None:
    model = MockJudgeModel(verdict=None, plain="INCORRECT - different player")
    correct, _ = judge(model, "sys", "q", ["Villager"], "Wolf")
    assert correct is False
    assert model.invoked is True

    model2 = MockJudgeModel(verdict=None, plain="Yes, this is correct.")
    correct2, _ = judge(model2, "sys", "q", ["Villager"], "villager")
    assert correct2 is True


def test_grade_answer_exact_short_circuits_judge() -> None:
    question = QuizQuestion(
        id="q1",
        type="self_role",
        question="role?",
        acceptable_answers=["Villager"],
        grading="auto",
    )
    judge_model = MockJudgeModel(verdict=JudgeVerdict(correct=False, reason="x"))
    correct, graded_by, _ = grade_answer(question, "Villager", judge_model, "sys")
    assert correct is True
    assert graded_by == "exact"
    assert judge_model.invoked is False


def test_grade_answer_judge_only_always_calls_judge() -> None:
    question = QuizQuestion(
        id="q2",
        type="mayor_vote_trap",
        question="did you vote?",
        acceptable_answers=["did not vote"],
        grading="judge_only",
    )
    judge_model = MockJudgeModel(verdict=JudgeVerdict(correct=True, reason="ok"))
    # Even though the candidate would exact-match, judge_only routes to the judge.
    correct, graded_by, reason = grade_answer(
        question, "did not vote", judge_model, "sys"
    )
    assert correct is True
    assert graded_by == "judge"
    assert reason == "ok"
