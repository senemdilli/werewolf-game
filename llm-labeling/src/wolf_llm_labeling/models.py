"""Shared domain model stubs for game records and labeling."""

from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class Score:
    trust: int
    confidence: int


@dataclass(frozen=True, slots=True)
class TrustScores:
    alignment: Score | None
    strategic: Score | None
    consistency: Score | None


@dataclass(frozen=True, slots=True)
class Label:
    trust_scores: TrustScores
    reasoning: str


@dataclass(frozen=True, slots=True)
class Message:
    forum: Forum
    player_name: PlayerName
    message: str


@dataclass(frozen=True, slots=True)
class SystemMessage:
    message: str
    forum: Forum | None = None


@dataclass(frozen=True, slots=True)
class Vote:
    reason: VoteReason
    player_name: PlayerName
    voted_for: PlayerName


@dataclass(frozen=True, slots=True)
class KillEvent:
    affected_player: PlayerName | None
    kind: Literal["KillEvent"] = field(init=False, default="KillEvent")


@dataclass(frozen=True, slots=True)
class ExileEvent:
    affected_player: PlayerName | None
    kind: Literal["ExileEvent"] = field(init=False, default="ExileEvent")


@dataclass(frozen=True, slots=True)
class MayorElected:
    affected_player: PlayerName | None
    kind: Literal["MayorElected"] = field(init=False, default="MayorElected")


@dataclass(frozen=True, slots=True)
class SeerRevealed:
    affected_player: PlayerName
    kind: Literal["SeerRevealed"] = field(init=False, default="SeerRevealed")


@dataclass(frozen=True, slots=True)
class WitchKilled:
    affected_player: PlayerName
    kind: Literal["WitchKilled"] = field(init=False, default="WitchKilled")


@dataclass(frozen=True, slots=True)
class WitchSaved:
    affected_player: PlayerName
    kind: Literal["WitchSaved"] = field(init=False, default="WitchSaved")


Event: TypeAlias = "KillEvent | ExileEvent | MayorElected | SeerRevealed | WitchKilled | WitchSaved"
PhaseItem: TypeAlias = "Message | SystemMessage | Vote | Event"


class LLMCallInfo:
    provider_name: str | None
    context: str | None
    tool_calls: list[dict[str, Any]]
    raw_response: Any | None
    metadata: dict[str, Any]
