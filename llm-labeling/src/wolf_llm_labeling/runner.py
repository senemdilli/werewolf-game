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

# Apply monkeypatch to langchain_openai
try:
    import langchain_openai.chat_models.base as base
    original_convert = base._convert_dict_to_message

    def patched_convert(_dict: Any) -> Any:
        msg = original_convert(_dict)
        if _dict.get("role") == "assistant" and "reasoning_content" in _dict:
            if not msg.additional_kwargs:
                msg.additional_kwargs = {}
            msg.additional_kwargs["reasoning_content"] = _dict["reasoning_content"]
        return msg

    base._convert_dict_to_message = patched_convert
except ImportError:
    pass

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.inner_voice import InnerVoice
from wolf_llm_labeling.labeling import label_once
from wolf_llm_labeling.models import LLMModelProviders, FormatterType, Label
from wolf_llm_labeling.prompts import PromptSet


def _extract_reasoning_content(msg: Any) -> str | None:
    """Extract dedicated reasoning/thinking content from an AIMessage.

    Checks all known locations where LangChain wrappers (ChatOllama, ChatOpenAI)
    store reasoning content from various open-source models:
      - additional_kwargs["reasoning_content"]  (DeepSeek-R1, Gemma 4 via LM Studio)
      - response_metadata["reasoning_content"]
      - additional_kwargs["reasoning"]
      - response_metadata["reasoning"]
      - message_chunk.additional_kwargs (streaming)
    """
    rc = None
    ak = getattr(msg, "additional_kwargs", {}) or {}
    rm = getattr(msg, "response_metadata", {}) or {}

    rc = ak.get("reasoning_content")
    if not rc:
        rc = rm.get("reasoning_content")
    if not rc:
        rc = ak.get("reasoning")
    if not rc:
        rc = rm.get("reasoning")

    # Check inside streaming message chunks
    if not rc and hasattr(msg, "message_chunk") and getattr(msg, "message_chunk", None):
        chunk = msg.message_chunk
        if chunk and hasattr(chunk, "additional_kwargs"):
            cak = chunk.additional_kwargs or {}
            rc = cak.get("reasoning_content") or cak.get("reasoning")

    return rc.strip() if rc else None


def _extract_trace_events(messages: list[Any]) -> list[dict[str, Any]]:
    """Walk through all LangChain messages in chronological order and produce
    a flat list of trace events.

    Event types:
      - "thinking"    : LLM's internal reasoning (from dedicated field, <think> tags, or content)
      - "tool_call"   : LLM requested a tool call
      - "tool_result" : Tool returned a result
      - "user_message" : A human/system message
    """
    import re
    events: list[dict[str, Any]] = []

    for msg in messages:
        msg_type = type(msg).__name__

        if msg_type == "HumanMessage":
            content = getattr(msg, "content", "") or ""
            if content.strip():
                events.append({"type": "user_message", "content": content.strip()})

        elif msg_type == "AIMessage":
            # 1. Extract dedicated reasoning content
            rc = _extract_reasoning_content(msg)
            if rc:
                events.append({"type": "thinking", "content": rc, "source": "reasoning_content"})

            # 2. Extract content: check for <think> tags or use as thinking fallback
            content = getattr(msg, "content", "") or ""
            if content.strip():
                think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
                if think_match:
                    events.append({"type": "thinking", "content": think_match.group(1).strip(), "source": "think_tags"})
                    # Also capture any content outside <think> tags
                    outside = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                    if outside and len(outside) > 10:
                        events.append({"type": "thinking", "content": outside, "source": "content"})
                elif not rc:
                    # No dedicated reasoning and no think tags -> use raw content as thinking
                    if len(content.strip()) > 10:
                        events.append({"type": "thinking", "content": content.strip(), "source": "content"})

            # 3. Extract tool calls
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    events.append({
                        "type": "tool_call",
                        "tool_name": tc.get("name", "unknown"),
                        "tool_args": tc.get("args", {}),
                        "tool_id": tc.get("id"),
                    })

        elif msg_type == "ToolMessage":
            content = getattr(msg, "content", "") or ""
            tool_name = getattr(msg, "name", None) or "unknown"
            events.append({
                "type": "tool_result",
                "tool_name": tool_name,
                "content": content.strip(),
                "tool_id": getattr(msg, "tool_call_id", None),
            })

    return events


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
) -> list[str]:
    """Execute a labeling experiment for game records and save the results."""
    from wolf_llm_labeling.models import chronology_type
    chronology_type.set(chronology)
    
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
                
                messages = call_info.raw_response or []

                # Extract inner voice calls for JSON output
                inner_voice_calls = []
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

                # Extract final reasoning text for JSON output
                reasoning = None
                for msg in reversed(messages):
                    if type(msg).__name__ == "AIMessage" and msg.content:
                        reasoning = msg.content
                        break

                # Extract full chronological trace events (for trace file)
                trace_events = _extract_trace_events(messages)

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
                    "trace_events": trace_events
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

        # Generate date and time string (Berlin timezone)
        from zoneinfo import ZoneInfo
        berlin_tz = ZoneInfo("Europe/Berlin")
        date_str = datetime.now(berlin_tz).strftime("%Y-%m-%d-%H-%M")
        run_id = uuid.uuid4().hex[:8]
        out_file = base_out_path / f"{player}-{date_str}-{run_id}.json"
        with open(out_file, "w", encoding="utf-8") as out_f:
            json.dump(run_data, out_f, indent=2)
            
        written_files.append(str(out_file))
        print(f"Saved labeling results for player '{player}' to {out_file}")

        # Trace log file (comprehensive debug/trace output)
        trace_file = out_file.with_name(f"{player}-{date_str}-{run_id}-trace.md")
        with open(trace_file, "w", encoding="utf-8") as tf:
            tf.write(f"# Trace Log for {player}\n\n")

            # Run Configuration table
            tf.write("## Run Configuration\n\n")
            tf.write("| Parameter | Value |\n")
            tf.write("|:---|:---|\n")
            tf.write(f"| Game File | `{game_file}` |\n")
            tf.write(f"| Game ID | `{run_data.get('game_id')}` |\n")
            tf.write(f"| Experiment | `{experiment_name}` |\n")
            tf.write(f"| Primary Model | `{primary_model}` |\n")
            tf.write(f"| Inner Voice Model | `{iv_model if iv_model != primary_model else '—'}` |\n")
            tf.write(f"| Prompt Set | `{prompt_set_path or 'default (simple.json)'}` |\n")
            tf.write(f"| Trust Scale | `{'likert-' + likert_type if use_likert else 'numeric'}` |\n")
            tf.write(f"| Formatter | `{formatter}` |\n")
            tf.write(f"| Temperature | `{temperature}` |\n")
            tf.write(f"| Chronology | `{chronology}` |\n")
            tf.write(f"| Context as Tool | `{context_as_tool}` |\n")
            tf.write(f"| Max Phases | `{max_phases}` |\n")
            tf.write(f"| Total Phases | `{total_phases}` |\n")
            tf.write(f"| Alive Phases | `{alive_phases}` |\n")
            tf.write(f"| Date | `{run_data.get('time')}` |\n\n")
            tf.write("---\n\n")

            # Chronological trace events per phase
            for p_res in phase_results:
                phase_idx = p_res['phase_idx']
                phase_type = game_record.get_phase_type(phase_idx).value
                tf.write(f"## Phase {phase_idx} ({phase_type})\n\n")

                events = p_res.get("trace_events", [])
                if not events:
                    tf.write("*No trace events captured for this phase*\n\n")
                else:
                    for e_idx, event in enumerate(events, start=1):
                        etype = event["type"]

                        if etype == "thinking":
                            source = event.get("source", "unknown")
                            tf.write(f"### Event {e_idx} — Thinking (source: `{source}`)\n\n")
                            for line in event["content"].splitlines():
                                tf.write(f"> {line}\n")
                            tf.write("\n")

                        elif etype == "tool_call":
                            tool_name = event.get("tool_name", "unknown")
                            tf.write(f"### Event {e_idx} — Tool Call: `{tool_name}`\n\n")
                            tf.write("**Arguments:**\n")
                            tf.write("```json\n")
                            try:
                                tf.write(json.dumps(event.get("tool_args", {}), indent=2))
                            except (TypeError, ValueError):
                                tf.write(str(event.get("tool_args", {})))
                            tf.write("\n```\n\n")

                        elif etype == "tool_result":
                            tool_name = event.get("tool_name", "unknown")
                            tf.write(f"### Event {e_idx} — Tool Result: `{tool_name}`\n\n")
                            content = event.get("content", "")
                            if len(content) > 500:
                                tf.write(f"> {content[:500]}...\n\n")
                            else:
                                for line in content.splitlines():
                                    tf.write(f"> {line}\n")
                                tf.write("\n")

                        elif etype == "user_message":
                            tf.write(f"### Event {e_idx} — User Message\n\n")
                            content = event.get("content", "")
                            if len(content) > 500:
                                tf.write(f"> {content[:500]}...\n\n")
                            else:
                                for line in content.splitlines():
                                    tf.write(f"> {line}\n")
                                tf.write("\n")

                tf.write("---\n\n")
                
        written_files.append(str(trace_file))

    print("\nLabeling run complete.")
    print(f"Total files written: {len(written_files)}")
    for f in written_files:
        print(f"  - {f}")

    return written_files
