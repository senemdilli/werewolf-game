"""Align human checkpoints with LLM labeling phase indices.

Human labels are keyed by (round, checkpoint); LLM labeling outputs are keyed
by a flat `phase_idx`. The labeling engine builds its phase list from the
game record's system messages (see `_csv_phase_defs` in
llm-labeling/src/wolf_llm_labeling/game_records.py):

- "Dawn breaks. ..."      -> BEFORE_DISCUSSION
- "Voting begins."        -> BEFORE_VOTING
- vote result message     -> AFTER_VOTING

with one quirk: system messages that occur *after* a round's vote result
(e.g. a mayor election held after the vote) are counted toward the next
round. `phase_idx` is the index into the resulting ordered list, so this
module reproduces that list from the game events JSON to translate between
the two keyings. Any change to the engine's phase construction must be
mirrored here (guarded by tests against real game records).
"""

import re
from dataclasses import dataclass

from data.models.event import GameEvent

CHECKPOINT_ORDER = ("BEFORE_DISCUSSION", "BEFORE_VOTING", "AFTER_VOTING")

# Checkpoint -> engine phase name (PhaseType in the labeling engine)
CHECKPOINT_PHASE_NAME: dict[str, str] = {
    "BEFORE_DISCUSSION": "MORNING",
    "BEFORE_VOTING": "DAY",
    "AFTER_VOTING": "EVENING",
}

_DEATH_MARKERS = ("was found dead", "were found dead", "has been eliminated")


def _is_vote_result(content: str) -> bool:
    return content.startswith("The village voted") or content == "The vote ended in a tie. No one was eliminated."


def _checkpoint_for_system_message(content: str) -> str | None:
    if content.startswith("Dawn breaks."):
        return "BEFORE_DISCUSSION"
    if content == "Voting begins.":
        return "BEFORE_VOTING"
    if _is_vote_result(content):
        return "AFTER_VOTING"
    return None


@dataclass(frozen=True)
class PhaseAlignment:
    """Bidirectional mapping between phase_idx and (round, checkpoint)."""

    phase_defs: list[tuple[int, str]]  # ordered (round, checkpoint)
    dead_at_phase: list[frozenset[str]]  # players dead as of each phase

    def phase_idx(self, round_number: int, checkpoint: str) -> int | None:
        try:
            return self.phase_defs.index((round_number, checkpoint))
        except ValueError:
            return None

    def round_checkpoint(self, phase_idx: int) -> tuple[int, str] | None:
        if 0 <= phase_idx < len(self.phase_defs):
            return self.phase_defs[phase_idx]
        return None

    def phase_name(self, phase_idx: int) -> str | None:
        rc = self.round_checkpoint(phase_idx)
        return CHECKPOINT_PHASE_NAME[rc[1]] if rc else None

    def dead_players(self, phase_idx: int) -> frozenset[str]:
        if 0 <= phase_idx < len(self.dead_at_phase):
            return self.dead_at_phase[phase_idx]
        return self.dead_at_phase[-1] if self.dead_at_phase else frozenset()


def build_phase_alignment(events: list[GameEvent], player_names: set[str] | None = None) -> PhaseAlignment:
    """Reproduce the labeling engine's ordered phase list from game events.

    Also tracks which players are dead at each phase: deaths are announced in
    the "Dawn breaks." message (night kills) and vote result messages
    (eliminations), and take effect at the announcing checkpoint — matching
    the engine's status snapshots.
    """
    system_events = [e for e in events if e.type == "chat" and e.is_system]

    # First vote-result event per raw round, for the effective-round rule.
    vote_result_pos: dict[int, int] = {}
    for pos, event in enumerate(system_events):
        if _is_vote_result(event.content) and event.round not in vote_result_pos:
            vote_result_pos[event.round] = pos

    def effective_round(pos: int, event: GameEvent) -> int:
        result_pos = vote_result_pos.get(event.round)
        if result_pos is not None and pos > result_pos:
            return event.round + 1
        return event.round

    checkpoints_by_round: dict[int, set[str]] = {}
    deaths_by_key: dict[tuple[int, str], set[str]] = {}
    for pos, event in enumerate(system_events):
        checkpoint = _checkpoint_for_system_message(event.content)
        if checkpoint is None:
            continue
        round_number = effective_round(pos, event)
        checkpoints_by_round.setdefault(round_number, set()).add(checkpoint)
        dead = _extract_deaths(event.content, player_names)
        if dead:
            deaths_by_key.setdefault((round_number, checkpoint), set()).update(dead)

    phase_defs = [
        (round_number, checkpoint)
        for round_number in sorted(checkpoints_by_round)
        for checkpoint in CHECKPOINT_ORDER
        if checkpoint in checkpoints_by_round[round_number]
    ]

    dead_at_phase: list[frozenset[str]] = []
    dead: set[str] = set()
    for key in phase_defs:
        dead |= deaths_by_key.get(key, set())
        dead_at_phase.append(frozenset(dead))

    return PhaseAlignment(phase_defs=phase_defs, dead_at_phase=dead_at_phase)


def _extract_deaths(content: str, player_names: set[str] | None) -> set[str]:
    """Pull player names out of death/elimination announcements.

    Messages look like "Dawn breaks. Gray (villager) and Orange (villager)
    were found dead." or "The village voted. Blue (werewolf) has been
    eliminated." — every "Name (role)" pair marks a death.
    """
    if not any(marker in content for marker in _DEATH_MARKERS):
        return set()
    dead = set()
    for match in re.finditer(r"(\w[\w-]*)\s*\([^)]*\)", content):
        name = match.group(1)
        if player_names is None or name in player_names:
            dead.add(name)
    return dead
