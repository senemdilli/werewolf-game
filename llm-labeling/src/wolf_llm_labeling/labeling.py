"""Core label_once interface implementation."""

from typing import Any
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
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


def formatted_trust_scores(scores: TrustScores, formatter_type: FormatterType) -> str:
    """Format trust scores based on formatter type (json or markdown)."""
    if formatter_type == "json":
        import json
        res = {}
        if scores.alignment:
            res["alignment"] = {"trust": scores.alignment.trust, "confidence": scores.alignment.confidence}
        if scores.strategic:
            res["strategic"] = {"trust": scores.strategic.trust, "confidence": scores.strategic.confidence}
        if scores.consistency:
            res["consistency"] = {"trust": scores.consistency.trust, "confidence": scores.consistency.confidence}
        return json.dumps(res)
    else:
        lines = []
        if scores.alignment:
            lines.append(f"Alignment Trust: {scores.alignment.trust}/7 (Confidence: {scores.alignment.confidence})")
        if scores.strategic:
            lines.append(f"Strategic Trust: {scores.strategic.trust}/7 (Confidence: {scores.strategic.confidence})")
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

    # Set dynamic trust instructions based on mode
    if use_likert:
        trust_instructions = (
            "Possible values for trust are the following 7-point Likert scale string constants:\n"
            "- 'VERY_LOW_TRUST' (Sehr niedriges Vertrauen)\n"
            "- 'LOW_TRUST' (Niedriges Vertrauen)\n"
            "- 'SLIGHTLY_LOW_TRUST' (Eher niedriges Vertrauen)\n"
            "- 'NEUTRAL_TRUST' (Neutral)\n"
            "- 'SLIGHTLY_HIGH_TRUST' (Eher hohes Vertrauen)\n"
            "- 'HIGH_TRUST' (Hohes Vertrauen)\n"
            "- 'VERY_HIGH_TRUST' (Sehr hohes Vertrauen)\n\n"
            "Possible values for confidence are the following 3-point Likert scale string constants:\n"
            "- 'LOW_CONFIDENCE'\n"
            "- 'MEDIUM_CONFIDENCE'\n"
            "- 'HIGH_CONFIDENCE'\n\n"
            "When reporting trust evaluations via the `report_labels` tool, you must output the exact following keys:\n"
            "- `player_name`: The name of the player.\n"
            "- `label`:\n"
            "  - `reasoning`: Your reasoning.\n"
            "  - `trust_scores`:\n"
            "    - `alignment`: `{ \"trust\": \"<Likert string>\", \"confidence\": \"<Likert string>\" }` (or null)\n"
            "    - `strategic`: `{ \"trust\": \"<Likert string>\", \"confidence\": \"<Likert string>\" }` (or null)\n"
            "    - `consistency`: `{ \"trust\": \"<Likert string>\", \"confidence\": \"<Likert string>\" }` (or null)\n\n"
            "CRITICAL: You are running in LIKERT SCALE mode. You MUST use string enum values for trust and confidence in the report_labels tool call. Do NOT use numbers."
        )
    else:
        trust_instructions = (
            "Possible values for trust are integers from 1 (lowest trust) to 7 (highest trust).\n\n"
            "Possible values for confidence are integers from 1 (low confidence) to 3 (high confidence).\n\n"
            "When reporting trust evaluations via the `report_labels` tool, you must output the exact following keys:\n"
            "- `player_name`: The name of the player.\n"
            "- `label`:\n"
            "  - `reasoning`: Your reasoning.\n"
            "  - `trust_scores`:\n"
            "    - `alignment`: `{ \"trust\": <1-7>, \"confidence\": <1-3> }` (or null)\n"
            "    - `strategic`: `{ \"trust\": <1-7>, \"confidence\": <1-3> }` (or null)\n"
            "    - `consistency`: `{ \"trust\": <1-7>, \"confidence\": <1-3> }` (or null)\n\n"
            "CRITICAL: You must use the key name \"trust\" for the trust value. Do NOT use the key name \"score\"."
        )

    # Set dynamic system prompt from prompt_set
    system_prompt = prompt_set.get_prompt(
        "labeling__system_prompt",
        {"trust_instructions": trust_instructions},
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

        reported_labels_dict: dict[PlayerName, Label] = {}

        # 1. Define report_labels tool callback and tool
        def report_labels_fn(labels: list[Any]) -> str:
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
                        t_likert = t_val
                        trust_mapping = {
                            "VERY_LOW_TRUST": 1,
                            "LOW_TRUST": 2,
                            "SLIGHTLY_LOW_TRUST": 3,
                            "NEUTRAL_TRUST": 4,
                            "SLIGHTLY_HIGH_TRUST": 5,
                            "HIGH_TRUST": 6,
                            "VERY_HIGH_TRUST": 7
                        }
                        t_val = trust_mapping.get(t_val, 4)
                    elif isinstance(t_val, int):
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
                        c_likert = c_val
                        confidence_mapping = {
                            "LOW_CONFIDENCE": 1,
                            "MEDIUM_CONFIDENCE": 2,
                            "HIGH_CONFIDENCE": 3
                        }
                        c_val = confidence_mapping.get(c_val, 2)
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
                strategic_val = parse_score(getattr(ts, "strategic", None) or (ts.get("strategic") if isinstance(ts, dict) else None))
                consistency_val = parse_score(getattr(ts, "consistency", None) or (ts.get("consistency") if isinstance(ts, dict) else None))

                reported_labels_dict[pname] = Label(
                    trust_scores=TrustScores(
                        alignment=alignment_val,
                        strategic=strategic_val,
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

        from wolf_llm_labeling.models import ReportLabelsArgs, ReportLabelsLikertArgs
        schema_class = ReportLabelsLikertArgs if use_likert else ReportLabelsArgs

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
        else:
            user_content = (
                f"Here is the game context:\n{context_str}\n\n"
                "Evaluate the trust scores for all other players and report them using the report_labels tool."
            )

        messages = [
            HumanMessage(content=user_content),
        ]

        result = agent.invoke({"messages": messages})
        current_messages = result.get("messages", [])
        last_response = current_messages[-1] if current_messages else None

        # 4. Fallback if the LLM did not call report_labels
        if not reported_labels_dict:
            structured_llm = models.primary.with_structured_output(schema_class)
            try:
                final_messages = current_messages + [
                    HumanMessage(content="Please provide the final trust scores and reasoning for all other players as structured output now.")
                ]
                final_res = structured_llm.invoke(final_messages)
                if final_res and hasattr(final_res, "labels") and final_res.labels:
                    report_labels_fn(final_res.labels)
            except Exception:
                try:
                    final_res = structured_llm.invoke(messages)
                    if final_res and hasattr(final_res, "labels") and final_res.labels:
                        report_labels_fn(final_res.labels)
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
