#!/usr/bin/env python
"""Collect hidden-phase benchmark results into a report table.

Scans results/quiz for run reports / aggregates matching the hidden-phase
matrix tags and writes a Markdown summary with:

  - per-setup overall / objective / speculative accuracy
  - role and phase-kind breakdowns

Usage (from the llm-labeling directory):
  ./.venv/bin/python scripts/summarize_hidden_phase_benchmark.py
  ./.venv/bin/python scripts/summarize_hidden_phase_benchmark.py \\
      --out results/quiz/HIDDEN_PHASE_REPORT.md
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

# Known matrix metadata keyed by short room code + player + hidden phase.
# Mirrors scripts/run_hidden_phase_benchmark.sh
MATRIX: dict[tuple[str, str, int], dict[str, str]] = {
    ("44UT6Y", "blue", 3): {"role": "Werewolf", "kind": "Morning", "game": "44UT6Y"},
    ("44UT6Y", "brown", 5): {"role": "Seer", "kind": "Evening", "game": "44UT6Y"},
    ("5NOHGS", "cyan", 0): {"role": "Witch", "kind": "Morning", "game": "5NOHGS"},
    ("5NOHGS", "white", 5): {"role": "Villager", "kind": "Evening", "game": "5NOHGS"},
    ("T5AVSL", "orange", 3): {"role": "Werewolf", "kind": "Morning", "game": "T5AVSL"},
    ("T5AVSL", "cyan", 5): {"role": "Seer", "kind": "Evening", "game": "T5AVSL"},
    ("928B2K", "yellow", 3): {"role": "Werewolf", "kind": "Morning", "game": "928B2K"},
    ("928B2K", "cyan", 5): {"role": "Villager", "kind": "Evening", "game": "928B2K"},
    ("VOKIJD", "green", 0): {"role": "Witch", "kind": "Morning", "game": "VOKIJD"},
    ("VOKIJD", "magenta", 8): {"role": "Villager", "kind": "Evening", "game": "VOKIJD"},
    ("CCUTH3", "beige", 3): {"role": "Werewolf", "kind": "Morning", "game": "CCUTH3"},
    ("CCUTH3", "purple", 5): {"role": "Seer", "kind": "Evening", "game": "CCUTH3"},
}

_TAG_RE = re.compile(
    r"^(?P<player>[a-z]+)-h(?P<hidden>\d+)-(?P<code>[A-Za-z0-9]+)-"
    r"(?P<chrono>numeric|timestamp)-(?P<style>plain|dash)"
)


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _load_setup_result(path: Path) -> dict | None:
    """Load either aggregate.json or a single quiz-*.json / run-*.json."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if "overall" in data and "by_category" in data:
        # Aggregate from --runs > 1
        return {
            "kind": "aggregate",
            "num_runs": data.get("num_runs", 0),
            "models": data.get("models", {}),
            "overall_acc": data["overall"]["mean"],
            "objective_acc": data.get("by_category", {}).get("objective", {}).get(
                "mean"
            ),
            "speculative_acc": data.get("by_category", {}).get("speculative", {}).get(
                "mean"
            ),
            "run_tag": data.get("run_tag", path.parent.name),
        }
    if "overall_summary" in data:
        summary = data["overall_summary"]
        by_cat = summary.get("by_category", {})
        return {
            "kind": "single",
            "num_runs": 1,
            "models": data.get("models", {}),
            "overall_acc": summary["accuracy"],
            "objective_acc": by_cat.get("objective", {}).get("accuracy"),
            "speculative_acc": by_cat.get("speculative", {}).get("accuracy"),
            "objective_correct": by_cat.get("objective", {}).get("correct"),
            "objective_total": by_cat.get("objective", {}).get("total"),
            "speculative_correct": by_cat.get("speculative", {}).get("correct"),
            "speculative_total": by_cat.get("speculative", {}).get("total"),
            "run_tag": path.stem,
            "source_game_file": data.get("source_game_file", ""),
        }
    return None


def _parse_tag(tag: str) -> dict[str, str | int] | None:
    # Strip trailing -xN from batch folder names.
    tag = re.sub(r"-x\d+$", "", tag)
    match = _TAG_RE.match(tag)
    if not match:
        return None
    return {
        "player": match.group("player"),
        "hidden": int(match.group("hidden")),
        "code": match.group("code"),
        "chrono": match.group("chrono"),
        "style": match.group("style"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-dir", default="results/quiz")
    ap.add_argument(
        "--out",
        default="results/quiz/HIDDEN_PHASE_REPORT.md",
        help="Markdown report path",
    )
    args = ap.parse_args()

    results_dir = Path(args.results_dir)
    rows: list[dict] = []

    # Prefer aggregates; otherwise take the newest single-run quiz JSON per tag.
    candidates: dict[str, tuple[float, Path]] = {}
    for path in sorted(results_dir.rglob("aggregate.json")):
        tag = path.parent.name
        parsed = _parse_tag(tag)
        if parsed is None:
            continue
        key = f"{parsed['player']}-h{parsed['hidden']}-{parsed['code']}"
        candidates[key] = (path.stat().st_mtime, path)

    for path in sorted(results_dir.rglob("quiz-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        quizzes = data.get("quizzes", [])
        if not quizzes:
            continue
        q0 = quizzes[0]
        if q0.get("quiz_mode") != "hidden_phase":
            continue
        player = str(q0.get("player_name", "")).lower()
        hidden = q0.get("hidden_phase_idx")
        source = data.get("source_game_file", "")
        code = source.split("-")[1] if source.count("-") >= 1 else ""
        if hidden is None or not player or not code:
            continue
        key = f"{player}-h{hidden}-{code}"
        mtime = path.stat().st_mtime
        if key not in candidates or mtime > candidates[key][0]:
            # Prefer aggregate if already present for this key.
            if key in candidates and candidates[key][1].name == "aggregate.json":
                continue
            candidates[key] = (mtime, path)

    for key, (_, path) in sorted(candidates.items()):
        loaded = _load_setup_result(path)
        if loaded is None:
            continue
        # Recover identity from path / payload.
        if path.name == "aggregate.json":
            parsed = _parse_tag(path.parent.name)
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            q0 = data["quizzes"][0]
            source = data.get("source_game_file", "")
            code = source.split("-")[1] if source.count("-") >= 1 else ""
            parsed = {
                "player": str(q0["player_name"]).lower(),
                "hidden": int(q0["hidden_phase_idx"]),
                "code": code,
                "chrono": "numeric",
                "style": "plain",
            }
        if parsed is None:
            continue
        meta = MATRIX.get(
            (str(parsed["code"]), str(parsed["player"]), int(parsed["hidden"]))
        )
        if meta is None:
            # Not part of the report matrix; skip.
            continue
        rows.append(
            {
                **loaded,
                **meta,
                "player": str(parsed["player"]).capitalize(),
                "hidden": int(parsed["hidden"]),
                "path": str(path),
            }
        )

    lines: list[str] = []
    out = lines.append
    out("# Hidden-phase comprehension benchmark\n")
    if not rows:
        out("No matching results found under the results directory.\n")
        Path(args.out).write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote empty report to {args.out}")
        return

    models = rows[0].get("models", {})
    out(f"- Answer model: `{models.get('answer_model', '?')}`")
    out(f"- Judge model: `{models.get('judge_model', '?')}`")
    out(f"- Temperature: {models.get('temperature', '?')}")
    out(f"- Setups found: {len(rows)} / 12")
    out("")

    out("## Per-setup accuracy\n")
    out(
        "| Game | Player | Role | Hidden phase | Kind | "
        "Objective | Speculative | Overall |"
    )
    out("|------|--------|------|--------------|------|-----------|-------------|---------|")
    for row in sorted(rows, key=lambda r: (r["game"], r["hidden"], r["player"])):
        obj = row["objective_acc"]
        spec = row["speculative_acc"]
        obj_s = _pct(obj) if obj is not None else "—"
        spec_s = _pct(spec) if spec is not None else "—"
        if row.get("objective_correct") is not None:
            obj_s = f"{row['objective_correct']}/{row['objective_total']} ({obj_s})"
        if row.get("speculative_correct") is not None and row.get(
            "speculative_total", 0
        ):
            spec_s = (
                f"{row['speculative_correct']}/{row['speculative_total']} ({spec_s})"
            )
        out(
            f"| {row['game']} | {row['player']} | {row['role']} | "
            f"h{row['hidden']} | {row['kind']} | {obj_s} | {spec_s} | "
            f"{_pct(row['overall_acc'])} |"
        )
    out("")

    # Role / kind means over objective accuracy.
    def mean_group(key: str) -> list[tuple[str, float, int]]:
        groups: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            if row["objective_acc"] is None:
                continue
            groups[row[key]].append(row["objective_acc"])
        return [
            (name, sum(vals) / len(vals), len(vals))
            for name, vals in sorted(groups.items())
        ]

    out("## Objective accuracy by role\n")
    out("| Role | Mean objective | Setups |")
    out("|------|----------------|--------|")
    for name, mean, n in mean_group("role"):
        out(f"| {name} | {_pct(mean)} | {n} |")
    out("")

    out("## Objective accuracy by phase kind\n")
    out("| Kind | Mean objective | Setups |")
    out("|------|----------------|--------|")
    for name, mean, n in mean_group("kind"):
        out(f"| {name} | {_pct(mean)} | {n} |")
    out("")

    obj_vals = [r["objective_acc"] for r in rows if r["objective_acc"] is not None]
    if obj_vals:
        out("## Headline\n")
        out(
            f"- Mean **objective** accuracy across {len(obj_vals)} setups: "
            f"**{_pct(sum(obj_vals) / len(obj_vals))}**"
        )
        spec_vals = [
            r["speculative_acc"] for r in rows if r["speculative_acc"] is not None
        ]
        if spec_vals:
            out(
                f"- Mean **speculative** accuracy across {len(spec_vals)} setups: "
                f"{_pct(sum(spec_vals) / len(spec_vals))}"
            )
        out("")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote report ({len(rows)} setups) to {out_path}")


if __name__ == "__main__":
    main()
