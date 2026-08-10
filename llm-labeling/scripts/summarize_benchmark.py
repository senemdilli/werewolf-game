#!/usr/bin/env python
"""Collect all per-setup aggregate.json files into one comparison report.

Scans results/quiz/**/aggregate.json (produced by `quiz run --runs N` or
`quiz aggregate`) and prints:
  - an overall per-setup table (mean +/- std accuracy)
  - a format-effect table averaged across games (chronology x list style)
  - a per-question-type table across setups

Usage (from the llm-labeling directory):
  ./.venv/bin/python scripts/summarize_benchmark.py
  ./.venv/bin/python scripts/summarize_benchmark.py --results-dir results/quiz \
      --out results/quiz/BENCHMARK_SUMMARY.md
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path


def _parse_tag(tag: str) -> dict[str, str]:
    """Parse standard (`pN`) and hidden-phase (`hN`) benchmark tags."""
    info = {"player": "", "game": "", "chronology": "", "list_style": "", "tag": tag}
    for chrono in ("numeric", "timestamp"):
        for style in ("plain", "dash"):
            if tag.endswith(f"{chrono}-{style}"):
                info["chronology"] = chrono
                info["list_style"] = style
                head = tag[: -(len(chrono) + len(style) + 2)]
                break
        else:
            continue
        break
    m = re.match(r"([a-z]+)-[ph]\d+-([A-Za-z0-9]+)-", tag)
    if m:
        info["player"] = m.group(1)
        info["game"] = m.group(2)
    return info


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-dir", default="results/quiz")
    ap.add_argument("--out", default=None, help="Optional path to write the Markdown report")
    args = ap.parse_args()

    results_dir = Path(args.results_dir)
    agg_files = sorted(results_dir.rglob("aggregate.json"))
    if not agg_files:
        print(f"No aggregate.json files found under {results_dir}")
        return

    setups = []
    for p in agg_files:
        d = json.loads(p.read_text(encoding="utf-8"))
        tag = d.get("run_tag", p.parent.name)
        info = _parse_tag(tag)
        setups.append({
            "tag": tag,
            "game": info["game"],
            "player": info["player"],
            "chronology": info["chronology"],
            "list_style": info["list_style"],
            "num_runs": d.get("num_runs", 0),
            "overall": d["overall"],
            "by_type": d.get("by_type", {}),
            "models": d.get("models", {}),
        })

    setups.sort(key=lambda s: (s["game"], s["chronology"], s["list_style"]))

    lines: list[str] = []
    out = lines.append

    models = setups[0]["models"]
    out("# Context-format benchmark summary\n")
    out(f"- Answer model: `{models.get('answer_model', '?')}`")
    out(f"- Judge model: `{models.get('judge_model', '?')}`")
    out(f"- Temperature: {models.get('temperature', '?')}")
    out(f"- Setups: {len(setups)}")
    out("")

    # 1) Per-setup overall.
    out("## Per-setup accuracy (mean +/- std over N runs)\n")
    out("| Game | Player | Chronology | List style | Runs | Mean | Std | Min | Max |")
    out("|------|--------|-----------|-----------|------|------|-----|-----|-----|")
    for s in setups:
        ov = s["overall"]
        out(
            f"| {s['game']} | {s['player']} | {s['chronology']} | {s['list_style']} | "
            f"{s['num_runs']} | {_fmt_pct(ov['mean'])} | {_fmt_pct(ov['std'])} | "
            f"{_fmt_pct(ov['min'])} | {_fmt_pct(ov['max'])} |"
        )
    out("")

    # 2) Format effect averaged across games.
    out("## Format effect (mean accuracy averaged across games)\n")
    fmt_groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for s in setups:
        fmt_groups[(s["chronology"], s["list_style"])].append(s["overall"]["mean"])
    out("| Chronology | List style | Mean accuracy | (setups) |")
    out("|-----------|-----------|---------------|----------|")
    for (chrono, style), vals in sorted(fmt_groups.items()):
        mean = sum(vals) / len(vals)
        out(f"| {chrono} | {style} | {_fmt_pct(mean)} | {len(vals)} |")
    out("")

    # 3) Per question type across setups.
    out("## Accuracy by question type (mean per setup)\n")
    all_types: list[str] = []
    for s in setups:
        for t in s["by_type"]:
            if t not in all_types:
                all_types.append(t)
    all_types.sort()
    header = "| Setup | " + " | ".join(all_types) + " |"
    out(header)
    out("|" + "----|" * (len(all_types) + 1))
    for s in setups:
        cells = []
        for t in all_types:
            st = s["by_type"].get(t)
            cells.append(_fmt_pct(st["mean"]) if st else "-")
        out(f"| {s['tag']} | " + " | ".join(cells) + " |")
    out("")

    report = "\n".join(lines) + "\n"
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
