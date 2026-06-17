"""Core label_once interface stub."""

from typing import Any

from wolf_llm_labeling.contexts import ContextProvider
from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.inner_voice import InnerVoice
from wolf_llm_labeling.models import Label, LLMCallInfo, PlayerName


def label_once(
    llm_provider: Any,
    system_prompt: str,
    context: ContextProvider,
    inner_voice: InnerVoice | None,
    game_data: GameRecord,
    phase_idx: int,
) -> tuple[dict[PlayerName, Label], LLMCallInfo]: ...
