"""CLI for the Werewolf game-comprehension quiz.

Two subcommands:

  generate  Build a quiz (JSON) from a game record. No LLM required.
  run       Answer + grade a quiz with a candidate model. Requires an LLM server.

Examples (run from the llm-labeling directory):

  python src/wolf_llm_labeling/quiz/cli.py generate \\
      --game game-44UT6Y-d59e923e.csv --player Blue --phase 0 \\
      --out quizzes/blue-p0.json

  python src/wolf_llm_labeling/quiz/cli.py run quizzes/blue-p0.json \\
      --primary-model gemma4:26b \\
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

    load_dotenv()
except ImportError:
    pass

from wolf_llm_labeling.game_records import GameRecord
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

    phases = None if args.all_phases else [args.phase]

    quiz_set = generate_quiz_set(
        record,
        game_file=csv_path.stem,
        players=players,
        phases=phases,
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


def cmd_run(args: argparse.Namespace) -> None:
    quiz_path = Path(args.quiz_file)
    if not quiz_path.exists():
        print(f"Error: quiz file not found: {quiz_path}", file=sys.stderr)
        sys.exit(1)

    quiz_set = QuizSet.from_dict(json.loads(quiz_path.read_text(encoding="utf-8")))

    answer_model = build_chat_model(
        args.primary_model, args.ollama_url, temperature=args.temperature
    )
    judge_model_name = args.judge_model or args.primary_model
    judge_model = build_chat_model(
        judge_model_name, args.ollama_url, temperature=0.0
    )

    rules = load_prompt(args.rules_file, DEFAULT_RULES)
    answerer_system = load_prompt(args.answerer_prompt, DEFAULT_ANSWERER_SYSTEM)
    judge_system = load_prompt(args.judge_prompt, DEFAULT_JUDGE_SYSTEM)

    def on_progress(quiz, index: int, total: int) -> None:
        print(
            f"  [{index}/{total}] {quiz.player_name} phase {quiz.phase_idx} "
            f"({len(quiz.questions)} questions)..."
        )

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

    out_dir = Path(args.output_dir) / quiz_set.source_game_file
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"quiz-{uuid.uuid4().hex[:8]}.json"
    out_file.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    summary = report["overall_summary"]
    print("\n=== Quiz results ===")
    print(
        f"Overall: {summary['correct']}/{summary['total_questions']} correct "
        f"({summary['accuracy']:.1%})"
    )
    for qtype, stats in summary["by_type"].items():
        print(
            f"  - {qtype}: {stats['correct']}/{stats['total']} "
            f"({stats['accuracy']:.1%})"
        )
    print(f"\nSaved detailed results to {out_file}")


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
    gen.add_argument("--phase", type=int, default=0, help="Phase index (default: 0)")
    gen.add_argument(
        "--all-phases",
        action="store_true",
        help="Generate for every phase the player is alive",
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
    run.add_argument("--primary-model", required=True, help="Candidate (answering) model")
    run.add_argument("--ollama-url", required=True, help="Ollama / LM Studio base URL")
    run.add_argument(
        "--judge-model",
        default=None,
        help="Judge model (default: same as --primary-model)",
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
    run.set_defaults(func=cmd_run)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
