"""Inner voice interfaces and stubs used as optional LLM tools."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Protocol

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import PlayerName, Score, TrustScores
from wolf_llm_labeling.prompts import PromptSet

if TYPE_CHECKING:
    from wolf_llm_labeling.contexts import ContextProvider, Ctx

TRUST_MIN, TRUST_MAX = 1, 7
CONFIDENCE_MIN, CONFIDENCE_MAX = 1, 3


def _make_score(trust: int, confidence: int) -> Score:
    return Score(trust=trust, confidence=confidence)


def _make_trust_scores(alignment: Score, information: Score, consistency: Score) -> TrustScores:
    return TrustScores(alignment=alignment, information=information, consistency=consistency)


def _neutral_trust_scores() -> TrustScores:
    midpoint = (TRUST_MIN + TRUST_MAX) // 2
    medium_confidence = (CONFIDENCE_MIN + CONFIDENCE_MAX) // 2
    return _make_trust_scores(
        _make_score(midpoint, medium_confidence),
        _make_score(midpoint, medium_confidence),
        _make_score(midpoint, medium_confidence),
    )


class InnerVoice(Protocol):
    def ask(self, player_name: PlayerName, context: Ctx | None, game_records: GameRecord, prompt_set: PromptSet, phase_idx: int) -> TrustScores:
        """Return a trust assessment toward ``player_name`` at ``phase_idx``."""
        ...

    def tool_description(self, prompt_set: PromptSet) -> str:
        """Natural-language description registered with the LLM tool call."""
        ...

    def feed_context(self, game_records: GameRecord, phase_idx: int) -> None:
        """Feed the game context to the inner trust voice (e.g. for updating a knowledge graph)."""
        ...


class HumanHistoricInnerVoice:
    observer: PlayerName

    def __init__(self, observer: PlayerName) -> None:
        self.observer = observer

    def ask(
        self,
        player_name: PlayerName,
        context: Ctx | None,
        game_records: GameRecord,
        prompt_set_or_phase_idx: Any = None,
        phase_idx: int | None = None,
    ) -> TrustScores:
        if phase_idx is None:
            target_phase_idx = prompt_set_or_phase_idx
            prompt_set = PromptSet()
        else:
            target_phase_idx = phase_idx
            prompt_set = prompt_set_or_phase_idx if isinstance(prompt_set_or_phase_idx, PromptSet) else PromptSet()

        from wolf_llm_labeling.contexts import _get_effective_labels
        effective_labels = _get_effective_labels(game_records, self.observer, target_phase_idx)
        labels = effective_labels.get(player_name, ())
        if not labels:
            return _neutral_trust_scores()
        return labels[-1].trust_scores

    def tool_description(self, prompt_set: PromptSet | None = None) -> str:
        if prompt_set is None:
            prompt_set = PromptSet()
        return prompt_set.get_prompt(
            "inner_voice__human_historic_voice",
            {"observer": self.observer},
            f"Returns the trust scores that {self.observer} actually recorded "
            "toward the given player at this point in the recorded game."
        )

    def feed_context(self, game_records: GameRecord, phase_idx: int) -> None:
        pass


class RandomInnerVoice:
    def ask(
        self,
        player_name: PlayerName,
        context: Ctx | None,
        game_records: GameRecord,
        prompt_set_or_phase_idx: Any = None,
        phase_idx: int | None = None,
    ) -> TrustScores:
        if phase_idx is None:
            target_phase_idx = prompt_set_or_phase_idx
            prompt_set = PromptSet()
        else:
            target_phase_idx = phase_idx
            prompt_set = prompt_set_or_phase_idx if isinstance(prompt_set_or_phase_idx, PromptSet) else PromptSet()

        def _random_score() -> Score:
            return _make_score(
                random.randint(TRUST_MIN, TRUST_MAX),
                random.randint(CONFIDENCE_MIN, CONFIDENCE_MAX),
            )

        return _make_trust_scores(_random_score(), _random_score(), _random_score())

    def tool_description(self, prompt_set: PromptSet | None = None) -> str:
        if prompt_set is None:
            prompt_set = PromptSet()
        return prompt_set.get_prompt(
            "inner_voice__random_voice",
            {},
            "Returns a random trust assessment for the given player. This is a "
            "baseline control and is not grounded in any game evidence."
        )

    def feed_context(self, game_records: GameRecord, phase_idx: int) -> None:
        pass


class ConstantInnerVoice:
    def __init__(self, trust_score: Score | TrustScores) -> None:
        self.trust_scores = (
            trust_score
            if isinstance(trust_score, TrustScores)
            else _make_trust_scores(trust_score, trust_score, trust_score)
        )

    def ask(
        self,
        player_name: PlayerName,
        context: Ctx | None,
        game_records: GameRecord,
        prompt_set_or_phase_idx: Any = None,
        phase_idx: int | None = None,
    ) -> TrustScores:
        return self.trust_scores

    def tool_description(self, prompt_set: PromptSet | None = None) -> str:
        if prompt_set is None:
            prompt_set = PromptSet()
        return prompt_set.get_prompt(
            "inner_voice__constant_voice",
            {},
            "Always returns the same configured trust assessment for every player."
        )

    def feed_context(self, game_records: GameRecord, phase_idx: int) -> None:
        pass


def _trust_scores_from_schema(result: object) -> TrustScores:
    def to_score(s: object) -> Score | None:
        if s is None:
            return None
        return Score(trust=getattr(s, "trust"), confidence=getattr(s, "confidence"))

    return TrustScores(
        alignment=to_score(getattr(result, "alignment", None)),
        information=to_score(getattr(result, "information", None)),
        consistency=to_score(getattr(result, "consistency", None)),
    )


def _ask_llm_for_trust(player_name: PlayerName, context_str: str) -> TrustScores:
    from wolf_llm_labeling.models import TrustScoresSchema, active_llm_provider, active_system_prompt

    llm_provider = active_llm_provider.get()
    system_prompt = active_system_prompt.get()
    if llm_provider is None:
        return _neutral_trust_scores()

    user_content = (
        f"Here is the game context:\n{context_str}\n\n"
        f"Provide your gut-feeling trust assessment for player '{player_name}' "
        "without any rationale. Only provide trust scores."
    )
    messages = []
    if system_prompt:
        messages.append(("system", system_prompt))
    messages.append(("human", user_content))

    try:
        structured_llm = llm_provider.with_structured_output(TrustScoresSchema)
        result = structured_llm.invoke(messages)
        if result is None:
            return _neutral_trust_scores()
        return _trust_scores_from_schema(result)
    except Exception:
        return _neutral_trust_scores()


class LLMInnerVoice:
    def ask(
        self,
        player_name: PlayerName,
        context: Ctx | None,
        game_records: GameRecord,
        prompt_set_or_phase_idx: Any = None,
        phase_idx: int | None = None,
    ) -> TrustScores:
        if phase_idx is None:
            target_phase_idx = prompt_set_or_phase_idx
            prompt_set = PromptSet()
        else:
            target_phase_idx = phase_idx
            prompt_set = prompt_set_or_phase_idx if isinstance(prompt_set_or_phase_idx, PromptSet) else PromptSet()

        context_str = context.to_string() if context is not None else "No context available."
        return _ask_llm_for_trust(player_name, context_str)

    def tool_description(self, prompt_set: PromptSet | None = None) -> str:
        if prompt_set is None:
            prompt_set = PromptSet()
        return prompt_set.get_prompt(
            "inner_voice__llm_voice",
            {},
            "Asks an LLM with its current context for a gut-feeling trust assessment "
            "toward the given player. Returns trust scores without rationale."
        )

    def feed_context(self, game_records: GameRecord, phase_idx: int) -> None:
        pass
