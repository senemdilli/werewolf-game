from __future__ import annotations

import pytest

from wolf_llm_labeling.game_records import GameRecord, GameRecordParseError
from wolf_llm_labeling.models import (
    ExileEvent,
    Forum,
    KillEvent,
    MayorElected,
    Message,
    PhaseType,
    PlayerStatus,
    SeerRevealed,
    SystemMessage,
    Vote,
    WitchSaved,
)

from conftest import base_rows, write_export


def test_visibility_and_structured_rows(tmp_path) -> None:
    csv_path, labels_path = write_export(tmp_path)
    record = GameRecord()
    record.read_from_files([csv_path, labels_path])

    morning = record.get_phase_data(0)
    day = record.get_phase_data(1)
    evening = record.get_phase_data(2)

    assert record.get_phase_type(0) == PhaseType.MORNING
    assert any(isinstance(item, Message) and item.forum == Forum.WEREWOLF_CHAT for item in morning)
    assert any(isinstance(item, Vote) and item.voted_for == "Seer" for item in morning)
    assert any(isinstance(item, SeerRevealed) and item.affected_player == "Wolf" for item in morning)
    assert any(isinstance(item, WitchSaved) and item.affected_player == "Seer" for item in morning)
    assert any(isinstance(item, KillEvent) and item.affected_player == "Seer" for item in morning)
    assert any(isinstance(item, SystemMessage) and item.message == "A strange bell rings." for item in morning)
    assert any(isinstance(item, MayorElected) and item.affected_player == "Villager" for item in morning)

    assert any(
        isinstance(item, Message) and item.forum == Forum.VILLAGE_CHAT and item.message == "hello village"
        for item in day
    )
    assert any(isinstance(item, SystemMessage) and item.message == "Voting begins." for item in evening)
    assert any(isinstance(item, ExileEvent) and item.affected_player == "Wolf" for item in evening)

    assert record.get_player_status(0, "Villager") == PlayerStatus.MAYOR
    assert record.get_player_status(0, "Seer") == PlayerStatus.DEAD
    assert record.get_player_status(2, "Wolf") == PlayerStatus.EXILED


def test_night_timing_alone_does_not_make_werewolf_chat(tmp_path) -> None:
    rows = base_rows()
    rows[1]["player_name"] = "Seer"
    rows[1]["player_role"] = "SEER"
    rows[1]["content"] = "private seer thought"
    csv_path, labels_path = write_export(tmp_path, rows=rows)

    record = GameRecord()
    with pytest.raises(GameRecordParseError, match="NIGHT chat for non-werewolf"):
        record.read_from_files([csv_path, labels_path])
