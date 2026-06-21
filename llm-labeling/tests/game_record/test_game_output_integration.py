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
    WitchKilled,
)

from conftest import count_phases

EXPORT_DIR = Path(__file__).parents[3] / "results" / "game-output"


@pytest.mark.parametrize(
    ("filename", "player_count", "phase_count", "known_player", "known_role"),
    [
        ("game-706E87-97809dcb.csv", 7, 8, "Garrett", Role.SEER),
        ("game-AA0F7O-30bcd6c1.csv", 8, 9, "TheTorminator", Role.WITCH),
        ("game-OX8OBY-3b3beea1.csv", 7, 6, "Wren", Role.SEER),
    ],
)
def test_real_exports_load_with_known_counts_and_roles(
    filename: str,
    player_count: int,
    phase_count: int,
    known_player: str,
    known_role: Role,
) -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / filename)

    assert len(record.get_players()) == player_count
    assert count_phases(record) == phase_count
    assert record.get_players()[known_player] == known_role


def test_real_export_single_path_inference_from_csv_and_labels() -> None:
    csv_path = EXPORT_DIR / "game-AA0F7O-30bcd6c1.csv"
    labels_path = EXPORT_DIR / "game-AA0F7O-30bcd6c1-labels.json"

    from_csv = GameRecord()
    from_csv.read_from_files(csv_path)
    from_labels = GameRecord()
    from_labels.read_from_files(labels_path)

    assert from_csv.get_players() == from_labels.get_players()
    assert count_phases(from_csv) == count_phases(from_labels) == 9


def test_706e87_known_message_label_mayor_and_exile() -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / "game-706E87-97809dcb.csv")

    assert any(
        isinstance(item, Message)
        and item.forum == Forum.VILLAGE_CHAT
        and item.player_name == "Garrett"
        and "I'm the Seer, Mosh is the Werewolf" in item.message
        for item in record.get_phase_data(5)
    )
    assert record.get_labels(0)["Dorian"]["Mosh"][0].trust_scores.alignment.trust == 3
    assert record.get_player_status(2, "Petra") == PlayerStatus.MAYOR
    assert any(isinstance(item, ExileEvent) and item.affected_player == "Mosh" for item in record.get_phase_data(6))


def test_aa0f7o_known_mayor_death_and_label() -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / "game-AA0F7O-30bcd6c1.csv")

    assert record.get_player_status(0, "TheTorminator") == PlayerStatus.MAYOR
    assert record.get_player_status(2, "TheTorminator") == PlayerStatus.DEAD
    assert record.get_labels(0)["Elara"]["Seraphina"][0].trust_scores.strategic.trust == 7
    assert any(isinstance(item, SeerRevealed) and item.affected_player == "Gideon" for item in record.get_phase_data(2))


def test_ox8oby_known_witch_kill_deaths_and_exile() -> None:
    record = GameRecord()
    record.read_from_files(EXPORT_DIR / "game-OX8OBY-3b3beea1.csv")

    assert record.get_player_status(0, "Yellow") == PlayerStatus.MAYOR
    assert any(isinstance(item, WitchKilled) and item.affected_player == "Lyra" for item in record.get_phase_data(4))
    assert {item.affected_player for item in record.get_phase_data(4) if isinstance(item, KillEvent)} == {"Wren", "Lyra"}
    assert any(isinstance(item, ExileEvent) and item.affected_player == "Beatrix" for item in record.get_phase_data(3))
    assert record.get_labels(0)["Beatrix"]["spcx"][0].trust_scores.alignment.trust == 7
