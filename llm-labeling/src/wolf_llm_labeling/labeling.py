"""Core label_once interface implementation."""

import sys
import threading
import time
from typing import Any
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_core.tools import StructuredTool

from wolf_llm_labeling.contexts import ContextProvider
from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.inner_voice import InnerVoice
from wolf_llm_labeling.models import (
    Label,
    LLMCallInfo,
    PlayerName,
    Score,
    TrustScores,
    active_player_name,
    active_llm_provider,
    active_system_prompt,
    ReportLabelsArgs,
    FormatterType,
    LLMModelProviders,
)
from wolf_llm_labeling.prompts import PromptSet


class ConsoleSpinner:
    def __init__(self, message="Thinking"):
        self.message = message
        self.spinner_cycle = ["|", "/", "-", "\\"] # New spinner for showing loading
        self.running = False
        self._thread = None

    def _spin(self):
        idx = 0
        while self.running:
            sys.stdout.write(f"\r    {self.message} {self.spinner_cycle[idx]}")
            sys.stdout.flush()
            idx = (idx + 1) % len(self.spinner_cycle)
            time.sleep(0.15)
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._spin)
        self._thread.daemon = True
        self._thread.start()
        return self

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def formatted_trust_scores(scores: TrustScores, formatter_type: FormatterType) -> str:
    """Format trust scores based on formatter type (json or markdown)."""
    if formatter_type == "json":
        import json
        res = {}
        if scores.alignment:
            res["alignment"] = {"trust": scores.alignment.trust, "confidence": scores.alignment.confidence}
        if scores.information:
            res["information"] = {"trust": scores.information.trust, "confidence": scores.information.confidence}
        if scores.consistency:
            res["consistency"] = {"trust": scores.consistency.trust, "confidence": scores.consistency.confidence}
        return json.dumps(res)
    else:
        lines = []
        if scores.alignment:
            lines.append(f"Alignment Trust: {scores.alignment.trust}/7 (Confidence: {scores.alignment.confidence})")
        if scores.information:
            lines.append(f"Information Trust: {scores.information.trust}/7 (Confidence: {scores.information.confidence})")
        if scores.consistency:
            lines.append(f"Consistency Trust: {scores.consistency.trust}/7 (Confidence: {scores.consistency.confidence})")
        return "\n".join(lines)


def label_once(
    models: LLMModelProviders,
    prompt_set: PromptSet,
    context: ContextProvider,
    inner_voice: InnerVoice | None,
    formatter_type: FormatterType,
    game_data: GameRecord,
    phase_idx: int,
    context_as_tool: bool = False,
    use_likert: bool = False,
    likert_type: str = "agree-disagree",
) -> tuple[dict[PlayerName, Label], LLMCallInfo]:
    # Find player_name from the context if possible (e.g. from StaticContext or GameNowContext)
    player_name = getattr(context, "player_name", None)
    if player_name is None and hasattr(context, "sub_contexts"):
        def find_player(ctx_provider: Any) -> PlayerName | None:
            if hasattr(ctx_provider, "player_name"):
                return ctx_provider.player_name
            if hasattr(ctx_provider, "sub_contexts"):
                for sub in ctx_provider.sub_contexts:
                    p = find_player(sub)
                    if p is not None:
                        return p
            return None
        player_name = find_player(context)

    # Fallback to the first player in the game record if not resolved
    if player_name is None:
        players = list(game_data.get_players().keys())
        if players:
            player_name = players[0]
        else:
            player_name = "UnknownObserver"

    # Set dynamic system prompt from prompt_set depending on CLI configuration
    if not use_likert:
        prompt_key = "system_prompt_numeric"
    elif likert_type == "legacy":
        prompt_key = "system_prompt_legacy"
    else:
        prompt_key = "system_prompt"

    system_prompt = prompt_set.get_prompt(
        f"labeling__{prompt_key}",
        {},  # No placeholders anymore
        "You are a helpful assistant playing Werewolf. Assess the trust level of other players."
    )

    # Set context variables for dynamic downstream lookup (for inside contexts or inner voices)
    t1 = active_player_name.set(player_name)
    # The inner voice queries should use the inner_voice model provider, not the primary
    t2 = active_llm_provider.set(models.inner_voice)
    t3 = active_system_prompt.set(system_prompt)

    try:
        # Materialize context
        context_ctx = context.get_context(game_data, prompt_set, phase_idx)
        context_str = context_ctx.to_string(formatter_type=formatter_type) if context_ctx else "No context available."

        context_injected_in_system = False
        if "[PLACEHOLDER FOR GAME CONTEXT]" in system_prompt:
            system_prompt = system_prompt.replace("[PLACEHOLDER FOR GAME CONTEXT]", context_str)
            context_injected_in_system = True
            active_system_prompt.set(system_prompt)

        reported_labels_dict: dict[PlayerName, Label] = {}

        # 1. Define report_labels tool callback and tool
        def report_labels_fn(labels: list[Any]) -> str:
            print("      [Tool Call] Agent reported final trust labels.")
            for item in labels:
                pname = getattr(item, "player_name", None) or (item.get("player_name") if isinstance(item, dict) else None)
                lbl = getattr(item, "label", None) or (item.get("label") if isinstance(item, dict) else None)
                if not pname or not lbl:
                    continue

                ts = getattr(lbl, "trust_scores", None) or (lbl.get("trust_scores") if isinstance(lbl, dict) else None)
                reasoning = getattr(lbl, "reasoning", "") or (lbl.get("reasoning") if isinstance(lbl, dict) else "")

                def parse_score(s: Any) -> Score | None:
                    if s is None:
                        return None
                    t_val = getattr(s, "trust", None) or (s.get("trust") if isinstance(s, dict) else None)
                    c_val = getattr(s, "confidence", None) or (s.get("confidence") if isinstance(s, dict) else None)
                    if t_val is None or c_val is None:
                        return None

                    t_likert = None
                    c_likert = None

                    if isinstance(t_val, str):
                        t_val_clean = t_val.upper().replace("_", " ").replace("-", " ").strip()
                        # Agree/disagree scale matching:
                        if "STRONGLY DISAGREE" in t_val_clean:
                            t_val = 1
                            t_likert = "STRONGLY_DISAGREE"
                        elif "SLIGHTLY DISAGREE" in t_val_clean:
                            t_val = 3
                            t_likert = "SLIGHTLY_DISAGREE"
                        elif "DISAGREE" in t_val_clean:
                            t_val = 2
                            t_likert = "DISAGREE"
                        elif "STRONGLY AGREE" in t_val_clean:
                            t_val = 7
                            t_likert = "STRONGLY_AGREE"
                        elif "SLIGHTLY AGREE" in t_val_clean:
                            t_val = 5
                            t_likert = "SLIGHTLY_AGREE"
                        elif "AGREE" in t_val_clean:
                            t_val = 6
                            t_likert = "AGREE"
                        elif "NEUTRAL" in t_val_clean and "TRUST" not in t_val_clean:
                            t_val = 4
                            t_likert = "NEUTRAL"
                        # Legacy scale matching:
                        elif "VERY LOW" in t_val_clean:
                            t_val = 1
                            t_likert = "VERY_LOW_TRUST"
                        elif "SLIGHTLY LOW" in t_val_clean:
                            t_val = 3
                            t_likert = "SLIGHTLY_LOW_TRUST"
                        elif "LOW" in t_val_clean:
                            t_val = 2
                            t_likert = "LOW_TRUST"
                        elif "VERY HIGH" in t_val_clean:
                            t_val = 7
                            t_likert = "VERY_HIGH_TRUST"
                        elif "SLIGHTLY HIGH" in t_val_clean:
                            t_val = 5
                            t_likert = "SLIGHTLY_HIGH_TRUST"
                        elif "HIGH" in t_val_clean:
                            t_val = 6
                            t_likert = "HIGH_TRUST"
                        elif "NEUTRAL TRUST" in t_val_clean:
                            t_val = 4
                            t_likert = "NEUTRAL_TRUST"
                        else:
                            t_val = 4
                            t_likert = "NEUTRAL" if likert_type == "agree-disagree" else "NEUTRAL_TRUST"
                    elif isinstance(t_val, int):
                        if likert_type == "agree-disagree":
                            reverse_trust = {
                                1: "STRONGLY_DISAGREE",
                                2: "DISAGREE",
                                3: "SLIGHTLY_DISAGREE",
                                4: "NEUTRAL",
                                5: "SLIGHTLY_AGREE",
                                6: "AGREE",
                                7: "STRONGLY_AGREE"
                            }
                            t_likert = reverse_trust.get(t_val, "NEUTRAL")
                        else:
                            reverse_trust = {
                                1: "VERY_LOW_TRUST",
                                2: "LOW_TRUST",
                                3: "SLIGHTLY_LOW_TRUST",
                                4: "NEUTRAL_TRUST",
                                5: "SLIGHTLY_HIGH_TRUST",
                                6: "HIGH_TRUST",
                                7: "VERY_HIGH_TRUST"
                            }
                            t_likert = reverse_trust.get(t_val, "NEUTRAL_TRUST")

                    if isinstance(c_val, str):
                        c_val_clean = c_val.upper().replace("_", " ").replace("-", " ").strip()
                        if "LOW" in c_val_clean:
                            c_val = 1
                            c_likert = "LOW_CONFIDENCE"
                        elif "HIGH" in c_val_clean:
                            c_val = 3
                            c_likert = "HIGH_CONFIDENCE"
                        else:
                            c_val = 2
                            c_likert = "MEDIUM_CONFIDENCE"
                    elif isinstance(c_val, int):
                        reverse_conf = {
                            1: "LOW_CONFIDENCE",
                            2: "MEDIUM_CONFIDENCE",
                            3: "HIGH_CONFIDENCE"
                        }
                        c_likert = reverse_conf.get(c_val, "MEDIUM_CONFIDENCE")

                    return Score(
                        trust=t_val,
                        confidence=c_val,
                        trust_likert=t_likert,
                        confidence_likert=c_likert
                    )

                alignment_val = parse_score(getattr(ts, "alignment", None) or (ts.get("alignment") if isinstance(ts, dict) else None))
                information_val = parse_score(getattr(ts, "information", None) or (ts.get("information") if isinstance(ts, dict) else None))
                consistency_val = parse_score(getattr(ts, "consistency", None) or (ts.get("consistency") if isinstance(ts, dict) else None))

                reported_labels_dict[pname] = Label(
                    trust_scores=TrustScores(
                        alignment=alignment_val,
                        information=information_val,
                        consistency=consistency_val,
                    ),
                    reasoning=reasoning,
                )
            return "Labels successfully reported."

        report_desc = prompt_set.get_prompt(
            "labeling__report_labels_desc",
            {},
            "Report the final trust labels and reasoning for all other players."
        )
        if use_likert:
            if likert_type == "agree-disagree":
                report_desc += (
                    "IMPORTANT: Each active trust score dimension (alignment, information, consistency) MUST be a nested object containing 'trust' (e.g., 'STRONGLY_DISAGREE', 'AGREE') and "
                    "'confidence' (e.g. 'MEDIUM_CONFIDENCE'). Never pass simple strings or numbers directly to the alignment/information/consistency fields."
                )
            else:
                report_desc += (
                    "IMPORTANT: Each active trust score dimension (alignment, information, consistency) MUST be a nested object containing 'trust' (e.g., 'HIGH_TRUST', 'LOW_TRUST') and "
                    "'confidence' (e.g. 'MEDIUM_CONFIDENCE'). Never pass simple strings or numbers directly to the alignment/information/consistency fields."
                )
        else:
            report_desc += (
                "IMPORTANT: Each active trust score dimension (alignment, information, consistency) MUST be a nested object containing 'trust' (integer 1-10) and 'confidence' (integer 1-5). "
                "Never pass simple numbers directly to the alignment/information/consistency fields!"
            )

        from wolf_llm_labeling.models import ReportLabelsArgs, ReportLabelsLikertArgs, ReportLabelsLikertLegacyArgs
        if use_likert:
            schema_class = ReportLabelsLikertArgs if likert_type == "agree-disagree" else ReportLabelsLikertLegacyArgs
        else:
            schema_class = ReportLabelsArgs

        report_tool = StructuredTool.from_function(
            func=report_labels_fn,
            name="report_labels",
            description=report_desc,
            args_schema=schema_class,
        )

        # 2. Define ask_inner_trust_voice tool if available
        has_inner_voice = inner_voice is not None and type(inner_voice).__name__ != "NoInnerVoice"
        ask_tool = None

        if has_inner_voice and inner_voice is not None:
            def ask_inner_voice_fn(player_name: str) -> str:
                print(f"      [Tool Call] Agent requested inner trust voice advice for '{player_name}'.")
                if inner_voice is None:
                    return "No inner voice advice is available."
                try:
                    scores = inner_voice.ask(player_name, context_ctx, game_data, prompt_set, phase_idx)
                    advice_content = formatted_trust_scores(scores, formatter_type)
                    if not advice_content:
                        return f"No trust advice available for {player_name}."
                    
                    if formatter_type == "json":
                        return advice_content
                    return f"Advice for {player_name}:\n" + advice_content
                except Exception as e:
                    return f"Error querying inner voice: {e}"

            class AskInnerVoiceArgs(BaseModel):
                player_name: str = Field(description="The name of the player to get trust advice for")

            ask_tool = StructuredTool.from_function(
                func=ask_inner_voice_fn,
                name="ask_inner_trust_voice",
                description=inner_voice.tool_description(prompt_set),
                args_schema=AskInnerVoiceArgs,
            )

        # Define get_game_context tool
        def get_game_context_fn() -> str:
            print("      [Tool Call] Agent requested game context.")
            return context_str

        get_context_desc = prompt_set.get_prompt(
            "labeling__get_game_context_desc",
            {},
            "Retrieve the current werewolf game conversation and history context."
        )

        get_context_tool = StructuredTool.from_function(
            func=get_game_context_fn,
            name="get_game_context",
            description=get_context_desc,
        )

        # 3. Setup tools list and invoke agent using custom create_agent framework
        tools = [report_tool]
        if ask_tool is not None:
            tools.append(ask_tool)
        if context_as_tool:
            tools.append(get_context_tool)

        from langchain.agents import create_agent
        agent = create_agent(
            model=models.primary,
            system_prompt=system_prompt,
            tools=tools,
            middleware=[]
        )

        if context_as_tool:
            user_content = (
                "You do not have the game context pre-injected. "
                "Use the 'get_game_context' tool to retrieve the werewolf game conversation and history context. "
                "Then evaluate the trust scores for all other players and report them using the report_labels tool"
            )
        elif context_injected_in_system:
            user_content = (
                "Evaluate the trust scores for all other players and report them using the report_labels tool."
            )
        else:
            user_content = (
                f"Here is the game context:\n{context_str}\n\n"
                "Evaluate the trust scores for all other players and report them using the report_labels tool."
            )

        messages = [
            HumanMessage(content=user_content),
        ]

        current_messages = list(messages)
        tool_calls_detected = 0
        step_count = 0
        
        print("Running agentic loop:")
        try:
            for event in agent.stream({"messages": messages}):
                for node_name, node_state in event.items():
                    node_msgs = node_state.get("messages", [])
                    for msg in node_msgs:
                        current_messages.append(msg)
                        if isinstance(msg, AIMessage):
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    tool_calls_detected += 1
                                    print(f"      -> [Step {step_count+1}] Calling tool '{tc['name']}' with args: {tc['args']}...")
                            elif msg.content:
                                # Show snippet of thinking content if any
                                snippet = msg.content.strip().replace("\n", " ")
                                if len(snippet) > 80:
                                    snippet = snippet[:80] + "..."
                                print(f"      [Thinking] {snippet}")
                        elif isinstance(msg, ToolMessage):
                            content_summary = msg.content.strip().replace("\n", " ")
                            if len(content_summary) > 80:
                                content_summary = content_summary[:80] + "..."
                            print(f"      <- [Step {step_count+1}] Tool returned: {content_summary}")
                            step_count += 1
        except Exception as e:
            print(f"    Warning: Agent stream encountered exception: {e}. Falling back to normal invoke...")
            with ConsoleSpinner("Running agentic loop (fallback)..."):
                result = agent.invoke({"messages": messages})
            current_messages = result.get("messages", [])
            
        last_response = current_messages[-1] if current_messages else None

        # 4. Fallback if the LLM did not call report_labels
        if not reported_labels_dict:
            # First try to extract JSON directly from any AIMessage content
            import re
            import json
            for msg in reversed(current_messages):
                if type(msg).__name__ == "AIMessage" and msg.content:
                    # Look for markdown JSON code blocks or generic JSON array structures
                    json_blocks = re.findall(r"```json\s*(.*?)\s*```", msg.content, re.DOTALL)
                    if not json_blocks:
                        # Fallback
                        json_blocks = re.findall(r"(\[.*?\])", msg.content, re.DOTALL)
                    
                    for block in json_blocks:
                        try:
                            # Clean up block in case of trailing commas or comments
                            cleaned_block = block.strip()
                            # Basic cleanup
                            if cleaned_block.endswith(","):
                                cleaned_block = cleaned_block[:-1]
                            data = json.loads(cleaned_block)
                            if isinstance(data, list):
                                mock_labels = []
                                for item in data:
                                    if isinstance(item, dict) and "player_name" in item and "label" in item:
                                        mock_labels.append(item)
                                if mock_labels:
                                    print("      [Fallback] Successfully extracted labels directly from AIMessage content JSON.")
                                    report_labels_fn(mock_labels)
                                    current_messages.append(SystemMessage(
                                        content="[SYSTEM_FALLBACK] The model failed to call the 'report_labels' tool directly. However, the trust scores were successfully parsed and extracted from the raw response content."
                                    ))
                                    break
                        except Exception:
                            pass
                if reported_labels_dict:
                    break

        if not reported_labels_dict:
            structured_llm = models.primary.with_structured_output(schema_class)
            try:
                final_messages = current_messages + [
                    HumanMessage(content="Please provide the final trust scores and reasoning for all other players as structured output now.")
                ]
                with ConsoleSpinner("Running structured output fallback..."):
                    final_res = structured_llm.invoke(final_messages)
                if final_res and hasattr(final_res, "labels") and final_res.labels:
                    report_labels_fn(final_res.labels)
                    current_messages.append(SystemMessage(
                        content="[SYSTEM_FALLBACK] The model failed to call the 'report_labels' tool directly. A structured fallback request was executed to retrieve the final labels."
                    ))
            except Exception:
                try:
                    with ConsoleSpinner("Running structured fallback..."):
                        final_res = structured_llm.invoke(messages)
                    if final_res and hasattr(final_res, "labels") and final_res.labels:
                        report_labels_fn(final_res.labels)
                        current_messages.append(SystemMessage(
                            content="[SYSTEM_FALLBACK] The model failed to call the 'report_labels' tool directly. A structured fallback request was executed to retrieve the final labels."
                        ))
                except Exception:
                    pass

        # 5. Build LLMCallInfo
        provider_name = (
            getattr(models.primary, "model_name", None)
            or getattr(models.primary, "model", None)
            or type(models.primary).__name__
        )

        tool_calls = []
        for msg in current_messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append(tc)

        call_info = LLMCallInfo(
            provider_name=provider_name,
            context=context_str,
            tool_calls=tool_calls,
            raw_response=current_messages,
            metadata=getattr(last_response, "response_metadata", {}) if last_response else {},
        )

        return reported_labels_dict, call_info

    finally:
        active_player_name.reset(t1)
        active_llm_provider.reset(t2)
        active_system_prompt.reset(t3)
