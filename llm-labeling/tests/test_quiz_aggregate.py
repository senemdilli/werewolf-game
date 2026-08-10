from __future__ import annotations

import math

import pytest

from wolf_llm_labeling.quiz.aggregate import (
    aggregate_run_reports,
    format_aggregate_markdown,
)


def _report(accuracy: float, by_type: dict, results: list[dict]) -> dict:
    by_category: dict[str, dict[str, float | int]] = {}
    for result in results:
        category = result.get("category", "objective")
        stats = by_category.setdefault(
            category, {"correct": 0, "total": 0, "accuracy": 0.0}
        )
        stats["total"] += 1
        if result["correct"]:
            stats["correct"] += 1
    for stats in by_category.values():
        stats["accuracy"] = stats["correct"] / stats["total"]

    return {
        "source_game_file": "game-test",
        "models": {"answer_model": "m", "judge_model": "j", "temperature": 0.7},
        "overall_summary": {
            "total_questions": len(results),
            "correct": sum(1 for r in results if r["correct"]),
            "accuracy": accuracy,
            "by_type": by_type,
            "by_category": by_category,
        },
        "quizzes": [{"player_name": "P", "phase_idx": 0, "results": results}],
    }


def test_aggregate_overall_mean_std() -> None:
    reports = [
        _report(1.0, {"t": {"accuracy": 1.0}}, [{"id": "q1", "type": "t", "correct": True}]),
        _report(0.0, {"t": {"accuracy": 0.0}}, [{"id": "q1", "type": "t", "correct": False}]),
    ]
    agg = aggregate_run_reports(reports)
    assert agg["num_runs"] == 2
    assert agg["overall"]["mean"] == pytest.approx(0.5)
    assert agg["overall"]["std"] == pytest.approx(0.5)
    assert agg["overall"]["min"] == 0.0
    assert agg["overall"]["max"] == 1.0


def test_aggregate_by_type_and_per_question() -> None:
    reports = [
        _report(
            0.5,
            {"seq": {"accuracy": 1.0}, "trap": {"accuracy": 0.0}},
            [
                {"id": "s1", "type": "seq", "correct": True},
                {"id": "t1", "type": "trap", "correct": False},
            ],
        ),
        _report(
            0.5,
            {"seq": {"accuracy": 1.0}, "trap": {"accuracy": 0.0}},
            [
                {"id": "s1", "type": "seq", "correct": True},
                {"id": "t1", "type": "trap", "correct": False},
            ],
        ),
    ]
    agg = aggregate_run_reports(reports)
    assert agg["by_type"]["seq"]["mean"] == pytest.approx(1.0)
    assert agg["by_type"]["seq"]["std"] == pytest.approx(0.0)
    assert agg["by_type"]["trap"]["mean"] == pytest.approx(0.0)
    assert agg["by_category"]["objective"]["mean"] == pytest.approx(0.5)
    # Per-question stability: s1 always correct, t1 never correct.
    assert agg["per_question"]["s1"]["correct_rate"] == pytest.approx(1.0)
    assert agg["per_question"]["t1"]["correct_rate"] == pytest.approx(0.0)
    assert agg["per_question"]["s1"]["runs"] == 2


def test_aggregate_empty_raises() -> None:
    with pytest.raises(ValueError):
        aggregate_run_reports([])


def test_format_markdown_contains_sections() -> None:
    reports = [
        _report(1.0, {"t": {"accuracy": 1.0}}, [{"id": "q1", "type": "t", "correct": True}]),
    ]
    agg = aggregate_run_reports(reports)
    agg["run_tag"] = "demo"
    md = format_aggregate_markdown(agg)
    assert "Overall accuracy" in md
    assert "Accuracy by question type" in md
    assert "Per-question stability" in md
    assert "demo" in md
