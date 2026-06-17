"""Shared domain model stubs for game records and labeling."""

from enum import StrEnum
from typing import Any, Literal, TypeAlias

PlayerName: TypeAlias = str


class Forum(StrEnum):
    VILLAGE_CHAT = "VillageChat"
    WEREWOLF_CHAT = "WerewolfChat"


class VoteReason(StrEnum):
    KILL = "Kill"
    EXILE = "Exile"
    MAYOR = "Mayor"


class PhaseType(StrEnum):
    DAY = "Day"
    EVENING = "Evening"
    MORNING = "Morning"


class Role(StrEnum):
    WEREWOLF = "Werewolf"
    VILLAGER = "Villager"
    SEER = "Seer"
    WITCH = "Witch"


class PlayerStatus(StrEnum):
    MAYOR = "Mayor"
    ALIVE = "Alive"
    DEAD = "Dead"
    EXILED = "Exiled"


class Score:
    trust: int
    confidence: int


class TrustScores:
    alignment: Score
    strategic: Score
    consistency: Score


class Label:
    trust_scores: TrustScores
    reasoning: str


class Message:
    forum: Forum
    player_name: PlayerName
    message: str


class Vote:
    reason: VoteReason
    player_name: PlayerName
    voted_for: PlayerName


class KillEvent:
    affected_player: PlayerName | None
    kind: Literal["KillEvent"]


class ExileEvent:
    affected_player: PlayerName | None
    kind: Literal["ExileEvent"]


class MayorElected:
    affected_player: PlayerName | None
    kind: Literal["MayorElected"]


class SeerRevealed:
    affected_player: PlayerName
    kind: Literal["SeerRevealed"]


class WitchKilled:
    affected_player: PlayerName
    kind: Literal["WitchKilled"]


class WitchSaved:
    affected_player: PlayerName
    kind: Literal["WitchSaved"]


Event: TypeAlias = "KillEvent | ExileEvent | MayorElected | SeerRevealed | WitchKilled | WitchSaved"
PhaseItem: TypeAlias = "Message | Vote | Event"


class LLMCallInfo:
    provider_name: str | None
    context: str | None
    tool_calls: list[dict[str, Any]]
    raw_response: Any | None
    metadata: dict[str, Any]
