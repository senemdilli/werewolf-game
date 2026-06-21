from __future__ import annotations

import pytest

from wolf_llm_labeling.game_records import GameRecord, GameRecordParseError, GameRecordValidationError

from conftest import base_labels, base_rows, count_phases, row, write_export


def second_export() -> tuple[list[dict[str, str]], dict]:
    rows = [
        row("chat", "DAY", "Villager", "VILLAGER", "second game", game_id="game-b"),
        row("chat", "DAY", "Wolf", "WEREWOLF", "reply", game_id="game-b"),
    ]
    return rows, base_labels("game-b")


def test_successful_reload_replaces_previous_state(tmp_path) -> None:
    first_csv, first_labels = write_export(tmp_path, "first")
    second_rows, second_labels = second_export()
    second_csv, second_labels_path = write_export(tmp_path, "second", second_rows, second_labels)

    record = GameRecord()
    record.read_from_files([first_csv, first_labels])
    assert len(record.get_players()) == 4

    record.read_from_files([second_csv, second_labels_path])
    assert set(record.get_players()) == {"Villager", "Wolf"}


def test_repeated_load_does_not_duplicate_records(tmp_path) -> None:
    csv_path, labels_path = write_export(tmp_path)
    record = GameRecord()

    record.read_from_files([csv_path, labels_path])
    record.read_from_files([csv_path, labels_path])

    assert count_phases(record) == 3
    assert len(record.get_phase_data(0)) == 9


def test_failed_reload_preserves_previous_state(tmp_path) -> None:
    csv_path, labels_path = write_export(tmp_path)
    bad_labels = tmp_path / "bad-labels.json"
    bad_labels.write_text("{", encoding="utf-8")

    record = GameRecord()
    record.read_from_files([csv_path, labels_path])
    before_players = record.get_players()

    with pytest.raises(GameRecordParseError):
        record.read_from_files([csv_path, bad_labels])

    assert record.get_players() == before_players
    assert count_phases(record) == 3


def test_malformed_json_reports_file(tmp_path) -> None:
    csv_path, _labels_path = write_export(tmp_path)
    bad_labels = tmp_path / "game-test-labels.json"
    bad_labels.write_text("{", encoding="utf-8")

    record = GameRecord()
    with pytest.raises(GameRecordParseError, match="game-test-labels.json"):
        record.read_from_files([csv_path, bad_labels])


def test_invalid_csv_field_reports_row(tmp_path) -> None:
    rows = base_rows()
    rows[0]["round"] = "zero"
    csv_path, labels_path = write_export(tmp_path, rows=rows)

    record = GameRecord()
    with pytest.raises(GameRecordValidationError, match="row 2 field round"):
        record.read_from_files([csv_path, labels_path])


def test_invalid_score_reports_json_path(tmp_path) -> None:
    labels = base_labels()
    labels["rounds"][0]["checkpoints"][0]["labels"][0]["targets"][0]["alignment"]["score"] = 8
    csv_path, labels_path = write_export(tmp_path, labels=labels)

    record = GameRecord()
    with pytest.raises(GameRecordValidationError, match=r"alignment\.score"):
        record.read_from_files([csv_path, labels_path])


def test_unknown_structured_action_fails(tmp_path) -> None:
    rows = base_rows()
    rows[2]["content"] = "DANCE"
    csv_path, labels_path = write_export(tmp_path, rows=rows)

    record = GameRecord()
    with pytest.raises(GameRecordParseError, match="Unknown night_action"):
        record.read_from_files([csv_path, labels_path])


def test_mismatched_game_ids_fail(tmp_path) -> None:
    csv_path, labels_path = write_export(tmp_path, labels=base_labels("other-game"))

    record = GameRecord()
    with pytest.raises(GameRecordValidationError, match="Mismatched game_id"):
        record.read_from_files([csv_path, labels_path])
