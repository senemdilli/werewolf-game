from __future__ import annotations

from pathlib import Path
from typing import Any

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.quiz.generate import generate_quiz_set
from wolf_llm_labeling.quiz.models import JudgeVerdict, QuestionResult
from wolf_llm_labeling.quiz.run_quiz import run_quiz_set, summarize


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
    def __init__(self, verdict: JudgeVerdict, calls: list[Any]) -> None:
        self.verdict = verdict
        self.calls = calls

    def invoke(self, messages: Any) -> JudgeVerdict:
        self.calls.append(messages)
        return self.verdict


class MockJudgeModel:
    def __init__(self, correct: bool) -> None:
        self.verdict = JudgeVerdict(correct=correct, reason="mock")
        self.calls: list[Any] = []

    def with_structured_output(self, schema: Any) -> _StructuredJudge:
        return _StructuredJudge(self.verdict, self.calls)

    def invoke(self, messages: Any) -> _Resp:  # pragma: no cover - not used
        return _Resp("")


def _quiz_set(tmp_path: Path):
    from game_record.conftest import write_export

    csv_path, labels_path = write_export(tmp_path)
    record = GameRecord()
    record.read_from_files([csv_path, labels_path])
    return generate_quiz_set(record, game_file="game-test", players=["Villager"])


def _hidden_quiz_set(tmp_path: Path):
    from game_record.conftest import write_export

    csv_path, labels_path = write_export(tmp_path)
    record = GameRecord()
    record.read_from_files([csv_path, labels_path])
    return generate_quiz_set(
        record,
        game_file="game-test",
        players=["Villager"],
        hidden_phases=[0],
    )


def test_summarize_counts() -> None:
    results = [
        QuestionResult("a", "t1", "q", [], "x", True, "exact"),
        QuestionResult("b", "t1", "q", [], "x", False, "judge"),
        QuestionResult("c", "t2", "q", [], "x", True, "judge"),
    ]
    summary = summarize(results)
    assert summary["total_questions"] == 3
    assert summary["correct"] == 2
    assert abs(summary["accuracy"] - 2 / 3) < 1e-9
    assert summary["by_type"]["t1"] == {"correct": 1, "total": 2, "accuracy": 0.5}
    assert summary["by_type"]["t2"] == {"correct": 1, "total": 1, "accuracy": 1.0}
    assert summary["by_category"]["objective"] == {
        "correct": 2,
        "total": 3,
        "accuracy": 2 / 3,
    }


def test_summarize_separates_objective_and_speculative() -> None:
    results = [
        QuestionResult("a", "t", "q", [], "x", True, "judge"),
        QuestionResult(
            "b",
            "t",
            "q",
            [],
            "x",
            False,
            "judge",
            category="speculative",
        ),
    ]
    summary = summarize(results)
    assert summary["by_category"]["objective"]["accuracy"] == 1.0
    assert summary["by_category"]["speculative"]["accuracy"] == 0.0


def test_run_quiz_set_all_correct(tmp_path: Path) -> None:
    quiz_set = _quiz_set(tmp_path)
    report = run_quiz_set(
        quiz_set,
        answer_model=MockAnswerModel("anything"),
        judge_model=MockJudgeModel(correct=True),
        rules="RULES-TEXT",
        answerer_system_template="System. ${rules}",
        judge_system_prompt="judge",
    )
    # Judge always says correct; exact matches also count -> everything correct.
    assert report["overall_summary"]["accuracy"] == 1.0
    assert report["quizzes"][0]["player_name"] == "Villager"
    assert report["overall_summary"]["total_questions"] > 0


def test_hidden_phase_run_separates_answerer_and_judge_contexts(
    tmp_path: Path,
) -> None:
    quiz_set = _hidden_quiz_set(tmp_path)
    answer_model = MockAnswerModel("reconstructed answer")
    judge_model = MockJudgeModel(correct=True)
    report = run_quiz_set(
        quiz_set,
        answer_model=answer_model,
        judge_model=judge_model,
        rules="RULES-TEXT",
        answerer_system_template="Answer rules: ${rules}",
        judge_system_prompt="Judge rules: ${rules}",
    )

    answer_human = answer_model.calls[0][1][1]
    judge_system, judge_human = judge_model.calls[0]
    assert "Night 1 begins." not in answer_human
    assert "Night 1 begins." in judge_human[1]
    assert judge_system == ("system", "Judge rules: RULES-TEXT")
    assert report["quizzes"][0]["quiz_mode"] == "hidden_phase"
    assert report["quizzes"][0]["hidden_phase_idx"] == 0


class _RaisingModel:
    def invoke(self, messages: Any) -> Any:
        raise TimeoutError("simulated server hang")


def test_run_quiz_set_survives_answer_model_errors(tmp_path: Path, monkeypatch) -> None:
    # Avoid real backoff sleeps during the retry attempts.
    monkeypatch.setattr("wolf_llm_labeling.quiz.grading.time.sleep", lambda *_: None)
    quiz_set = _quiz_set(tmp_path)
    report = run_quiz_set(
        quiz_set,
        answer_model=_RaisingModel(),
        judge_model=MockJudgeModel(correct=True),
        rules="RULES-TEXT",
        answerer_system_template="System. ${rules}",
        judge_system_prompt="judge",
    )
    # Every question fails gracefully instead of crashing the batch.
    assert report["overall_summary"]["correct"] == 0
    graded_by = {
        r["graded_by"] for q in report["quizzes"] for r in q["results"]
    }
    assert graded_by == {"error"}


def test_run_quiz_set_judge_false_only_exact_pass(tmp_path: Path) -> None:
    quiz_set = _quiz_set(tmp_path)
    report = run_quiz_set(
        quiz_set,
        answer_model=MockAnswerModel("zzz-unmatchable-zzz"),
        judge_model=MockJudgeModel(correct=False),
        rules="RULES-TEXT",
        answerer_system_template="System. ${rules}",
        judge_system_prompt="judge",
    )
    # Nothing exact-matches "zzz..." and the judge rejects everything.
    assert report["overall_summary"]["correct"] == 0
    assert report["overall_summary"]["accuracy"] == 0.0
