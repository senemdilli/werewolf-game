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
    VoteReason,
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


def test_post_exile_mayor_election_moves_to_next_phase(tmp_path) -> None:
    rows = base_rows()
    rows.extend(
        [
            rows[0]
            | {
                "round": "1",
                "phase": "DAY",
                "content": "The village must elect a Mayor.",
                "timestamp": "2026-01-01T00:00:13.000Z",
            },
            rows[0]
            | {
                "round": "1",
                "phase": "DAY",
                "content": "Witch has been elected Mayor. Their vote counts double.",
                "timestamp": "2026-01-01T00:00:14.000Z",
            },
            rows[0] | {"round": "2", "phase": "NIGHT", "content": "Night 2 begins.", "timestamp": "2026-01-01T00:00:15.000Z"},
            rows[0]
            | {
                "round": "2",
                "phase": "DAY",
                "content": "Dawn breaks. No one was killed.",
                "timestamp": "2026-01-01T00:00:16.000Z",
            },
            rows[0]
            | {
                "round": "2",
                "phase": "DAY",
                "content": "The village must elect a Mayor.",
                "timestamp": "2026-01-01T00:00:16.500Z",
            },
            rows[0]
            | {
                "round": "2",
                "phase": "DAY",
                "content": "Villager has been elected Mayor. Their vote counts double.",
                "timestamp": "2026-01-01T00:00:16.750Z",
            },
            rows[0] | {"round": "2", "phase": "DAY", "content": "Voting begins.", "timestamp": "2026-01-01T00:00:17.000Z"},
            rows[0]
            | {
                "round": "2",
                "phase": "DAY",
                "content": "The village voted to skip. No one was eliminated.",
                "timestamp": "2026-01-01T00:00:18.000Z",
            },
        ]
    )
    csv_path, labels_path = write_export(tmp_path, rows=rows)

    record = GameRecord()
    record.read_from_files([csv_path, labels_path])

    assert not any(isinstance(item, MayorElected) and item.affected_player == "Witch" for item in record.get_phase_data(2))
    assert any(isinstance(item, MayorElected) and item.affected_player == "Witch" for item in record.get_phase_data(3))
    assert any(isinstance(item, MayorElected) and item.affected_player == "Villager" for item in record.get_phase_data(3))


def test_day_votes_are_parsed_before_results(tmp_path) -> None:
    rows = base_rows()
    rows.extend(
        [
            rows[0]
            | {
                "type": "day_vote",
                "player_name": "Wolf",
                "player_role": "WEREWOLF",
                "target_name": "Villager",
                "content": "MAYOR",
            },
            rows[0]
            | {
                "type": "day_vote",
                "player_name": "Villager",
                "player_role": "VILLAGER",
                "target_name": "Wolf",
                "content": "EXILE",
            },
        ]
    )
    csv_path, labels_path = write_export(tmp_path, rows=rows)

    record = GameRecord()
    record.read_from_files([csv_path, labels_path])

    morning = record.get_phase_data(0)
    evening = record.get_phase_data(2)
    assert [type(item).__name__ for item in morning][-2:] == ["Vote", "MayorElected"]
    assert any(isinstance(item, Vote) and item.reason == VoteReason.MAYOR and item.voted_for == "Villager" for item in morning)
    assert [type(item).__name__ for item in evening] == ["SystemMessage", "Vote", "ExileEvent"]


def test_random_mayor_assignment_preserves_system_text(tmp_path) -> None:
    rows = base_rows()
    rows[8]["content"] = "No one voted. Villager was randomly selected as Mayor. Their vote counts double."
    csv_path, labels_path = write_export(tmp_path, rows=rows)

    record = GameRecord()
    record.read_from_files([csv_path, labels_path])

    morning = record.get_phase_data(0)
    assert any(isinstance(item, SystemMessage) and item.message == "The village must elect a Mayor." for item in morning)
    assert any(
        isinstance(item, SystemMessage)
        and item.message == "No one voted. Villager was randomly selected as Mayor. Their vote counts double."
        for item in morning
    )
    assert any(isinstance(item, MayorElected) and item.affected_player == "Villager" for item in morning)
