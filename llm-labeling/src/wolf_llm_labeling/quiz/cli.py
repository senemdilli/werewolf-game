"""CLI for the Werewolf game-comprehension quiz.

Two subcommands:

  generate  Build a quiz (JSON) from a game record. No LLM required.
  run       Answer + grade a quiz with a candidate model. Requires an LLM server.

Examples (run from the llm-labeling directory):

  python src/wolf_llm_labeling/quiz/cli.py generate \\
      --game game-44UT6Y-d59e923e.csv --player Blue --hidden-phase 4 \\
      --out quizzes/blue-h4.json

  python src/wolf_llm_labeling/quiz/cli.py run quizzes/blue-h4.json \\
      --primary-model gemma4:31b \\
      --ollama-url https://gpu.snet.tu-berlin.de/echelon/ollama
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

# Ensure src/ is importable when the script is run directly.
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

try:  # dotenv is only needed to pick up OLLAMA_API_KEY for the `run` command.
    from dotenv import load_dotenv

    _LLM_LABELING_ROOT = Path(__file__).resolve().parents[3]
    load_dotenv(_LLM_LABELING_ROOT / ".env")
except ImportError:
    pass

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.quiz.aggregate import (
    aggregate_run_reports,
    format_aggregate_markdown,
)
from wolf_llm_labeling.quiz.generate import generate_quiz_set
from wolf_llm_labeling.quiz.llm_setup import (
    DEFAULT_ANSWERER_SYSTEM,
    DEFAULT_JUDGE_SYSTEM,
    DEFAULT_RULES,
    build_chat_model,
    load_prompt,
)
from wolf_llm_labeling.quiz.models import QuizSet
from wolf_llm_labeling.quiz.run_quiz import run_quiz_set

_DEFAULT_GAME_DIR = _SRC_DIR.parent.parent / "results" / "game-records"
_DEFAULT_ANSWER_MODEL = "gemma4:31b"
_DEFAULT_JUDGE_MODEL = "mistral-large:123b-instruct-2411-q6_K"


def _resolve_game_paths(game: str, game_dir: str) -> tuple[Path, Path]:
    """Resolve a CSV/labels pair from a filename or path."""
    csv_path = Path(game)
    if not csv_path.exists():
        csv_path = Path(game_dir) / game
    if csv_path.suffix != ".csv":
        csv_path = csv_path.with_suffix(".csv")
    labels_path = csv_path.with_name(f"{csv_path.stem}-labels.json")
    return csv_path, labels_path


def cmd_generate(args: argparse.Namespace) -> None:
    csv_path, labels_path = _resolve_game_paths(args.game, args.game_dir)
    if not csv_path.exists():
        print(f"Error: could not find game CSV at {csv_path}", file=sys.stderr)
        sys.exit(1)

    record = GameRecord()
    record.read_from_files([labels_path, csv_path])

    all_players = list(record.get_players().keys())
    if args.player and not args.all_players:
        if args.player not in all_players:
            print(
                f"Error: player {args.player!r} not in game. Players: {all_players}",
                file=sys.stderr,
            )
            sys.exit(1)
        players = [args.player]
    else:
        players = all_players

    phase_count = record.get_phase_count()
    anchor_phase = (
        phase_count - 1 if args.anchor_phase is None else args.anchor_phase
    )
    if not 0 <= anchor_phase < phase_count:
        print(
            f"Error: anchor phase must be in 0..{phase_count - 1}",
            file=sys.stderr,
        )
        sys.exit(1)

    hidden_phases: list[int]
    if args.all_hidden_phases:
        hidden_phases = []
    else:
        if not 0 <= args.hidden_phase <= anchor_phase:
            print(
                f"Error: hidden phase must be in 0..{anchor_phase}",
                file=sys.stderr,
            )
            sys.exit(1)
        hidden_phases = [args.hidden_phase]

    quiz_set = generate_quiz_set(
        record,
        game_file=csv_path.stem,
        players=players,
        hidden_phases=hidden_phases,
        anchor_phase_idx=anchor_phase,
        chronology=args.chronology,
        list_style_mode=args.list_style,
    )

    num_questions = sum(len(q.questions) for q in quiz_set.quizzes)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(quiz_set.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"Wrote {len(quiz_set.quizzes)} quiz(zes) with {num_questions} questions "
        f"to {out_path}"
    )


def _print_run_summary(report: dict, answer_model: str, judge_model_name: str) -> None:
    summary = report["overall_summary"]
    print("\n=== Quiz results ===")
    print(f"Answer model: {answer_model}")
    print(f"Judge model:  {judge_model_name}")
    print(
        f"Overall: {summary['correct']}/{summary['total_questions']} correct "
        f"({summary['accuracy']:.1%})"
    )
    for category, stats in summary.get("by_category", {}).items():
        print(
            f"{category.title()}: {stats['correct']}/{stats['total']} correct "
            f"({stats['accuracy']:.1%})"
        )
    for qtype, stats in summary["by_type"].items():
        print(
            f"  - {qtype}: {stats['correct']}/{stats['total']} "
            f"({stats['accuracy']:.1%})"
        )


def cmd_run(args: argparse.Namespace) -> Path | list[Path]:
    quiz_path = Path(args.quiz_file)
    if not quiz_path.exists():
        print(f"Error: quiz file not found: {quiz_path}", file=sys.stderr)
        sys.exit(1)

    runs = max(1, int(getattr(args, "runs", 1)))

    quiz_set = QuizSet.from_dict(json.loads(quiz_path.read_text(encoding="utf-8")))

    request_timeout = getattr(args, "request_timeout", 300.0)
    if request_timeout is not None and request_timeout <= 0:
        request_timeout = None

    answer_model = build_chat_model(
        args.primary_model,
        args.ollama_url,
        temperature=args.temperature,
        request_timeout=request_timeout,
    )
    judge_model_name = args.judge_model or args.primary_model
    judge_model = build_chat_model(
        judge_model_name,
        args.ollama_url,
        temperature=0.0,
        request_timeout=request_timeout,
    )

    rules = load_prompt(args.rules_file, DEFAULT_RULES)
    answerer_system = load_prompt(args.answerer_prompt, DEFAULT_ANSWERER_SYSTEM)
    judge_system = load_prompt(args.judge_prompt, DEFAULT_JUDGE_SYSTEM)

    def on_progress(quiz, index: int, total: int) -> None:
        print(
            f"  [{index}/{total}] {quiz.player_name} hidden phase "
            f"{quiz.hidden_phase_idx if quiz.hidden_phase_idx is not None else quiz.phase_idx} "
            f"({len(quiz.questions)} questions)..."
        )

    def _one_run() -> dict:
        report = run_quiz_set(
            quiz_set,
            answer_model=answer_model,
            judge_model=judge_model,
            rules=rules,
            answerer_system_template=answerer_system,
            judge_system_prompt=judge_system,
            on_progress=on_progress,
        )
        report["models"] = {
            "answer_model": args.primary_model,
            "judge_model": judge_model_name,
            "ollama_url": args.ollama_url,
            "temperature": args.temperature,
        }
        return report

    # Single-run behaviour: preserve the original flat output layout.
    if runs == 1:
        report = _one_run()
        out_dir = Path(args.output_dir) / quiz_set.source_game_file
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"quiz-{uuid.uuid4().hex[:8]}.json"
        out_file.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        _print_run_summary(report, args.primary_model, judge_model_name)
        print(f"\nSaved detailed results to {out_file}")
        return out_file

    # Multi-run behaviour: group per-run files in a batch folder for aggregation.
    tag = getattr(args, "run_tag", None) or quiz_path.stem
    batch_dir = (
        Path(args.output_dir) / quiz_set.source_game_file / f"{tag}-x{runs}"
    )
    batch_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for run_idx in range(1, runs + 1):
        print(f"\n{'=' * 60}")
        print(f"Run {run_idx}/{runs}  ({tag})")
        print("=" * 60)
        report = _one_run()
        report["run_index"] = run_idx
        run_file = batch_dir / f"run-{run_idx:03d}.json"
        run_file.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        written.append(run_file)
        s = report["overall_summary"]
        print(
            f"  -> {s['correct']}/{s['total_questions']} ({s['accuracy']:.1%})  "
            f"saved {run_file.name}"
        )

    aggregate = aggregate_run_reports(
        [json.loads(p.read_text(encoding="utf-8")) for p in written]
    )
    aggregate["source_game_file"] = quiz_set.source_game_file
    aggregate["quiz_file"] = str(quiz_path)
    aggregate["run_tag"] = tag
    (batch_dir / "aggregate.json").write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (batch_dir / "aggregate.md").write_text(
        format_aggregate_markdown(aggregate), encoding="utf-8"
    )

    print(f"\n=== Aggregate over {runs} runs ({tag}) ===")
    ov = aggregate["overall"]
    print(
        f"Accuracy: mean {ov['mean']:.1%}  std {ov['std']:.1%}  "
        f"min {ov['min']:.1%}  max {ov['max']:.1%}"
    )
    for qtype, st in aggregate["by_type"].items():
        print(f"  - {qtype}: mean {st['mean']:.1%}  std {st['std']:.1%}")
    print(f"\nSaved {runs} run files + aggregate.json/aggregate.md to {batch_dir}")
    return written


def cmd_run_batch(args: argparse.Namespace) -> None:
    """Run the same quiz with many answer models; one fixed judge for all runs."""
    written: list[Path] = []
    for index, answer_model in enumerate(args.answer_models, start=1):
        print(f"\n{'=' * 60}")
        print(f"[{index}/{len(args.answer_models)}] Answer model: {answer_model}")
        print(f"Judge model: {args.judge_model}")
        print("=" * 60)
        batch_args = argparse.Namespace(
            quiz_file=args.quiz_file,
            primary_model=answer_model,
            ollama_url=args.ollama_url,
            judge_model=args.judge_model,
            temperature=args.temperature,
            rules_file=args.rules_file,
            answerer_prompt=args.answerer_prompt,
            judge_prompt=args.judge_prompt,
            output_dir=args.output_dir,
        )
        written.append(cmd_run(batch_args))

    print(f"\n=== Batch complete: {len(written)} result files ===")
    for path in written:
        print(f"  - {path}")


def cmd_aggregate(args: argparse.Namespace) -> None:
    """Aggregate a folder of per-run result files into mean/std statistics."""
    batch_dir = Path(args.batch_dir)
    if not batch_dir.is_dir():
        print(f"Error: not a directory: {batch_dir}", file=sys.stderr)
        sys.exit(1)

    run_files = sorted(batch_dir.glob("run-*.json"))
    if not run_files:
        # Fall back to any quiz-*.json (e.g. a folder of single-run results).
        run_files = sorted(batch_dir.glob("quiz-*.json"))
    if not run_files:
        print(f"Error: no run-*.json or quiz-*.json files in {batch_dir}", file=sys.stderr)
        sys.exit(1)

    reports = [json.loads(p.read_text(encoding="utf-8")) for p in run_files]
    aggregate = aggregate_run_reports(reports)
    aggregate["source_game_file"] = reports[0].get("source_game_file", "")
    aggregate["run_tag"] = args.run_tag or batch_dir.name

    (batch_dir / "aggregate.json").write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (batch_dir / "aggregate.md").write_text(
        format_aggregate_markdown(aggregate), encoding="utf-8"
    )

    ov = aggregate["overall"]
    print(f"=== Aggregate over {aggregate['num_runs']} runs ({batch_dir.name}) ===")
    print(
        f"Accuracy: mean {ov['mean']:.1%}  std {ov['std']:.1%}  "
        f"min {ov['min']:.1%}  max {ov['max']:.1%}"
    )
    for qtype, st in aggregate["by_type"].items():
        print(f"  - {qtype}: mean {st['mean']:.1%}  std {st['std']:.1%}")
    print(f"\nWrote aggregate.json + aggregate.md to {batch_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Werewolf game-comprehension quiz")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate a quiz from a game record")
    gen.add_argument("--game", required=True, help="Game CSV filename or path")
    gen.add_argument(
        "--game-dir",
        default=str(_DEFAULT_GAME_DIR),
        help="Directory to look for the game record in",
    )
    gen.add_argument("--player", default=None, help="Player name (default: all players)")
    gen.add_argument("--all-players", action="store_true", help="Generate for all players")
    hidden = gen.add_mutually_exclusive_group()
    hidden.add_argument(
        "--hidden-phase",
        "--phase",
        dest="hidden_phase",
        type=int,
        default=0,
        help="Zero-based phase index to omit and quiz (default: 0; --phase is an alias)",
    )
    hidden.add_argument(
        "--all-hidden-phases",
        "--all-phases",
        dest="all_hidden_phases",
        action="store_true",
        help="Generate one quiz for every phase in which the player is alive",
    )
    gen.add_argument(
        "--anchor-phase",
        type=int,
        default=None,
        help="Final phase visible to both models (default: last phase in the game)",
    )
    gen.add_argument(
        "--chronology",
        default="numeric",
        choices=["numeric", "timestamp"],
        help="Chronology formatting type",
    )
    gen.add_argument(
        "--list-style",
        default="plain",
        choices=["plain", "dash"],
        help="Enumeration style for Static Data / Current Game State lines "
        "(plain newline vs. '- ' bullets)",
    )
    gen.add_argument("--out", required=True, help="Output quiz JSON path")
    gen.set_defaults(func=cmd_generate)

    run = sub.add_parser("run", help="Run and grade a quiz with a candidate model")
    run.add_argument("quiz_file", help="Path to a quiz JSON produced by 'generate'")
    run.add_argument(
        "--primary-model",
        default=_DEFAULT_ANSWER_MODEL,
        help=f"Candidate (answering) model (default: {_DEFAULT_ANSWER_MODEL})",
    )
    run.add_argument("--ollama-url", required=True, help="Ollama / LM Studio base URL")
    run.add_argument(
        "--judge-model",
        default=_DEFAULT_JUDGE_MODEL,
        help=f"Judge model (default: {_DEFAULT_JUDGE_MODEL})",
    )
    run.add_argument("--temperature", type=float, default=0.0, help="Answering temperature")
    run.add_argument("--rules-file", default=None, help="Path to a rules text file")
    run.add_argument(
        "--answerer-prompt",
        default=None,
        help="Path to the answerer system prompt (may contain ${rules})",
    )
    run.add_argument(
        "--judge-prompt", default=None, help="Path to the judge system prompt"
    )
    run.add_argument(
        "--output-dir", default="./results/quiz", help="Base output directory"
    )
    run.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of repeated independent runs (default: 1). With >1, per-run "
        "files plus aggregate.json/aggregate.md are written to a batch folder.",
    )
    run.add_argument(
        "--run-tag",
        default=None,
        help="Name for the batch folder when --runs > 1 (default: quiz filename stem)",
    )
    run.add_argument(
        "--request-timeout",
        type=float,
        default=300.0,
        help="Per-request timeout in seconds (0 or negative disables; default: 300)",
    )
    run.set_defaults(func=cmd_run)

    batch = sub.add_parser(
        "run-batch",
        help="Run the same quiz with many answer models and one fixed judge",
    )
    batch.add_argument("quiz_file", help="Path to a quiz JSON produced by 'generate'")
    batch.add_argument(
        "--answer-models",
        nargs="+",
        required=True,
        help="Models that answer the questions (one run per model)",
    )
    batch.add_argument(
        "--judge-model",
        default=_DEFAULT_JUDGE_MODEL,
        help="Strong model that grades every answer "
        f"(default: {_DEFAULT_JUDGE_MODEL})",
    )
    batch.add_argument("--ollama-url", required=True, help="Ollama / LM Studio base URL")
    batch.add_argument("--temperature", type=float, default=0.0, help="Answering temperature")
    batch.add_argument("--rules-file", default=None, help="Path to a rules text file")
    batch.add_argument(
        "--answerer-prompt",
        default=None,
        help="Path to the answerer system prompt (may contain ${rules})",
    )
    batch.add_argument(
        "--judge-prompt", default=None, help="Path to the judge system prompt"
    )
    batch.add_argument(
        "--output-dir", default="./results/quiz", help="Base output directory"
    )
    batch.set_defaults(func=cmd_run_batch)

    agg = sub.add_parser(
        "aggregate",
        help="Aggregate a folder of per-run result files into mean/std stats",
    )
    agg.add_argument(
        "batch_dir",
        help="Folder containing run-*.json (or quiz-*.json) result files",
    )
    agg.add_argument(
        "--run-tag", default=None, help="Label for the aggregate (default: folder name)"
    )
    agg.set_defaults(func=cmd_aggregate)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
