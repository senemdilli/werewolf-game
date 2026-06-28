"""Integration example and CLI wrapper for Werewolf trust labeling experiments."""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure src is in python path
src_dir = Path(__file__).parents[1]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.inner_voice import InnerVoice
from wolf_llm_labeling.labeling import label_once
from wolf_llm_labeling.models import LLMModelProviders, FormatterType, Label
from wolf_llm_labeling.prompts import PromptSet


def run_example(llm_provider: Any, system_prompt: str, game_path: str, player_name: str) -> None:
    """Legacy/integration entry point."""
    record = GameRecord()
    record.read_from_files(game_path)
    
    # Wrap llm_provider in LLMModelProviders
    models = LLMModelProviders(primary=llm_provider, inner_voice=llm_provider)
    
    # Setup dummy PromptSet
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
        if ts.strategic:
            print(f"  - Strategic Trust: {ts.strategic.trust} (Confidence: {ts.strategic.confidence})")
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
    
    args = parser.parse_args()

    token = os.getenv("OLLAMA_API_KEY")

    available_models = []
    try:
        import requests
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = requests.get(f"{args.ollama_url.rstrip('/')}/api/tags", headers=headers, timeout=5)
        if resp.status_code == 200:
            available_models = [m["name"] for m in resp.json().get("models", [])]
    except Exception as e:
        print(f"Warning: Could not connect to Ollama server at {args.ollama_url} to list available models: {e}")

    # Resolve inner voice model default
    iv_model = args.inner_voice_model if args.inner_voice_model else args.primary_model

    if available_models:
        if args.primary_model not in available_models:
            print(f"Error: primary model '{args.primary_model}' is not supported by the server. Available models: {available_models}", file=sys.stderr)
            sys.exit(1)
        if iv_model not in available_models:
            print(f"Error: inner voice model '{iv_model}' is not supported by the server. Available models: {available_models}", file=sys.stderr)
            sys.exit(1)

    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        try:
            from langchain_community.chat_models import ChatOllama
        except ImportError:
            print("Error: Neither langchain_ollama nor langchain_community is installed.", file=sys.stderr)
            sys.exit(1)

    primary_llm = ChatOllama(
        model=args.primary_model,
        temperature=0.0,
        base_url=args.ollama_url,
        client_kwargs={
            "headers": {
                "Authorization": f"Bearer {token}"
            }
        } if token else {}
    )

    inner_voice_llm = ChatOllama(
        model=iv_model,
        temperature=0.0,
        base_url=args.ollama_url,
        client_kwargs={
            "headers": {
                "Authorization": f"Bearer {token}"
            }
        } if token else {}
    )

    models = LLMModelProviders(primary=primary_llm, inner_voice=inner_voice_llm)

    game_record = GameRecord()
    try:
        game_record.read_from_files([args.game_record_json, args.game_record_csv])
    except Exception as e:
        print(f"Error loading game records: {e}", file=sys.stderr)
        sys.exit(1)

    prompt_set = PromptSet(prompt_dir=args.prompt_dir)
    if args.prompt_set:
        try:
            prompt_set.load(args.prompt_set)
        except Exception as e:
            print(f"Error loading prompt set JSON: {e}", file=sys.stderr)
            sys.exit(1)

    import importlib
    experiment_name = args.experiment.removesuffix(".py")
    try:
        exp_module = importlib.import_module(f"experiments.{experiment_name}")
    except ImportError as e:
        print(f"Error: Could not load experiment '{experiment_name}': {e}", file=sys.stderr)
        sys.exit(1)

    if not hasattr(exp_module, "experiment"):
        print(f"Error: Experiment '{experiment_name}' does not define an 'experiment' function.", file=sys.stderr)
        sys.exit(1)

    players = game_record.get_players()
    player_names = list(players.keys())

    target_players = []
    if args.player_name:
        val = args.player_name
        if val.isdigit():
            idx = int(val)
            if 0 <= idx < len(player_names):
                target_players = [player_names[idx]]
            else:
                print(f"Error: Invalid player index '{val}'. Players are: {player_names}", file=sys.stderr)
                sys.exit(1)
        else:
            if val in players:
                target_players = [val]
            else:
                print(f"Error: Invalid player name '{val}'. Players are: {player_names}", file=sys.stderr)
                sys.exit(1)
    else:
        target_players = player_names

    output_dir = Path(args.output_dir)
    game_id = game_record.get_game_id() or "unknown_game"
    base_out_path = output_dir / experiment_name / game_id
    base_out_path.mkdir(parents=True, exist_ok=True)

    written_files = []

    for player in target_players:
        total_phases = game_record.get_phase_count()
        alive_phases = 0
        phases_to_label = []
        
        for phase_idx in range(total_phases):
            status = game_record.get_player_status(phase_idx, player)
            if status.value in {"Alive", "Mayor"}:
                alive_phases += 1
                phases_to_label.append(phase_idx)

        if args.max_phases > 0:
            phases_to_label = phases_to_label[:args.max_phases]

        try:
            context_provider, inner_voice = exp_module.experiment(player, args.experiment_args, models)
        except Exception as e:
            print(f"Error setting up experiment '{experiment_name}' for player '{player}': {e}", file=sys.stderr)
            continue

        phase_results = []
        
        print(f"Labeling {len(phases_to_label)} phases for player '{player}'...")
        
        for idx, phase_idx in enumerate(phases_to_label, start=1):
            print(f"  [{idx}/{len(phases_to_label)}] Labeling phase {phase_idx}...")
            
            try:
                labels, call_info = label_once(
                    models=models,
                    prompt_set=prompt_set,
                    context=context_provider,
                    inner_voice=inner_voice,
                    formatter_type=args.formatter,
                    game_data=game_record,
                    phase_idx=phase_idx
                )
                
                inner_voice_calls = []
                messages = call_info.raw_response or []
                for m_idx, msg in enumerate(messages):
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            if tc.get("name") == "ask_inner_trust_voice":
                                t_id = tc.get("id")
                                t_args = tc.get("args")
                                t_resp = None
                                for other in messages[m_idx:]:
                                    if getattr(other, "tool_call_id", None) == t_id:
                                        t_resp = other.content
                                        break
                                inner_voice_calls.append({
                                    "request": t_args,
                                    "response": t_resp
                                })

                reasoning = None
                for msg in reversed(messages):
                    if type(msg).__name__ == "AIMessage" and msg.content:
                        reasoning = msg.content
                        break

                labels_out = {}
                for target_player, lbl in labels.items():
                    ts = lbl.trust_scores
                    labels_out[target_player] = {
                        "alignment": {
                            "trust": ts.alignment.trust,
                            "confidence": ts.alignment.confidence
                        } if ts.alignment else None,
                        "strategic": {
                            "trust": ts.strategic.trust,
                            "confidence": ts.strategic.confidence
                        } if ts.strategic else None,
                        "consistency": {
                            "trust": ts.consistency.trust,
                            "confidence": ts.consistency.confidence
                        } if ts.consistency else None,
                        "reasoning": lbl.reasoning
                    }

                phase_results.append({
                    "phase_idx": phase_idx,
                    "context": call_info.context,
                    "inner_voice": inner_voice_calls,
                    "labels": labels_out,
                    "reasoning": reasoning
                })
            except Exception as e:
                print(f"    Error in phase {phase_idx}: {e}", file=sys.stderr)

        run_data = {
            "player_name": player,
            "models": {
                "primary_model": args.primary_model,
                "inner_voice_model": iv_model if iv_model != args.primary_model else None
            },
            "prompts": prompt_set.raw_mapping,
            "time": datetime.utcnow().isoformat() + "Z",
            "experiment": experiment_name,
            "formatter": args.formatter,
            "experiment_args": args.experiment_args,
            "total_phases": total_phases,
            "alive_phases": alive_phases,
            "phases": phase_results
        }

        if run_data["models"]["inner_voice_model"] is None:
            del run_data["models"]["inner_voice_model"]

        out_file = base_out_path / f"{player}-{uuid.uuid4().hex[:8]}.json"
        with open(out_file, "w", encoding="utf-8") as out_f:
            json.dump(run_data, out_f, indent=2)
            
        written_files.append(str(out_file))
        print(f"Saved labeling results for player '{player}' to {out_file}")

    print("\nLabeling run complete")
    print(f"Total files written: {len(written_files)}")
    for f in written_files:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
