from __future__ import annotations

from pathlib import Path

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.quiz.generate import (
    _parse_top_level_steps,
    generate_quiz,
    generate_quiz_set,
    render_context,
)


def _load_record(tmp_path: Path) -> GameRecord:
    from game_record.conftest import write_export

    csv_path, labels_path = write_export(tmp_path)
    record = GameRecord()
    record.read_from_files([csv_path, labels_path])
    return record


def test_render_context_has_chronology(tmp_path: Path) -> None:
    record = _load_record(tmp_path)
    context = render_context(record, "Villager", 0)
    assert "Phase chronology" in context
    assert "Static Data" in context


def test_parse_top_level_steps() -> None:
    context = (
        "# Current Phase\n\n"
        "- Day: 1\n\n"
        "## Phase chronology\n"
        "1. [Moderator] Night 1 begins.\n"
        "2. Conversation among players with role Werewolf:\n"
        "   2.1 [Blue] who do you think we should kill?\n"
        "   2.2 [Gold] no idea\n"
        "3. Purple was found dead.\n"
    )
    steps = _parse_top_level_steps(context)
    assert steps == [
        "1. [Moderator] Night 1 begins.",
        "2. Conversation among players with role Werewolf:",
        "3. Purple was found dead.",
    ]


def test_generate_quiz_structured_questions(tmp_path: Path) -> None:
    record = _load_record(tmp_path)
    quiz = generate_quiz(record, "Villager", 0, "game-test")

    by_type: dict[str, list] = {}
    for q in quiz.questions:
        by_type.setdefault(q.type, []).append(q)

    # Self role is always answerable.
    assert by_type["self_role"][0].acceptable_answers == ["Villager"]

    # Seer was killed during the night in the fixture.
    assert any("Seer" in ans for ans in by_type["who_died"][0].acceptable_answers)

    # Villager was elected mayor in the fixture.
    assert by_type["mayor_elected"][0].acceptable_answers == ["Villager"]

    # Alive at end of phase 0: Wolf, Witch, Villager(=Mayor) -> 3 (Seer dead).
    assert by_type["alive_count"][0].acceptable_answers == ["3"]

    # At least one sequence question was derived from the chronology.
    assert any(q.type == "sequence_next" for q in quiz.questions)
    assert any(q.type == "sequence_last" for q in quiz.questions)


def test_generate_quiz_set_serialization_roundtrip(tmp_path: Path) -> None:
    from wolf_llm_labeling.quiz.models import QuizSet

    record = _load_record(tmp_path)
    quiz_set = generate_quiz_set(record, game_file="game-test", players=["Villager"])

    assert len(quiz_set.quizzes) >= 1
    restored = QuizSet.from_dict(quiz_set.to_dict())
    assert restored.quizzes[0].player_name == "Villager"
    assert restored.quizzes[0].questions[0].id == quiz_set.quizzes[0].questions[0].id


def test_generate_quiz_werewolf_sees_kill_vote(tmp_path: Path) -> None:
    record = _load_record(tmp_path)
    quiz = generate_quiz(record, "Wolf", 0, "game-test")
    # The werewolf's context should include the private werewolf night content.
    assert "Werewolf" in quiz.context


def test_list_style_plain_is_default(tmp_path: Path) -> None:
    record = _load_record(tmp_path)
    context = render_context(record, "Villager", 0)
    # Static Data / Current Game State lines are plain (no leading bullet).
    assert "Your name is: Villager" in context
    assert "- Your name is: Villager" not in context


def test_list_style_dash_bullets_top_level_lines(tmp_path: Path) -> None:
    record = _load_record(tmp_path)
    context = render_context(record, "Villager", 0, list_style_mode="dash")
    # Top-level Static Data / Current Game State lines are now bulleted.
    assert "- Your name is: Villager" in context
    assert "- Current Day: 1" in context
    assert "- Current Phase:" in context
    # Already-indented nested lines keep their existing indentation (no double dash).
    assert "- - " not in context


def test_list_style_dash_does_not_leak(tmp_path: Path) -> None:
    record = _load_record(tmp_path)
    render_context(record, "Villager", 0, list_style_mode="dash")
    # A subsequent default render must be unaffected by the contextvar.
    context = render_context(record, "Villager", 0)
    assert "- Your name is: Villager" not in context
