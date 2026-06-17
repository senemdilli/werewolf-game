"""Context builder interfaces and stubs for LLM-visible game state."""

from typing import Protocol

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import Label, PlayerName
from wolf_llm_labeling.inner_voice import InnerVoice


class Ctx:
    header: str | None
    content: str | None
    subsections: list["Ctx"]

    def to_string(self) -> str: ...


class ContextProvider(Protocol):
    def get_context(self, game_record: GameRecord, phase_idx: int) -> "Ctx | None": ...

    @staticmethod
    def get_topness() -> float: ...


class JoinedContext:
    def __init__(
        self,
        header: str | None,
        content: str | None,
        topness: float,
        *sub_contexts: ContextProvider,
    ) -> None: ...

    def get_context(self, game_record: GameRecord, phase_idx: int) -> "Ctx | None": ...

    @staticmethod
    def get_topness() -> float: ...


class StaticContext:
    player_name: PlayerName

    def __init__(self, player_name: PlayerName) -> None: ...

    def get_context(self, game_record: GameRecord, phase_idx: int) -> "Ctx | None": ...

    @staticmethod
    def get_topness() -> float: ...


class GameNowContext:
    def get_context(self, game_record: GameRecord, phase_idx: int) -> "Ctx | None": ...

    @staticmethod
    def get_topness() -> float: ...


class PhaseGameContext:
    offset: int

    def __init__(self, offset: int = 0) -> None: ...

    def get_context(self, game_record: GameRecord, phase_idx: int) -> "Ctx | None": ...

    @staticmethod
    def get_topness() -> float: ...


class PhaseTrustContext:
    offset: int
    injected_trust: list[dict[PlayerName, Label]] | None

    def __init__(self, offset: int = 0, injected_trust: list[dict[PlayerName, Label]] | None = None) -> None: ...

    def get_context(self, game_record: GameRecord, phase_idx: int) -> "Ctx | None": ...

    @staticmethod
    def get_topness() -> float: ...


class InnerTrustVoiceContext:
    '''
        This context returns the scores of an inner trust voice for all players (except self).
        The inner voice is provided a custom trust context.
    ''' 

    def __init__(self, inner_voice: InnerVoice, inner_voice_context: ContextProvider) -> None: ...

    def get_context(self, game_record: GameRecord, phase_idx: int) -> "Ctx | None": ...

    @staticmethod
    def get_topness() -> float: ...