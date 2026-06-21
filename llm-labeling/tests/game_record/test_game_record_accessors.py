from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import (
    KillEvent,
    Label,
    Message,
    Score,
    SystemMessage,
    TrustScores,
    Vote,
    VoteReason,
)

from conftest import count_phases, write_export


@pytest.mark.parametrize(
    ("obj", "field"),
    [
        (Score(1, 2), "trust"),
        (TrustScores(Score(1, 2), None, None), "alignment"),
        (Label(TrustScores(None, None, None), "why"), "reasoning"),
        (Message("VillageChat", "Alice", "hi"), "message"),
        (SystemMessage("setup"), "message"),
        (Vote(VoteReason.KILL, "Alice", "Bob"), "voted_for"),
        (KillEvent("Bob"), "affected_player"),
    ],
)
def test_domain_objects_are_immutable(obj: object, field: str) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(obj, field, "changed")


def test_event_kind_cannot_be_overridden() -> None:
    with pytest.raises(TypeError):
        KillEvent("Alice", kind="Other")  # type: ignore[call-arg]
    assert KillEvent("Alice").kind == "KillEvent"


def test_accessors_return_defensive_collections(tmp_path) -> None:
    csv_path, labels_path = write_export(tmp_path)
    record = GameRecord()
    record.read_from_files([csv_path, labels_path])

    players = record.get_players()
    players.clear()
    assert len(record.get_players()) == 4

    data = record.get_phase_data(0)
    data.append(SystemMessage("external mutation"))
    assert all(getattr(item, "message", None) != "external mutation" for item in record.get_phase_data(0))

    labels = record.get_labels(0)
    labels["Villager"]["Wolf"].clear()
    assert record.get_labels(0)["Villager"]["Wolf"]
    assert count_phases(record) == 3
