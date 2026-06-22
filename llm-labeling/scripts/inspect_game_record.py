"""Small GameRecord inspection script for manual experiments."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import Label, Message, SystemMessage, Vote


DEFAULT_GAME = Path(__file__).parents[2] / "results/game-records/game-44UT6Y-d59e923e.csv"


def describe_item(item: object) -> str:
    if isinstance(item, Message):
        return f"message [{item.forum}] {item.player_name}: {item.message}"
    if isinstance(item, SystemMessage):
        return f"system: {item.message}"
    if isinstance(item, Vote):
        return f"vote [{item.reason}] {item.player_name} -> {item.voted_for}"
    return str(item)


def describe_label(label: Label) -> str:
    scores = label.trust_scores
    return (
        f"alignment={scores.alignment}, strategic={scores.strategic}, "
        f"consistency={scores.consistency}; {label.reasoning}"
    )


def main() -> None:
    game_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GAME
    max_phases = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    record = GameRecord()
    record.read_from_files(game_path)

    players = record.get_players()
    print(f"Loaded: {game_path}")
    print("\nPlayers")
    for name, role in players.items():
        print(f"- {name}: {role}")

    print(f"Winner: {record.get_winner()}")
    print(f"\nPhases: {record.get_phase_count()} total; showing first {max_phases}")
    for phase_idx in range(min(max_phases, record.get_phase_count())):
        print(f"\n=== phase {phase_idx}: {record.get_phase_type(phase_idx)} ===")

        print("Statuses")
        for player in players:
            print(f"- {player}: {record.get_player_status(phase_idx, player)}")

        print("Data")
        for item in record.get_phase_data(phase_idx):
            print(f"- {describe_item(item)}")

        labels = record.get_labels(phase_idx)
        print("Labels")
        for observer, targets in labels.items():
            for target, target_labels in targets.items():
                for label in target_labels:
                    print(f"- {observer} -> {target}: {describe_label(label)}")


if __name__ == "__main__":
    main()
