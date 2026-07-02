"""CLI wrapper entry point for Werewolf trust labeling experiments."""

import argparse
import sys
from pathlib import Path
from typing import Any

# Ensure src is in python path
src_dir = Path(__file__).parents[1]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from dotenv import load_dotenv

load_dotenv()

from wolf_llm_labeling.runner import run_labeling_experiment
from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import LLMModelProviders
from wolf_llm_labeling.prompts import PromptSet
from wolf_llm_labeling.labeling import label_once


def run_example(llm_provider: Any, system_prompt: str, game_path: str, player_name: str) -> None:
    """Legacy/integration entry point."""
    record = GameRecord()
    record.read_from_files(game_path)
    
    models = LLMModelProviders(primary=llm_provider, inner_voice=llm_provider)
    prompt_set = PromptSet()
    prompt_set.prompts["labeling__system_prompt"] = system_prompt
    
    from wolf_llm_labeling.contexts import JoinedContext, StaticContext, GameNowContext, PhaseGameContext
    context = JoinedContext(
        "Game Context",
        None,
        100.0,
        StaticContext(player_name),
        GameNowContext(player_name),
        PhaseGameContext(offset=0),
    )
    
    labels, call_info = label_once(
        models=models,
        prompt_set=prompt_set,
        context=context,
        inner_voice=None,
        formatter_type="markdown",
        game_data=record,
        phase_idx=0
    )
    
    print("\n=== Trust Labeling Results ===")
    for target, label in labels.items():
        print(f"\nPlayer: {target}")
        print(f"Reasoning: {label.reasoning}")
        ts = label.trust_scores
        if ts.alignment:
            print(f"  - Alignment Trust: {ts.alignment.trust} (Confidence: {ts.alignment.confidence})")
        if ts.information:
            print(f"  - Information Trust: {ts.information.trust} (Confidence: {ts.information.confidence})")
        if ts.consistency:
            print(f"  - Consistency Trust: {ts.consistency.trust} (Confidence: {ts.consistency.confidence})")


def main():
    parser = argparse.ArgumentParser(description="LLM Werewolf Labeling Engine Runner")
    parser.add_argument("game_record_json", type=str, help="Path to game record JSON file")
    parser.add_argument("game_record_csv", type=str, help="Path to game record CSV file")
    
    parser.add_argument("--primary-model", required=True, type=str, help="Model for primary labeling agent")
    parser.add_argument("--inner-voice-model", type=str, help="Model for the inner voice (default: same as primary)")
    parser.add_argument("--ollama-url", required=True, type=str, help="URL of the Ollama server")
    parser.add_argument("--player-name", type=str, help="Player name or index to run labeling for (runs for all players if not specified)")
    parser.add_argument("--output-dir", type=str, default="./results/llm-labeling", help="Base output directory")
    parser.add_argument("--experiment", required=True, type=str, help="Experiment id e.g. a.py or b.py")
    parser.add_argument("--max-phases", type=int, default=0, help="Limit maximum number of phases to label (0 for infinite)")
    parser.add_argument("--experiment-args", type=str, default="", help="Config args for the experiment")
    parser.add_argument("--prompt-set", type=str, help="Path to prompt-set JSON configuration file")
    parser.add_argument("--prompt-dir", type=str, default="./prompts", help="Directory containing prompt files")
    parser.add_argument("--formatter", type=str, default="markdown", choices=["markdown", "json"], help="Context formatting type")
    parser.add_argument("--context-as-tool", action="store_true", help="Retrieve game context via tool call instead of pre-injecting it in prompt")
    parser.add_argument("--temperature", type=float, default=0.0, help="LLM generation temperature (default: 0.0)")
    parser.add_argument("--use-likert", action="store_true", help="Output trust evaluations on a Likert scale instead of integers")
    parser.add_argument("--runs", type=int, default=1, help="Number of times to run the labeling experiment (default: 1)")
    parser.add_argument("--chronology", type=str, default="numeric", choices=["numeric", "timestamp"], help="Chronology formatting type (default: numeric)")
    
    args = parser.parse_args()

    for run_idx in range(args.runs):
        if args.runs > 1:
            print(f"Starting Run {run_idx + 1} of {args.runs}: \n\n")

        run_labeling_experiment(
            game_record_json=args.game_record_json,
            game_record_csv=args.game_record_csv,
            primary_model=args.primary_model,
            inner_voice_model=args.inner_voice_model,
            ollama_url=args.ollama_url,
            player_name=args.player_name,
            output_dir=args.output_dir,
            experiment=args.experiment,
            max_phases=args.max_phases,
            experiment_args=args.experiment_args,
            prompt_set_path=args.prompt_set,
            prompt_dir=args.prompt_dir,
            formatter=args.formatter,
            context_as_tool=args.context_as_tool,
            temperature=args.temperature,
            use_likert=args.use_likert,
            chronology=args.chronology,
        )


if __name__ == "__main__":
    main()
