"""One labeled phase inside an LLM labeling run output."""

from typing import Any

from pydantic import BaseModel

from data.models.llm_observation import LLMTargetLabel


class InnerVoiceExchange(BaseModel):
    request: dict[str, Any]
    response: str


class LLMPhase(BaseModel):
    phase_idx: int
    context: str | None = None
    inner_voice: list[InnerVoiceExchange] = []
    labels: dict[str, LLMTargetLabel] = {}  # target player name -> label
    reasoning: str | None = None
