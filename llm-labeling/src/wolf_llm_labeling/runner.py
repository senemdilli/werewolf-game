"""Orchestration and execution runner for Werewolf trust labeling experiments."""

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.inner_voice import InnerVoice
from wolf_llm_labeling.labeling import label_once
from wolf_llm_labeling.models import LLMModelProviders, FormatterType, Label
from wolf_llm_labeling.prompts import PromptSet


def run_labeling_experiment(
    game_record_json: str,
    game_record_csv: str,
    primary_model: str,
    ollama_url: str,
    experiment: str,
    inner_voice_model: str | None = None,
    player_name: str | None = None,
    output_dir: str = "./results/llm-labeling",
    max_phases: int = 0,
    experiment_args: str = "",
    prompt_set_path: str | None = None,
    prompt_dir: str = "./prompts",
    formatter: FormatterType = "markdown",
    context_as_tool: bool = False,
    temperature: float = 0.0,
    use_likert: bool = False,
    likert_type: str = "agree-disagree",
    chronology: str = "numeric",
    list_style_mode: str = "plain",
) -> list[str]:
    """Execute a labeling experiment for game records and save the results."""
    from wolf_llm_labeling.models import chronology_type, list_style
    chronology_type.set(chronology)
    list_style.set(list_style_mode)
    
    token = os.getenv("OLLAMA_API_KEY")

    # Check if LM Studio is used
    is_openai = "1234" in ollama_url or "/v1" in ollama_url

    available_models = []
    if not is_openai:
        try:
            import requests
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            resp = requests.get(f"{ollama_url.rstrip('/')}/api/tags", headers=headers, timeout=5)
            if resp.status_code == 200:
                available_models = [m["name"] for m in resp.json().get("models", [])]
            else:
                print(f"Warning: Ollama server returned status code {resp.status_code} when querying models.", file=sys.stderr)
        except Exception as e:
            print(f"Error: The Ollama server at '{ollama_url}' is offline or unreachable.", file=sys.stderr)
            print(f"Details: {e}", file=sys.stderr)
            print("Please check your network connection or server status. Exiting early", file=sys.stderr)
            sys.exit(1)

    iv_model = inner_voice_model if inner_voice_model else primary_model

    # Auto-detect available models for Ollama if key words are used
    if available_models:
        first_model = available_models[0]
        if primary_model in ("ollama-model", "any", "default"):
            print(f"Auto-detected active Ollama primary model: {first_model}")
            primary_model = first_model
        if iv_model in ("ollama-model", "any", "default"):
            print(f"Auto-detected active Ollama inner voice model: {first_model}")
            iv_model = first_model

    if is_openai:
        try:
            import requests
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            resp = requests.get(f"{ollama_url.rstrip('/')}/models", headers=headers, timeout=5)
            if resp.status_code == 200:
                models_data = resp.json().get("data", [])
                if models_data:
                    loaded_model = models_data[0]["id"]
                    print(f"Auto-detected active LM Studio model: {loaded_model}")
                    if primary_model in ("lm-studio-model", "any", "default"):
                        primary_model = loaded_model
                    if iv_model in ("lm-studio-model", "any", "default"):
                        iv_model = loaded_model
        except Exception as e:
            print(f"Warning: Could not query active LM Studio model: {e}", file=sys.stderr)

    if available_models:
        if primary_model not in available_models:
            print(f"Error: primary model '{primary_model}' is not supported by the server. Available models: {available_models}", file=sys.stderr)
            sys.exit(1)
        if iv_model not in available_models:
            print(f"Error: inner voice model '{iv_model}' is not supported by the server. Available models: {available_models}", file=sys.stderr)
            sys.exit(1)

    if is_openai:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            try:
                from langchain_community.chat_models import ChatOpenAI
            except ImportError:
                print("Error: Neither langchain_openai nor langchain_community is installed", file=sys.stderr)
                sys.exit(1)

        primary_llm = ChatOpenAI(
            model=primary_model,
            temperature=temperature,
            base_url=ollama_url,
            api_key=token or "lm-studio",
        )
        inner_voice_llm = ChatOpenAI(
            model=iv_model,
            temperature=temperature,
            base_url=ollama_url,
            api_key=token or "lm-studio",
        )
    else:
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            try:
                from langchain_community.chat_models import ChatOllama
            except ImportError:
                print("Error: langchain_ollama or langchain_community not installed", file=sys.stderr)
                sys.exit(1)

        primary_llm = ChatOllama(
            model=primary_model,
            temperature=temperature,
            base_url=ollama_url,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {token}"
                }
            } if token else {}
        )
        inner_voice_llm = ChatOllama(
            model=iv_model,
            temperature=temperature,
            base_url=ollama_url,
            client_kwargs={
                "headers": {
                    "Authorization": f"Bearer {token}"
                }
            } if token else {}
        )

    models = LLMModelProviders(primary=primary_llm, inner_voice=inner_voice_llm)

    game_record = GameRecord()
    try:
        game_record.read_from_files([game_record_json, game_record_csv])
    except Exception as e:
        print(f"Error loading game records: {e}", file=sys.stderr)
        sys.exit(1)

    prompt_set = PromptSet(prompt_dir=prompt_dir)
    if prompt_set_path:
        try:
            prompt_set.load(prompt_set_path)
        except Exception as e:
            print(f"Error loading prompt set JSON: {e}", file=sys.stderr)
            sys.exit(1)

    import importlib
    experiment_name = experiment.removesuffix(".py")
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
    if player_name:
        val = player_name
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

    output_path = Path(output_dir)
    game_file = Path(game_record_csv).stem
    base_out_path = output_path / experiment_name / game_file
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

        if max_phases > 0:
            phases_to_label = phases_to_label[:max_phases]

        try:
            context_provider, inner_voice = exp_module.experiment(player, experiment_args, models)
        except Exception as e:
            print(f"Error setting up experiment '{experiment_name}' for player '{player}': {e}", file=sys.stderr)
            continue

        phase_results = []
        
        print(f"Labeling {len(phases_to_label)} phases for player '{player}'...")
        
        for idx, phase_idx in enumerate(phases_to_label, start=1):
            print(f"  [{idx}/{len(phases_to_label)}] Labeling phase {phase_idx}...")
            
            if inner_voice is not None and hasattr(inner_voice, "feed_context"):
                try:
                    inner_voice.feed_context(game_record, phase_idx)
                except Exception as e:
                    print(f"    Warning: Failed to feed context to inner voice: {e}", file=sys.stderr)
            
            try:
                labels, call_info = label_once(
                    models=models,
                    prompt_set=prompt_set,
                    context=context_provider,
                    inner_voice=inner_voice,
                    formatter_type=formatter,
                    game_data=game_record,
                    phase_idx=phase_idx,
                    context_as_tool=context_as_tool,
                    use_likert=use_likert,
                    likert_type=likert_type,
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

                # Extract thinking trace steps
                thinking_steps = []
                for msg in messages:
                    if type(msg).__name__ == "AIMessage":
                        rc = msg.additional_kwargs.get("reasoning_content")
                        if not rc and msg.response_metadata:
                            rc = msg.response_metadata.get("reasoning_content")
                        
                        if rc:
                            thinking_steps.append(rc.strip())
                        elif msg.content:
                            import re
                            think_match = re.search(r"<think>(.*?)</think>", msg.content, re.DOTALL)
                            if think_match:
                                thinking_steps.append(think_match.group(1).strip())

                labels_out = {}
                for target_player, lbl in labels.items():
                    ts = lbl.trust_scores
                    labels_out[target_player] = {
                        "alignment": {
                            "trust": ts.alignment.trust,
                            "trust_likert": ts.alignment.trust_likert,
                            "confidence": ts.alignment.confidence,
                            "confidence_likert": ts.alignment.confidence_likert
                        } if ts.alignment else None,
                        "information": {
                            "trust": ts.information.trust,
                            "trust_likert": ts.information.trust_likert,
                            "confidence": ts.information.confidence,
                            "confidence_likert": ts.information.confidence_likert
                        } if ts.information else None,
                        "consistency": {
                            "trust": ts.consistency.trust,
                            "trust_likert": ts.consistency.trust_likert,
                            "confidence": ts.consistency.confidence,
                            "confidence_likert": ts.consistency.confidence_likert
                        } if ts.consistency else None,
                        "reasoning": lbl.reasoning
                    }

                phase_results.append({
                    "phase_idx": phase_idx,
                    "context": call_info.context,
                    "inner_voice": inner_voice_calls,
                    "labels": labels_out,
                    "reasoning": reasoning,
                    "thinking_process": thinking_steps
                })
            except Exception as e:
                print(f"    Error in phase {phase_idx}: {e}", file=sys.stderr)
                err_str = str(e).lower()
                if "connection" in err_str or "timeout" in err_str or "unreachable" in err_str or "host" in err_str or "connect" in err_str:
                    print("Connection/Timeout error detected. Aborting experiment execution.", file=sys.stderr)
                    sys.exit(1)

        run_data = {
            "game_id": game_record.get_game_id() or "unknown_game",
            "game_file": game_file,
            "player_name": player,
            "trust_scale_mode": f"likert-{likert_type}" if use_likert else "numeric",
            "models": {
                "primary_model": primary_model,
                "inner_voice_model": iv_model if iv_model != primary_model else None
            },
            "prompts": prompt_set.raw_mapping,
            "time": datetime.utcnow().isoformat() + "Z",
            "experiment": experiment_name,
            "formatter": formatter,
            "experiment_args": experiment_args,
            "temperature": temperature,
            "max_phases": max_phases,
            "context_as_tool": context_as_tool,
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

        # thinking process in markdown file (extra)
        thinking_file = out_file.with_name(out_file.stem + "-thinking.md")
        with open(thinking_file, "w", encoding="utf-8") as think_f:
            think_f.write(f"# Thinking Process / Chain of Thought for {player}\n\n")
            think_f.write(f"- **Game File**: {game_file}\n")
            think_f.write(f"- **Game ID**: {run_data.get('game_id')}\n")
            think_f.write(f"- **Experiment**: {experiment_name}\n")
            think_f.write(f"- **Date**: {run_data.get('time')}\n\n")
            
            for p_res in phase_results:
                think_f.write(f"## Phase {p_res['phase_idx']} ({game_record.get_phase_type(p_res['phase_idx']).value})\n\n")
                t_steps = p_res.get("thinking_process", [])
                if t_steps:
                    for s_idx, step in enumerate(t_steps):
                        think_f.write(f"### Step {s_idx + 1} Thinking\n")
                        formatted_step = "\n".join(f"> {line}" for line in step.splitlines())
                        think_f.write(formatted_step + "\n\n")
                else:
                    think_f.write("*No thinking trace captured for this phase*\n\n")
                think_f.write("---\n\n")
                
        written_files.append(str(thinking_file))

    print("\nLabeling run complete.")
    print(f"Total files written: {len(written_files)}")
    for f in written_files:
        print(f"  - {f}")

    return written_files
