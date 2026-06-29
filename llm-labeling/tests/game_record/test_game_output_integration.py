from __future__ import annotations

from pathlib import Path

import pytest

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import (
    ExileEvent,
    Forum,
    KillEvent,
    Message,
    PlayerStatus,
    Role,
    SeerRevealed,
    SystemMessage,
    WitchKilled,
    WitchSaved,
    MayorElected,
)

EXPORT_DIR = Path(__file__).parents[3] / "results" / "game-records"


@pytest.mark.parametrize(
    ("filename", "player_count", "phase_count", "known_player", "known_role", "winner"),
    [
        ("game-44UT6Y-d59e923e.csv", 9, 9, "Blue", Role.WEREWOLF, "VILLAGERS"),
        ("game-CCUTH3-352fd9ba.csv", 8, 10, "Beige", Role.WEREWOLF, "WEREWOLVES"),
        ("game-P3WO10-9eb0210d.csv", 8, 12, "Brown", Role.WEREWOLF, "WEREWOLVES"),
    ],
)
def test_real_exports_load_with_known_counts_and_roles(
    filename: str,
    player_count: int,
    phase_count: int,
    known_player: str,
    known_role: Role,
    winner: str,
) -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / filename)

    assert len(record.get_players()) == player_count
    assert record.get_phase_count() == phase_count
    assert record.get_players()[known_player] == known_role
    assert record.get_winner() == winner


def test_real_export_single_path_inference_from_csv_and_labels() -> None:
    csv_path = EXPORT_DIR / "game-44UT6Y-d59e923e.csv"
    labels_path = EXPORT_DIR / "game-44UT6Y-d59e923e-labels.json"

    from_csv = GameRecord()
    from_csv.read_from_files(csv_path)
    from_labels = GameRecord()
    from_labels.read_from_files(labels_path)

    assert from_csv.get_players() == from_labels.get_players()
    assert from_csv.get_phase_count() == from_labels.get_phase_count() == 9


def test_44ut6y_known_message_label_mayor_and_exile() -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / "game-44UT6Y-d59e923e.csv")

    phase_0 = record.get_phase_data(0)
    assert not any(isinstance(item, ExileEvent) for item in phase_0)
    assert any(isinstance(item, MayorElected) and item.affected_player == "Blue" for item in phase_0)
    assert record.get_player_status(0, "Blue") == PlayerStatus.MAYOR

    # Gold trusted Blue
    assert record.get_labels(1)["Gold"]["Blue"][0].trust_scores.alignment.trust == 7

    # Blue is exiled
    assert any(isinstance(item, ExileEvent) and item.affected_player == "Blue" for item in record.get_phase_data(5))
    assert record.get_player_status(5, "Blue") == PlayerStatus.EXILED


def test_ccuth3_known_mayor_death_and_label() -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / "game-CCUTH3-352fd9ba.csv")

    assert record.get_player_status(1, "Purple") == PlayerStatus.MAYOR
    # Purple is dead
    assert record.get_player_status(6, "Purple") == PlayerStatus.DEAD
    assert record.get_player_status(6, "Lime") == PlayerStatus.MAYOR
    assert any(isinstance(item, MayorElected) and item.affected_player == "Lime" for item in record.get_phase_data(6))


def test_p3wo10_known_witch_kill_deaths_and_exile() -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / "game-P3WO10-9eb0210d.csv")

    assert record.get_player_status(0, "Red") == PlayerStatus.MAYOR
    assert record.get_player_status(0, "Gold") == PlayerStatus.DEAD
    
    # Witch saved a player
    assert any(isinstance(item, WitchSaved) for item in record.get_phase_data(3))

    # Blue is exiled
    assert any(isinstance(item, ExileEvent) and item.affected_player == "Blue" for item in record.get_phase_data(11))
    assert record.get_player_status(11, "Blue") == PlayerStatus.EXILED
