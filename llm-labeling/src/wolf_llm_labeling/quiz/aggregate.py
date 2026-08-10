"""Aggregate multiple quiz run reports into mean/std statistics.

A "run report" is the JSON document produced by `run_quiz_set` (see
`run_quiz.py`): it has an `overall_summary` with an `accuracy` and a `by_type`
map, plus `quizzes[].results[]` with per-question `correct` flags.

Aggregation computes, across N repeated runs of the *same* quiz:
  - overall accuracy: mean, std (population), min, max
  - per-question-type accuracy: mean, std across runs
  - per-question stability: fraction of runs in which each question was correct

No LLM or I/O here; this is pure data reduction so it is easy to unit-test.
"""

from __future__ import annotations

import math
from typing import Any


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    """Population standard deviation (ddof=0)."""
    if not values:
        return 0.0
    mu = _mean(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / len(values))


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": _mean(values),
        "std": _std(values),
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
        "n": len(values),
    }


def aggregate_run_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Reduce a list of run reports into aggregate statistics.

    Returns a JSON-serializable dict with `overall`, `by_type`, and
    `per_question` sections.
    """
    if not reports:
        raise ValueError("aggregate_run_reports requires at least one report")

    overall_acc = [r["overall_summary"]["accuracy"] for r in reports]

    # Collect per-type accuracy per run (types may vary slightly between runs,
    # though for repeats of one quiz they are identical).
    type_names: list[str] = []
    for r in reports:
        for qtype in r["overall_summary"].get("by_type", {}):
            if qtype not in type_names:
                type_names.append(qtype)

    by_type: dict[str, dict[str, float]] = {}
    for qtype in type_names:
        per_run = [
            r["overall_summary"]["by_type"][qtype]["accuracy"]
            for r in reports
            if qtype in r["overall_summary"].get("by_type", {})
        ]
        by_type[qtype] = _stats(per_run)

    category_names: list[str] = []
    for report in reports:
        for category in report["overall_summary"].get("by_category", {}):
            if category not in category_names:
                category_names.append(category)

    by_category: dict[str, dict[str, float]] = {}
    for category in category_names:
        per_run = [
            report["overall_summary"]["by_category"][category]["accuracy"]
            for report in reports
            if category in report["overall_summary"].get("by_category", {})
        ]
        by_category[category] = _stats(per_run)

    # Per-question stability: id -> fraction of runs correct.
    q_correct: dict[str, int] = {}
    q_total: dict[str, int] = {}
    q_meta: dict[str, dict[str, str]] = {}
    for r in reports:
        for quiz in r.get("quizzes", []):
            for res in quiz.get("results", []):
                qid = res["id"]
                q_total[qid] = q_total.get(qid, 0) + 1
                q_correct[qid] = q_correct.get(qid, 0) + (1 if res["correct"] else 0)
                q_meta.setdefault(
                    qid,
                    {
                        "type": res.get("type", ""),
                        "category": res.get("category", "objective"),
                        "question": res.get("question", ""),
                    },
                )

    per_question = {
        qid: {
            "type": q_meta[qid]["type"],
            "category": q_meta[qid]["category"],
            "correct_rate": q_correct[qid] / q_total[qid] if q_total[qid] else 0.0,
            "correct": q_correct[qid],
            "runs": q_total[qid],
        }
        for qid in q_total
    }

    return {
        "num_runs": len(reports),
        "models": reports[0].get("models", {}),
        "overall": _stats(overall_acc),
        "by_category": by_category,
        "by_type": by_type,
        "per_question": per_question,
    }


def format_aggregate_markdown(aggregate: dict[str, Any]) -> str:
    """Render an aggregate dict as a Markdown report ready to paste."""
    lines: list[str] = []
    tag = aggregate.get("run_tag", "")
    game = aggregate.get("source_game_file", "")
    models = aggregate.get("models", {})
    n = aggregate["num_runs"]

    lines.append(f"# Quiz aggregate — {tag}" if tag else "# Quiz aggregate")
    if game:
        lines.append(f"\n- Game: `{game}`")
    if models:
        lines.append(f"- Answer model: `{models.get('answer_model', '?')}`")
        lines.append(f"- Judge model: `{models.get('judge_model', '?')}`")
        lines.append(f"- Temperature: {models.get('temperature', '?')}")
    lines.append(f"- Runs: {n}")

    ov = aggregate["overall"]
    lines.append("\n## Overall accuracy\n")
    lines.append("| Runs | Mean | Std | Min | Max |")
    lines.append("|------|------|-----|-----|-----|")
    lines.append(
        f"| {n} | {ov['mean']:.1%} | {ov['std']:.1%} | {ov['min']:.1%} | {ov['max']:.1%} |"
    )

    if aggregate.get("by_category"):
        lines.append("\n## Accuracy by evidence category\n")
        lines.append("| Category | Mean | Std |")
        lines.append("|----------|------|-----|")
        for category, stats in aggregate["by_category"].items():
            lines.append(
                f"| {category} | {stats['mean']:.1%} | {stats['std']:.1%} |"
            )

    lines.append("\n## Accuracy by question type\n")
    lines.append("| Question type | Mean | Std |")
    lines.append("|---------------|------|-----|")
    for qtype, st in aggregate["by_type"].items():
        lines.append(f"| {qtype} | {st['mean']:.1%} | {st['std']:.1%} |")

    lines.append("\n## Per-question stability (fraction of runs correct)\n")
    lines.append("| Question | Type | Category | Correct rate |")
    lines.append("|----------|------|----------|--------------|")
    for qid, st in sorted(
        aggregate["per_question"].items(), key=lambda kv: kv[1]["correct_rate"]
    ):
        lines.append(
            f"| {qid} | {st['type']} | {st['category']} | "
            f"{st['correct_rate']:.0%} ({st['correct']}/{st['runs']}) |"
        )

    return "\n".join(lines) + "\n"
