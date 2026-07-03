"""Stage A: turn a game record into a comprehension quiz.

Questions are generated two ways, both grounded in exactly what the candidate
model will be shown:

1. From the *rendered* phase chronology (sequence questions like "what comes
   after step N?"). These are parsed straight out of the same context string,
   so the ground truth always matches the wording the model sees.
2. From the *structured* GameRecord events (votes, deaths, roles, alive counts).
   These respect per-player visibility because we only ask about the observing
   player's own actions and publicly visible facts.

No LLM is involved here; generation is fully deterministic.
"""

from __future__ import annotations

import re

from wolf_llm_labeling.contexts import (
    GameNowContext,
    JoinedContext,
    PhaseGameContext,
    StaticContext,
)
from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import (
    ExileEvent,
    KillEvent,
    MayorElected,
    PlayerName,
    Vote,
    VoteReason,
    active_player_name,
    chronology_type,
    list_style,
)
from wolf_llm_labeling.quiz.models import Quiz, QuizQuestion, QuizSet

_ALIVE_STATUSES = {"Alive", "Mayor"}
_TOP_STEP_RE = re.compile(r"^(\d+)\.\s+(.*\S)\s*$")


def render_context(
    record: GameRecord,
    player: PlayerName,
    phase_idx: int,
    chronology: str = "numeric",
    list_style_mode: str = "plain",
) -> str:
    """Render the markdown context a given player sees at a given phase.

    Mirrors the labeler's base context (Static + GameNow + current phase) so the
    quiz asks about the very same text the labeling engine feeds to the model.
    """
    player_token = active_player_name.set(player)
    chrono_token = chronology_type.set(chronology)
    style_token = list_style.set(list_style_mode)
    try:
        provider = JoinedContext(
            "Game Information",
            None,
            1000.0,
            StaticContext(player),
            GameNowContext(player),
            PhaseGameContext(offset=0),
        )
        ctx = provider.get_context(record, phase_idx=phase_idx)
        return ctx.to_string(formatter_type="markdown") if ctx is not None else ""
    finally:
        active_player_name.reset(player_token)
        chronology_type.reset(chrono_token)
        list_style.reset(style_token)


def _parse_top_level_steps(context_md: str) -> list[str]:
    """Extract the ordered top-level chronology steps ("N. ...") from context.

    Sub-steps (rendered indented as "   N.M ...") are skipped; only the
    numbered top-level lines are returned, each as "N. text".
    """
    lines = context_md.splitlines()
    in_chronology = False
    steps: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower().endswith("phase chronology") and stripped.startswith("#"):
            in_chronology = True
            continue
        if not in_chronology:
            continue
        # A new markdown heading ends the chronology section.
        if line.startswith("#"):
            break
        # Only unindented "N. ..." lines are top-level steps.
        if line[:1].isspace():
            continue
        match = _TOP_STEP_RE.match(line)
        if match:
            steps.append(f"{match.group(1)}. {match.group(2)}")
    return steps


def _strip_step_number(step: str) -> str:
    match = _TOP_STEP_RE.match(step)
    return match.group(2) if match else step


def _sequence_questions(context_md: str, prefix: str) -> list[QuizQuestion]:
    steps = _parse_top_level_steps(context_md)
    questions: list[QuizQuestion] = []
    if not steps:
        return questions

    # "What comes after step i?" for each adjacent pair.
    for i in range(len(steps) - 1):
        nxt = steps[i + 1]
        questions.append(
            QuizQuestion(
                id=f"{prefix}-seq-{i}",
                type="sequence_next",
                question=(
                    "In the phase chronology, what is the step immediately after "
                    f'this one?\n\n"{steps[i]}"'
                ),
                acceptable_answers=[nxt, _strip_step_number(nxt)],
                grading="auto",
            )
        )

    # First step.
    questions.append(
        QuizQuestion(
            id=f"{prefix}-seq-first",
            type="sequence_first",
            question="What is the first step in the phase chronology?",
            acceptable_answers=[steps[0], _strip_step_number(steps[0])],
            grading="auto",
        )
    )

    # Trap: nothing comes after the last step.
    questions.append(
        QuizQuestion(
            id=f"{prefix}-seq-last",
            type="sequence_last",
            question=(
                "In the phase chronology, what step comes immediately after "
                f'this one?\n\n"{steps[-1]}"'
            ),
            acceptable_answers=[
                "Nothing, this is the last step in the phase chronology.",
                "There is no step after it.",
                "nothing",
            ],
            grading="judge_only",
        )
    )
    return questions


def _structured_questions(
    record: GameRecord,
    player: PlayerName,
    phase_idx: int,
    prefix: str,
) -> list[QuizQuestion]:
    players = record.get_players()
    role = players.get(player)
    phase_data = record.get_phase_data(phase_idx)
    questions: list[QuizQuestion] = []

    # Self role (always answerable from the Static Data block).
    if role is not None:
        questions.append(
            QuizQuestion(
                id=f"{prefix}-self-role",
                type="self_role",
                question="According to the context, what is your own role in this game?",
                acceptable_answers=[role.value],
                grading="auto",
            )
        )

    # Alive count at end of phase.
    alive = [
        p
        for p in players
        if record.get_player_status(phase_idx, p).value in _ALIVE_STATUSES
    ]
    questions.append(
        QuizQuestion(
            id=f"{prefix}-alive-count",
            type="alive_count",
            question="How many players are alive at the end of this phase?",
            acceptable_answers=[str(len(alive))],
            grading="auto",
        )
    )

    # Who was found dead this phase (public).
    deaths = [
        item.affected_player
        for item in phase_data
        if isinstance(item, KillEvent) and item.affected_player is not None
    ]
    if deaths:
        questions.append(
            QuizQuestion(
                id=f"{prefix}-deaths",
                type="who_died",
                question="Who was found dead in this phase?",
                acceptable_answers=[", ".join(deaths), *deaths],
                grading="auto",
            )
        )

    # Who was elected mayor this phase (public), if applicable.
    mayor_elected = [
        item.affected_player
        for item in phase_data
        if isinstance(item, MayorElected) and item.affected_player is not None
    ]
    if mayor_elected:
        questions.append(
            QuizQuestion(
                id=f"{prefix}-mayor-elected",
                type="mayor_elected",
                question="Who was elected Mayor in this phase?",
                acceptable_answers=list(mayor_elected),
                grading="auto",
            )
        )

    # The observer can only be asked about their own actions if they were alive.
    observer_alive = record.get_player_status(phase_idx, player).value in _ALIVE_STATUSES

    # Mayor-vote question (the observer's own mayor vote is visible; others hidden).
    mayor_votes = [
        item
        for item in phase_data
        if isinstance(item, Vote) and item.reason == VoteReason.MAYOR
    ]
    if mayor_elected and mayor_votes and observer_alive:
        own_mayor_vote = next(
            (v for v in mayor_votes if v.player_name == player), None
        )
        if own_mayor_vote is not None:
            questions.append(
                QuizQuestion(
                    id=f"{prefix}-mayor-own-vote",
                    type="own_mayor_vote",
                    question="In the mayor election this phase, whom did you vote for?",
                    acceptable_answers=[own_mayor_vote.voted_for],
                    grading="auto",
                )
            )
        else:
            # Trap: individual mayor votes are secret; the observer did not vote.
            questions.append(
                QuizQuestion(
                    id=f"{prefix}-mayor-trap",
                    type="mayor_vote_trap",
                    question=(
                        "Did you cast a vote in the mayor election this phase? "
                        "If so, for whom?"
                    ),
                    acceptable_answers=[
                        "I did not cast a vote in the mayor election.",
                        "did not vote",
                        "no",
                    ],
                    grading="judge_only",
                )
            )

    # Exile-vote question (all exile votes are public).
    exile_votes = [
        item
        for item in phase_data
        if isinstance(item, Vote) and item.reason == VoteReason.EXILE
    ]
    if exile_votes and observer_alive:
        own_exile_vote = next(
            (v for v in exile_votes if v.player_name == player), None
        )
        if own_exile_vote is not None:
            answers = [own_exile_vote.voted_for]
            grading = "auto"
            question = "In the exile vote this phase, whom did you vote to exile?"
        else:
            answers = ["I did not vote to exile anyone.", "did not vote", "no one"]
            grading = "judge_only"
            question = (
                "In the exile vote this phase, whom did you vote to exile? "
                "If you did not vote, say so."
            )
        questions.append(
            QuizQuestion(
                id=f"{prefix}-exile-own-vote",
                type="own_exile_vote",
                question=question,
                acceptable_answers=answers,
                grading=grading,
            )
        )

    return questions


def _dedupe(items: list[str]) -> list[str]:
    """Drop duplicate answers while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def generate_quiz(
    record: GameRecord,
    player: PlayerName,
    phase_idx: int,
    game_file: str,
    chronology: str = "numeric",
    list_style_mode: str = "plain",
) -> Quiz:
    """Build a self-contained quiz for one player at one phase."""
    context_md = render_context(
        record, player, phase_idx, chronology=chronology, list_style_mode=list_style_mode
    )
    prefix = f"{player}-p{phase_idx}"
    questions = _sequence_questions(context_md, prefix)
    questions.extend(_structured_questions(record, player, phase_idx, prefix))
    for question in questions:
        question.acceptable_answers = _dedupe(question.acceptable_answers)
    return Quiz(
        game_file=game_file,
        game_id=record.get_game_id(),
        player_name=player,
        phase_idx=phase_idx,
        context=context_md,
        questions=questions,
    )


def alive_phases_for(record: GameRecord, player: PlayerName) -> list[int]:
    """Phase indices where the player is alive (labelable / answerable)."""
    return [
        idx
        for idx in range(record.get_phase_count())
        if record.get_player_status(idx, player).value in _ALIVE_STATUSES
    ]


def generate_quiz_set(
    record: GameRecord,
    game_file: str,
    players: list[PlayerName] | None = None,
    phases: list[int] | None = None,
    chronology: str = "numeric",
    list_style_mode: str = "plain",
) -> QuizSet:
    """Generate quizzes for the given players/phases (defaults: all, alive-only)."""
    target_players = players if players is not None else list(record.get_players().keys())
    quizzes: list[Quiz] = []
    for player in target_players:
        target_phases = phases if phases is not None else alive_phases_for(record, player)
        for phase_idx in target_phases:
            quizzes.append(
                generate_quiz(
                    record,
                    player,
                    phase_idx,
                    game_file,
                    chronology=chronology,
                    list_style_mode=list_style_mode,
                )
            )
    return QuizSet(
        source_game_file=game_file,
        game_id=record.get_game_id(),
        quizzes=quizzes,
    )
