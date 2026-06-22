"""Integration example for early experiments."""

from typing import Any
from wolf_llm_labeling.contexts import JoinedContext, StaticContext, GameNowContext, PhaseGameContext
from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.labeling import label_once


def run_example(llm_provider: Any, system_prompt: str, game_path: str, player_name: str) -> None:
    """Integration example showing how to load a game record, build a context, and execute trust labeling"""
    print(f"Loading game record from {game_path}:")
    record = GameRecord()
    record.read_from_files(game_path)

    print(f"Building context for player '{player_name}':")
    context = JoinedContext(
        "Game Context",
        None,
        100.0,
        StaticContext(player_name),
        GameNowContext(player_name),
        PhaseGameContext(offset=0),
    )

    phase_idx = 0  # Start at the first phase
    print(f"Executing label_once for phase {phase_idx}:")

    labels, call_info = label_once(
        llm_provider=llm_provider,
        system_prompt=system_prompt,
        context=context,
        inner_voice=None,
        game_data=record,
        phase_idx=phase_idx,
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

    print("\n=== LLM Call Metadata ===")
    print(f"Provider: {call_info.provider_name}")
    print(f"Tool calls made: {len(call_info.tool_calls)}")

