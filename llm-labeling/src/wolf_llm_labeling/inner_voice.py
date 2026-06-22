"""Inner voice interfaces and stubs used as optional LLM tools."""

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from wolf_llm_labeling.contexts import ContextProvider, Ctx
from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import PlayerName, TrustScores


class InnerVoice(Protocol):
    def ask(self, player_name: PlayerName, context: "Ctx | None", game_records: GameRecord, phase_idx: int) -> TrustScores: ...

    def tool_description(self) -> str: ...


class HistoricInnerVoice:
    def ask(self, player_name: PlayerName, context: "Ctx | None", game_records: GameRecord, phase_idx: int) -> TrustScores: ...

    def tool_description(self) -> str: ...


class RandomInnerVoice:
    def ask(self, player_name: PlayerName, context: "Ctx | None", game_records: GameRecord, phase_idx: int) -> TrustScores: ...

    def tool_description(self) -> str: ...



class AskMyselfInnerVoice:
    def ask(self, player_name: PlayerName, context: "Ctx | None", game_records: GameRecord, phase_idx: int) -> TrustScores: ...

    def tool_description(self) -> str: ...


class OtherContextInnerVoice:
    context: "ContextProvider"

    def __init__(self, context: "ContextProvider") -> None: ...

    def ask(self, player_name: PlayerName, context: "Ctx | None", game_records: GameRecord, phase_idx: int) -> TrustScores: ...

    def tool_description(self) -> str: ...

