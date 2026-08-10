"""Stage B: run a quiz against a candidate model and grade the answers."""

from __future__ import annotations

from collections import defaultdict
from string import Template
from typing import Any

from wolf_llm_labeling.quiz.grading import answer_question, grade_answer
from wolf_llm_labeling.quiz.models import (
    QuestionResult,
    Quiz,
    QuizSet,
)


def run_quiz(
    quiz: Quiz,
    answer_model: Any,
    judge_model: Any,
    answerer_system_prompt: str,
    judge_system_prompt: str,
) -> list[QuestionResult]:
    """Answer and grade every question in a single quiz."""
    results: list[QuestionResult] = []
    for question in quiz.questions:
        try:
            candidate = answer_question(
                answer_model, answerer_system_prompt, quiz.context, question.question
            )
            correct, graded_by, reason = grade_answer(
                question,
                candidate,
                judge_model,
                judge_system_prompt,
                judge_context=quiz.judge_context,
            )
        except Exception as exc:  # noqa: BLE001 - keep the batch alive on transient failures
            # Record the failure as an incorrect answer instead of aborting the
            # whole run/batch, so one flaky server call costs at most one question.
            candidate = ""
            correct = False
            graded_by = "error"
            reason = f"{type(exc).__name__}: {exc}"
        results.append(
            QuestionResult(
                id=question.id,
                type=question.type,
                question=question.question,
                acceptable_answers=list(question.acceptable_answers),
                candidate_answer=candidate,
                correct=correct,
                graded_by=graded_by,
                judge_reason=reason,
                category=question.category,
            )
        )
    return results


def summarize(results: list[QuestionResult]) -> dict[str, Any]:
    """Compute overall and per-type accuracy from graded results."""
    total = len(results)
    correct = sum(1 for r in results if r.correct)
    by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [correct, total]
    by_category: dict[str, list[int]] = defaultdict(
        lambda: [0, 0]
    )  # [correct, total]
    for r in results:
        by_type[r.type][1] += 1
        by_category[r.category][1] += 1
        if r.correct:
            by_type[r.type][0] += 1
            by_category[r.category][0] += 1

    def summarized(groups: dict[str, list[int]]) -> dict[str, dict[str, float | int]]:
        return {
            name: {
                "correct": counts[0],
                "total": counts[1],
                "accuracy": (counts[0] / counts[1]) if counts[1] else 0.0,
            }
            for name, counts in sorted(groups.items())
        }

    return {
        "total_questions": total,
        "correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "by_type": summarized(by_type),
        "by_category": summarized(by_category),
    }


def run_quiz_set(
    quiz_set: QuizSet,
    answer_model: Any,
    judge_model: Any,
    rules: str,
    answerer_system_template: str,
    judge_system_prompt: str,
    on_progress: Any = None,
) -> dict[str, Any]:
    """Run every quiz in a set and return a JSON-serializable result document.

    `answerer_system_template` may contain a `${rules}` placeholder that is filled
    with `rules`. `on_progress(quiz, index, total)` is called before each quiz if
    provided (useful for CLI logging).
    """
    answerer_system_prompt = Template(answerer_system_template).safe_substitute(
        rules=rules
    )
    resolved_judge_system_prompt = Template(judge_system_prompt).safe_substitute(
        rules=rules
    )

    quiz_reports: list[dict[str, Any]] = []
    all_results: list[QuestionResult] = []

    total = len(quiz_set.quizzes)
    for index, quiz in enumerate(quiz_set.quizzes, start=1):
        if on_progress is not None:
            on_progress(quiz, index, total)
        results = run_quiz(
            quiz,
            answer_model,
            judge_model,
            answerer_system_prompt,
            resolved_judge_system_prompt,
        )
        all_results.extend(results)
        quiz_reports.append(
            {
                "player_name": quiz.player_name,
                "phase_idx": quiz.phase_idx,
                "quiz_mode": quiz.quiz_mode,
                "hidden_phase_idx": quiz.hidden_phase_idx,
                "anchor_phase_idx": quiz.anchor_phase_idx,
                "summary": summarize(results),
                "results": [r.to_dict() for r in results],
            }
        )

    return {
        "source_game_file": quiz_set.source_game_file,
        "game_id": quiz_set.game_id,
        "overall_summary": summarize(all_results),
        "quizzes": quiz_reports,
    }
