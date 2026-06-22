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
)


def label_once(
    llm_provider: Any,
    system_prompt: str,
    context: ContextProvider,
    inner_voice: InnerVoice | None,
    game_data: GameRecord,
    phase_idx: int,
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

    # Set context variables for dynamic downstream lookup (for inside contexts or inner voices)
    t1 = active_player_name.set(player_name)
    t2 = active_llm_provider.set(llm_provider)
    t3 = active_system_prompt.set(system_prompt)

    try:
        # Materialize context
        context_ctx = context.get_context(game_data, phase_idx)
        context_str = context_ctx.to_string() if context_ctx else "No context available."

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
                    return Score(trust=t_val, confidence=c_val)

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

        report_tool = StructuredTool.from_function(
            func=report_labels_fn,
            name="report_labels",
            description="Report the final trust labels and reasoning for all other players.",
            args_schema=ReportLabelsArgs,
        )

        # 2. Define ask_inner_trust_voice tool if available
        has_inner_voice = inner_voice is not None and type(inner_voice).__name__ != "NoInnerVoice"
        ask_tool = None

        if has_inner_voice and inner_voice is not None:
            def ask_inner_voice_fn(player_name: str) -> str:
                # Need to satisfy type checker that inner_voice is not None
                if inner_voice is None:
                    return "No inner voice advice is available."
                try:
                    scores = inner_voice.ask(player_name, context_ctx, game_data, phase_idx)
                    lines = []
                    if scores.alignment is not None:
                        lines.append(f"Alignment Trust: {scores.alignment.trust}/7 (Confidence: {scores.alignment.confidence})")
                    if scores.strategic is not None:
                        lines.append(f"Strategic Trust: {scores.strategic.trust}/7 (Confidence: {scores.strategic.confidence})")
                    if scores.consistency is not None:
                        lines.append(f"Consistency Trust: {scores.consistency.trust}/7 (Confidence: {scores.consistency.confidence})")
                    if not lines:
                        return f"No trust advice available for {player_name}."
                    return f"Advice for {player_name}:\n" + "\n".join(lines)
                except Exception as e:
                    return f"Error querying inner voice: {e}"

            class AskInnerVoiceArgs(BaseModel):
                player_name: str = Field(description="The name of the player to get trust advice for")

            ask_tool = StructuredTool.from_function(
                func=ask_inner_voice_fn,
                name="ask_inner_trust_voice",
                description="Ask the inner trust voice for advice regarding a specific player name.",
                args_schema=AskInnerVoiceArgs,
            )

        # 3. Setup tools list and invoke agent using custom create_agent framework
        tools = [report_tool]
        if ask_tool is not None:
            tools.append(ask_tool)

        from langchain.agents import create_agent
        agent = create_agent(
            model=llm_provider,
            system_prompt=system_prompt,
            tools=tools,
            middleware=[]
        )

        messages = [
            HumanMessage(
                content=(
                    f"Here is the game context:\n{context_str}\n\n"
                    "Evaluate the trust scores for all other players and report them using the report_labels tool."
                )
            ),
        ]

        result = agent.invoke({"messages": messages})
        current_messages = result.get("messages", [])
        last_response = current_messages[-1] if current_messages else None

        # 4. Fallback if the LLM did not call report_labels
        if not reported_labels_dict:
            structured_llm = llm_provider.with_structured_output(ReportLabelsArgs)
            try:
                final_messages = current_messages + [
                    HumanMessage(content="Please provide the final trust scores and reasoning for all other players as structured output now.")
                ]
                final_res = structured_llm.invoke(final_messages)
                if final_res and hasattr(final_res, "labels") and final_res.labels:
                    report_labels_fn(final_res.labels)
            except Exception as e:
                # Direct fallback on the original prompt
                try:
                    final_res = structured_llm.invoke(messages)
                    if final_res and hasattr(final_res, "labels") and final_res.labels:
                        report_labels_fn(final_res.labels)
                except Exception as inner_e:
                    # Let the exception bubble up or log it, but ensure we return what we can
                    pass

        # 5. Build LLMCallInfo
        provider_name = (
            getattr(llm_provider, "model_name", None)
            or getattr(llm_provider, "model", None)
            or type(llm_provider).__name__
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
            raw_response=last_response,
            metadata=getattr(last_response, "response_metadata", {}) if last_response else {},
        )

        return reported_labels_dict, call_info

    finally:
        active_player_name.reset(t1)
        active_llm_provider.reset(t2)
        active_system_prompt.reset(t3)

