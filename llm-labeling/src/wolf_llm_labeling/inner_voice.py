"""Inner voice interfaces and stubs used as optional LLM tools."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Protocol

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import PlayerName, Score, TrustScores

if TYPE_CHECKING:
    from wolf_llm_labeling.contexts import ContextProvider, Ctx

TRUST_MIN, TRUST_MAX = 1, 7
CONFIDENCE_MIN, CONFIDENCE_MAX = 1, 3


def _make_score(trust: int, confidence: int) -> Score:
    score = Score()
    score.trust = trust
    score.confidence = confidence
    return score


def _make_trust_scores(alignment: Score, strategic: Score, consistency: Score) -> TrustScores:
    scores = TrustScores()
    scores.alignment = alignment
    scores.strategic = strategic
    scores.consistency = consistency
    return scores


def _neutral_trust_scores() -> TrustScores:
    midpoint = (TRUST_MIN + TRUST_MAX) // 2
    return _make_trust_scores(
        _make_score(midpoint, CONFIDENCE_MIN),
        _make_score(midpoint, CONFIDENCE_MIN),
        _make_score(midpoint, CONFIDENCE_MIN),
    )


class InnerVoice(Protocol):
    """An optional advisor the labeling agent can consult for a second-opinion
    trust assessment toward a target player, exposed to the LLM as a tool."""

    def ask(self, player_name: PlayerName, context: Ctx | None, game_records: GameRecord, phase_idx: int) -> TrustScores:
        """Return a trust assessment toward ``player_name`` at ``phase_idx``."""
        ...

    def tool_description(self) -> str:
        """Natural-language description registered with the LLM tool call."""
        ...


class HistoricInnerVoice:
    """Replays the trust scores an observer actually recorded in the game history."""

    observer: PlayerName

    def __init__(self, observer: PlayerName) -> None:
        self.observer = observer

    def ask(self, player_name: PlayerName, context: Ctx | None, game_records: GameRecord, phase_idx: int) -> TrustScores:
        labels_by_observer = game_records.get_labels(phase_idx) or {}
        labels_by_target = labels_by_observer.get(self.observer, {})
        labels = labels_by_target.get(player_name, [])
        if not labels:
            return _neutral_trust_scores()
        # The most recent label carries the current absolute trust assessment.
        return labels[-1].trust_scores

    def tool_description(self) -> str:
        return (
            f"Returns the trust scores that {self.observer} actually recorded "
            "toward the given player at this point in the recorded game."
        )


class RandomInnerVoice:
    """Baseline/control voice: emits random scores ignoring game state."""

    def ask(self, player_name: PlayerName, context: Ctx | None, game_records: GameRecord, phase_idx: int) -> TrustScores:
        def _random_score() -> Score:
            return _make_score(
                random.randint(TRUST_MIN, TRUST_MAX),
                random.randint(CONFIDENCE_MIN, CONFIDENCE_MAX),
            )

        return _make_trust_scores(_random_score(), _random_score(), _random_score())

    def tool_description(self) -> str:
        return (
            "Returns a random trust assessment for the given player. This is a "
            "baseline control and is not grounded in any game evidence."
        )


class AskMyselfInnerVoice:
    def ask(self, player_name: PlayerName, context: Ctx | None, game_records: GameRecord, phase_idx: int) -> TrustScores: ...

    def tool_description(self) -> str: ...


class OtherContextInnerVoice:
    context: ContextProvider

    def __init__(self, context: ContextProvider) -> None: ...

    def ask(self, player_name: PlayerName, context: Ctx | None, game_records: GameRecord, phase_idx: int) -> TrustScores: ...

    def tool_description(self) -> str: ...
