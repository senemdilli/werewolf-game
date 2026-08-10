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
    Role,
    SeerRevealed,
    Vote,
    VoteReason,
    WitchKilled,
    WitchSaved,
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


def phase_label(record: GameRecord, phase_idx: int) -> str:
    """Return a human-readable, unambiguous label for one absolute phase."""
    phase_type = record.get_phase_type(phase_idx)
    day_num = (phase_idx // 3) + 1
    phase_name = {
        "Morning": "morning phase",
        "Day": "discussion phase",
        "Evening": "evening phase",
    }.get(phase_type.value, f"{phase_type.value.lower()} phase")
    return f"Day {day_num} {phase_name} (phase index {phase_idx})"


def _render_phase_collection(
    record: GameRecord,
    player: PlayerName,
    anchor_phase_idx: int,
    included_phase_indices: list[int],
    section_note: str,
    chronology: str,
    list_style_mode: str,
) -> str:
    """Render static player data plus selected phases, without a state summary."""
    player_token = active_player_name.set(player)
    chrono_token = chronology_type.set(chronology)
    style_token = list_style.set(list_style_mode)
    try:
        phase_contexts = [
            PhaseGameContext(offset=anchor_phase_idx - phase_idx)
            for phase_idx in sorted(included_phase_indices)
        ]
        game_info = JoinedContext(
            "Game Information",
            None,
            1000.0,
            StaticContext(player),
        )
        phases = JoinedContext(
            "Game Phase History",
            section_note,
            10.0,
            *phase_contexts,
        )
        provider = JoinedContext(None, None, 0.0, game_info, phases)
        ctx = provider.get_context(record, phase_idx=anchor_phase_idx)
        return ctx.to_string(formatter_type="markdown") if ctx is not None else ""
    finally:
        active_player_name.reset(player_token)
        chronology_type.reset(chrono_token)
        list_style.reset(style_token)


def render_hidden_phase_contexts(
    record: GameRecord,
    player: PlayerName,
    hidden_phase_idx: int,
    anchor_phase_idx: int | None = None,
    chronology: str = "numeric",
    list_style_mode: str = "plain",
) -> tuple[str, str]:
    """Render redacted answerer context and complete judge context."""
    phase_count = record.get_phase_count()
    anchor = phase_count - 1 if anchor_phase_idx is None else anchor_phase_idx
    if not 0 <= anchor < phase_count:
        raise ValueError(
            f"anchor phase {anchor} is outside game range 0..{phase_count - 1}"
        )
    if not 0 <= hidden_phase_idx <= anchor:
        raise ValueError(
            f"hidden phase {hidden_phase_idx} is outside anchored range 0..{anchor}"
        )

    all_phases = list(range(anchor + 1))
    visible_phases = [idx for idx in all_phases if idx != hidden_phase_idx]
    label = phase_label(record, hidden_phase_idx)
    answerer_note = (
        f"{label} is intentionally omitted. Reconstruct what happened in that "
        "phase from the rules and the surrounding phases."
    )
    judge_note = (
        f"This is the complete player-visible game through "
        f"{phase_label(record, anchor)}. No phase is omitted."
    )
    answerer_context = _render_phase_collection(
        record,
        player,
        anchor,
        visible_phases,
        answerer_note,
        chronology,
        list_style_mode,
    )
    judge_context = _render_phase_collection(
        record,
        player,
        anchor,
        all_phases,
        judge_note,
        chronology,
        list_style_mode,
    )
    return answerer_context, judge_context


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
                    acceptable_answers=_dedupe([
                        "I did not cast a vote in the mayor election.",
                        "did not vote",
                        "no",
                        f"{player} did not vote in the mayor election.",
                        f"{player} did not vote",
                    ]),
                    grading="auto",
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


def _hidden_phase_questions(
    record: GameRecord,
    player: PlayerName,
    phase_idx: int,
    prefix: str,
) -> list[QuizQuestion]:
    """Build reconstruction questions grounded only in the omitted phase."""
    label = phase_label(record, phase_idx)
    phase_data = record.get_phase_data(phase_idx)
    players = record.get_players()
    questions: list[QuizQuestion] = []
    speculative_questions: list[QuizQuestion] = []

    def add(
        suffix: str,
        question_type: str,
        question: str,
        answers: list[str],
        category: str = "objective",
    ) -> None:
        target = speculative_questions if category == "speculative" else questions
        target.append(
            QuizQuestion(
                id=f"{prefix}-{suffix}",
                type=question_type,
                question=question,
                acceptable_answers=_dedupe(answers),
                grading="judge_only",
                category=category,
            )
        )

    alive_at_start = (
        list(players)
        if phase_idx == 0
        else [
            name
            for name in players
            if record.get_player_status(phase_idx - 1, name).value
            in _ALIVE_STATUSES
        ]
    )
    add(
        "alive-count-start",
        "hidden_alive_count_start",
        f"At the start of the omitted {label}, how many players were alive?",
        [str(len(alive_at_start))],
    )

    alive = [
        name
        for name in players
        if record.get_player_status(phase_idx, name).value in _ALIVE_STATUSES
    ]
    add(
        "alive-count",
        "hidden_alive_count",
        f"At the end of the omitted {label}, how many players were alive?",
        [str(len(alive))],
    )

    deaths = [
        item.affected_player
        for item in phase_data
        if isinstance(item, KillEvent) and item.affected_player is not None
    ]
    add(
        "death-count",
        "hidden_death_count",
        f"How many players died during the omitted {label}?",
        [str(len(deaths))],
    )
    if deaths:
        add(
            "deaths",
            "hidden_who_died",
            f"Who was found dead during the omitted {label}? Name everyone.",
            [", ".join(deaths)],
        )
    else:
        add(
            "deaths-trap",
            "hidden_death_trap",
            f"Was anyone found dead during the omitted {label}? If so, who?",
            ["No one was found dead.", "no one", "nobody"],
        )

    mayors = [
        item.affected_player
        for item in phase_data
        if isinstance(item, MayorElected) and item.affected_player is not None
    ]
    if mayors:
        add(
            "mayor",
            "hidden_mayor_elected",
            f"Who was elected Mayor during the omitted {label}?",
            list(mayors),
        )
    else:
        add(
            "mayor-trap",
            "hidden_mayor_trap",
            f"Was a Mayor elected during the omitted {label}? If so, who?",
            ["No Mayor was elected.", "no", "no one"],
        )

    exiles = [
        item.affected_player
        for item in phase_data
        if isinstance(item, ExileEvent) and item.affected_player is not None
    ]
    if exiles:
        add(
            "exile",
            "hidden_who_exiled",
            f"Who was exiled during the omitted {label}?",
            [", ".join(exiles)],
        )
    else:
        add(
            "exile-trap",
            "hidden_exile_trap",
            f"Was anyone exiled during the omitted {label}? If so, who?",
            ["No one was exiled.", "no one", "nobody"],
        )

    observer_active = player in alive_at_start
    mayor_votes = [
        item
        for item in phase_data
        if isinstance(item, Vote) and item.reason == VoteReason.MAYOR
    ]
    if mayors and observer_active:
        own_mayor_vote = next(
            (vote for vote in mayor_votes if vote.player_name == player), None
        )
        if own_mayor_vote is not None:
            answers = [own_mayor_vote.voted_for]
            qtype = "hidden_own_mayor_vote"
        else:
            answers = [
                "I did not cast a vote in the mayor election.",
                f"{player} did not vote in the mayor election.",
                "did not vote",
            ]
            qtype = "hidden_mayor_vote_trap"
        add(
            "mayor-own-vote",
            qtype,
            f"In the Mayor election during the omitted {label}, whom did you vote "
            "for? If you did not vote, say so.",
            answers,
            "speculative",
        )

    exile_votes = [
        item
        for item in phase_data
        if isinstance(item, Vote) and item.reason == VoteReason.EXILE
    ]
    if observer_active and (exile_votes or exiles):
        own_exile_vote = next(
            (vote for vote in exile_votes if vote.player_name == player), None
        )
        if own_exile_vote is not None:
            answers = [own_exile_vote.voted_for]
            qtype = "hidden_own_exile_vote"
        else:
            answers = [
                "I did not vote to exile anyone.",
                f"{player} did not vote to exile anyone.",
                "did not vote",
            ]
            qtype = "hidden_exile_vote_trap"
        add(
            "exile-own-vote",
            qtype,
            f"In the exile vote during the omitted {label}, whom did you vote to "
            "exile? If you did not vote, say so.",
            answers,
            "speculative",
        )

    observer_role = players.get(player)
    if observer_role == Role.WEREWOLF and observer_active:
        kill_votes = [
            item
            for item in phase_data
            if isinstance(item, Vote) and item.reason == VoteReason.KILL
        ]
        kill_targets = _dedupe(
            [vote.voted_for for vote in kill_votes if vote.voted_for]
        )
        if kill_targets:
            add(
                "wolf-kill-targets",
                "hidden_wolf_kill_targets",
                f"Which player or players received Werewolf kill votes during "
                f"the omitted {label}? Name everyone.",
                [", ".join(kill_targets)],
                "speculative",
            )

            own_kill_vote = next(
                (vote for vote in kill_votes if vote.player_name == player),
                None,
            )
            if own_kill_vote is not None:
                add(
                    "wolf-own-kill-vote",
                    "hidden_own_kill_vote",
                    f"Whom did you vote to kill during the omitted {label}?",
                    [own_kill_vote.voted_for],
                    "speculative",
                )

            if len(kill_votes) > 1:
                unanimous = len(kill_targets) == 1
                add(
                    "wolf-vote-agreement",
                    "hidden_wolf_vote_agreement",
                    f"Did all Werewolves vote for the same kill target during "
                    f"the omitted {label}?",
                    ["Yes, the Werewolf votes were unanimous.", "yes"]
                    if unanimous
                    else ["No, the Werewolf votes were split.", "no"],
                    "speculative",
                )

            additional_deaths = [
                name for name in deaths if name not in set(kill_targets)
            ]
            if additional_deaths:
                add(
                    "additional-deaths",
                    "hidden_additional_deaths",
                    f"Who died during the omitted {label} without receiving a "
                    "Werewolf kill vote? Name everyone.",
                    [", ".join(additional_deaths)],
                    "speculative",
                )
            else:
                add(
                    "additional-deaths-trap",
                    "hidden_additional_deaths_trap",
                    f"Did anyone die during the omitted {label} without receiving "
                    "a Werewolf kill vote?",
                    ["No.", "no one", "nobody"],
                    "speculative",
                )

    if observer_role == Role.SEER and observer_active:
        investigations = [
            item
            for item in phase_data
            if isinstance(item, SeerRevealed) and item.affected_player is not None
        ]
        if investigations:
            targets = [item.affected_player for item in investigations]
            factions = [
                "Werewolves"
                if players.get(target) == Role.WEREWOLF
                else "Village"
                for target in targets
            ]
            add(
                "seer-targets",
                "hidden_seer_targets",
                f"Whom did you investigate as the Seer during the omitted {label}?",
                [", ".join(targets)],
                "speculative",
            )
            add(
                "seer-results",
                "hidden_seer_results",
                f"What faction did your Seer investigation reveal during the "
                f"omitted {label}?",
                [", ".join(factions)],
                "speculative",
            )

    if observer_role == Role.WITCH and observer_active:
        witch_kills = [
            item.affected_player
            for item in phase_data
            if isinstance(item, WitchKilled) and item.affected_player is not None
        ]
        witch_saves = [
            item.affected_player
            for item in phase_data
            if isinstance(item, WitchSaved) and item.affected_player is not None
        ]
        if witch_kills:
            add(
                "witch-poison-targets",
                "hidden_witch_poison_targets",
                f"Whom did you poison as the Witch during the omitted {label}?",
                [", ".join(witch_kills)],
                "speculative",
            )
        if witch_saves:
            add(
                "witch-save-targets",
                "hidden_witch_save_targets",
                f"Whom did you save as the Witch during the omitted {label}?",
                [", ".join(witch_saves)],
                "speculative",
            )
        if not witch_kills and not witch_saves:
            add(
                "witch-action-trap",
                "hidden_witch_action_trap",
                f"Did you use a potion during the omitted {label}?",
                ["No.", "no", "I did not use a potion."],
                "speculative",
            )

    questions.extend(speculative_questions[:2])
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


def generate_hidden_phase_quiz(
    record: GameRecord,
    player: PlayerName,
    hidden_phase_idx: int,
    game_file: str,
    anchor_phase_idx: int | None = None,
    chronology: str = "numeric",
    list_style_mode: str = "plain",
) -> Quiz:
    """Build one leave-one-phase-out reconstruction quiz."""
    anchor = (
        record.get_phase_count() - 1
        if anchor_phase_idx is None
        else anchor_phase_idx
    )
    answerer_context, judge_context = render_hidden_phase_contexts(
        record,
        player,
        hidden_phase_idx,
        anchor_phase_idx=anchor,
        chronology=chronology,
        list_style_mode=list_style_mode,
    )
    prefix = f"{player}-h{hidden_phase_idx}"
    questions = _hidden_phase_questions(
        record,
        player,
        hidden_phase_idx,
        prefix,
    )
    return Quiz(
        game_file=game_file,
        game_id=record.get_game_id(),
        player_name=player,
        phase_idx=hidden_phase_idx,
        context=answerer_context,
        quiz_mode="hidden_phase",
        hidden_phase_idx=hidden_phase_idx,
        anchor_phase_idx=anchor,
        judge_context=judge_context,
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
    hidden_phases: list[int] | None = None,
    anchor_phase_idx: int | None = None,
    chronology: str = "numeric",
    list_style_mode: str = "plain",
) -> QuizSet:
    """Generate standard or leave-one-phase-out quizzes.

    Passing `hidden_phases` selects the hidden-phase mode. A non-empty explicit
    list is used for every selected player; otherwise the legacy `phases`
    behavior remains available for existing callers and artifacts.
    """
    target_players = players if players is not None else list(record.get_players().keys())
    quizzes: list[Quiz] = []
    for player in target_players:
        if hidden_phases is not None:
            anchor = (
                record.get_phase_count() - 1
                if anchor_phase_idx is None
                else anchor_phase_idx
            )
            target_phases = hidden_phases or [
                idx for idx in alive_phases_for(record, player) if idx <= anchor
            ]
        else:
            target_phases = (
                phases if phases is not None else alive_phases_for(record, player)
            )
        for phase_idx in target_phases:
            if hidden_phases is not None:
                quizzes.append(
                    generate_hidden_phase_quiz(
                        record,
                        player,
                        phase_idx,
                        game_file,
                        anchor_phase_idx=anchor_phase_idx,
                        chronology=chronology,
                        list_style_mode=list_style_mode,
                    )
                )
            else:
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
