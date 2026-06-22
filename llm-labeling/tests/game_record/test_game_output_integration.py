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
)

EXPORT_DIR = Path(__file__).parents[3] / "results" / "game-records"


@pytest.mark.parametrize(
    ("filename", "player_count", "phase_count", "known_player", "known_role", "winner"),
    [
        ("game-706E87-97809dcb.csv", 7, 12, "Garrett", Role.SEER, "VILLAGERS"),
        ("game-AA0F7O-30bcd6c1.csv", 8, 12, "TheTorminator", Role.WITCH, "VILLAGERS"),
        ("game-OX8OBY-3b3beea1.csv", 7, 9, "Wren", Role.SEER, "VILLAGERS"),
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
    csv_path = EXPORT_DIR / "game-AA0F7O-30bcd6c1.csv"
    labels_path = EXPORT_DIR / "game-AA0F7O-30bcd6c1-labels.json"

    from_csv = GameRecord()
    from_csv.read_from_files(csv_path)
    from_labels = GameRecord()
    from_labels.read_from_files(labels_path)

    assert from_csv.get_players() == from_labels.get_players()
    assert from_csv.get_phase_count() == from_labels.get_phase_count() == 12


def test_706e87_known_message_label_mayor_and_exile() -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / "game-706E87-97809dcb.csv")

    phase_0 = record.get_phase_data(0)
    assert not any(isinstance(item, SystemMessage) and item.message == "Voting begins." for item in phase_0)
    assert not any(isinstance(item, ExileEvent) for item in phase_0)
    assert any(
        isinstance(item, Message)
        and item.forum == Forum.VILLAGE_CHAT
        and item.player_name == "Garrett"
        and "I'm the Seer, Mosh is the Werewolf" in item.message
        for item in record.get_phase_data(7)
    )
    assert record.get_labels(1)["Dorian"]["Mosh"][0].trust_scores.alignment.trust == 3
    assert record.get_player_status(4, "Petra") == PlayerStatus.MAYOR
    assert any(isinstance(item, ExileEvent) and item.affected_player == "Mosh" for item in record.get_phase_data(8))


def test_aa0f7o_known_mayor_death_and_label() -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / "game-AA0F7O-30bcd6c1.csv")

    assert record.get_player_status(1, "TheTorminator") == PlayerStatus.MAYOR
    assert record.get_player_status(3, "TheTorminator") == PlayerStatus.DEAD
    assert record.get_labels(1)["Elara"]["Seraphina"][0].trust_scores.strategic.trust == 7
    assert any(isinstance(item, SeerRevealed) and item.affected_player == "Gideon" for item in record.get_phase_data(3))


def test_ox8oby_known_witch_kill_deaths_and_exile() -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / "game-OX8OBY-3b3beea1.csv")

    assert record.get_player_status(1, "Yellow") == PlayerStatus.MAYOR
    assert any(isinstance(item, WitchKilled) and item.affected_player == "Lyra" for item in record.get_phase_data(6))
    assert {item.affected_player for item in record.get_phase_data(6) if isinstance(item, KillEvent)} == {"Wren", "Lyra"}
    assert any(isinstance(item, ExileEvent) and item.affected_player == "Beatrix" for item in record.get_phase_data(5))
    assert record.get_labels(2)["Beatrix"]["spcx"][0].trust_scores.alignment.trust == 7
