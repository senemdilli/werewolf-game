"""Small Ctx inspection script for manual experiments."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from wolf_llm_labeling.contexts import (
    Ctx,
    GameNowContext,
    JoinedContext,
    PhaseGameContext,
    PhaseTrustContext,
    StaticContext,
)
from wolf_llm_labeling.game_records import GameRecord


DEFAULT_GAME = Path(__file__).parents[2] / "results/game-records/game-44UT6Y-d59e923e.csv"


def main() -> None:
    game_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GAME
    player_name = sys.argv[2] if len(sys.argv) > 2 else "Lime"
    phase_idx = int(sys.argv[3]) if len(sys.argv) > 3 else 2

    record = GameRecord()
    record.read_from_files(game_path)

    print("\n=== StaticContext ===")
    static_ctx = StaticContext(player_name).get_context(record, phase_idx)
    print(static_ctx.to_string() if static_ctx else "<no context>")

    print("\n=== GameNowContext ===")
    game_now_ctx = GameNowContext(player_name).get_context(record, phase_idx)
    print(game_now_ctx.to_string() if game_now_ctx else "<no context>")

    print("\n=== PhaseGameContext ===")
    phase_game_ctx = PhaseGameContext().get_context(record, phase_idx)
    print(phase_game_ctx.to_string() if phase_game_ctx else "<no context>")

    print("\n=== Previous PhaseGameContext ===")
    previous_phase_game_ctx = PhaseGameContext(offset=1).get_context(record, phase_idx)
    print(previous_phase_game_ctx.to_string() if previous_phase_game_ctx else "<no context>")

    print("\n=== PhaseTrustContext ===")
    trust_ctx = PhaseTrustContext(player_name=player_name).get_context(record, phase_idx)
    print(trust_ctx.to_string() if trust_ctx else "<no context>")

    print("\n=== Previous PhaseTrustContext ===")
    previous_trust_ctx = PhaseTrustContext(offset=1, player_name=player_name).get_context(record, phase_idx)
    print(previous_trust_ctx.to_string() if previous_trust_ctx else "<no context>")

    print("\n=== JoinedContext ===")
    joined = JoinedContext(
        "Combined Context",
        None,
        0.0,
        GameNowContext(player_name),
        StaticContext(player_name),
        PhaseGameContext(),
        PhaseTrustContext(player_name=player_name),
    )
    joined_ctx = joined.get_context(record, phase_idx)
    print(joined_ctx.to_string() if joined_ctx else "<no context>")


if __name__ == "__main__":
    main()
