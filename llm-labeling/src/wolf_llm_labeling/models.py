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
    trust: int | str
    confidence: int | str
    trust_likert: str | None = None
    confidence_likert: str | None = None


@dataclass(frozen=True, slots=True)
class TrustScores:
    alignment: Score | None
    information: Score | None
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
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class SystemMessage:
    message: str
    forum: Forum | None = None
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class Vote:
    reason: VoteReason
    player_name: PlayerName
    voted_for: PlayerName
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class KillEvent:
    affected_player: PlayerName | None
    kind: Literal["KillEvent"] = field(init=False, default="KillEvent")
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class ExileEvent:
    affected_player: PlayerName | None
    kind: Literal["ExileEvent"] = field(init=False, default="ExileEvent")
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class MayorElected:
    affected_player: PlayerName | None
    kind: Literal["MayorElected"] = field(init=False, default="MayorElected")
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class SeerRevealed:
    affected_player: PlayerName
    kind: Literal["SeerRevealed"] = field(init=False, default="SeerRevealed")
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class WitchKilled:
    affected_player: PlayerName
    kind: Literal["WitchKilled"] = field(init=False, default="WitchKilled")
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class WitchSaved:
    affected_player: PlayerName
    kind: Literal["WitchSaved"] = field(init=False, default="WitchSaved")
    timestamp: str | None = None


Event: TypeAlias = "KillEvent | ExileEvent | MayorElected | SeerRevealed | WitchKilled | WitchSaved"
PhaseItem: TypeAlias = "Message | SystemMessage | Vote | Event"

from pydantic import BaseModel, Field, field_validator


class TrustConfidence(BaseModel):
    trust: int = Field(description="Trust score from 1 (lowest trust) to 7 (highest trust)", ge=1, le=7)
    confidence: int = Field(description="Confidence in this score from 1 (low) to 3 (high)", ge=1, le=3)


class TrustScoresSchema(BaseModel):
    alignment: TrustConfidence | None = Field(default=None, description="Assessment on whether the player's goals are compatible with ours")
    information: TrustConfidence | None = Field(default=None, description="Assessment on whether the player gives accurate or useful information")
    consistency: TrustConfidence | None = Field(default=None, description="Assessment on whether the player behaves predictably over time")


class LabelSchema(BaseModel):
    trust_scores: TrustScoresSchema = Field(description="The trust scores dimensions")
    reasoning: str = Field(description="A concise text explanation/rationale for these trust scores")


class SinglePlayerLabel(BaseModel):
    player_name: str = Field(description="Name of the player being labeled")
    label: LabelSchema = Field(description="Label containing trust scores and reasoning for this player")


class ReportLabelsArgs(BaseModel):
    labels: list[SinglePlayerLabel] = Field(description="List of trust labels for other players in the game")

    @field_validator('labels', mode='before')
    @classmethod
    def parse_labels_string(cls, v: Any) -> Any:
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                pass
        return v


from enum import Enum

class TrustLikert(str, Enum):
    STRONGLY_DISAGREE = "STRONGLY_DISAGREE"
    DISAGREE = "DISAGREE"
    SLIGHTLY_DISAGREE = "SLIGHTLY_DISAGREE"
    NEUTRAL = "NEUTRAL"
    SLIGHTLY_AGREE = "SLIGHTLY_AGREE"
    AGREE = "AGREE"
    STRONGLY_AGREE = "STRONGLY_AGREE"

class TrustLikertLegacy(str, Enum):
    VERY_LOW = "VERY_LOW_TRUST"
    LOW = "LOW_TRUST"
    SLIGHTLY_LOW = "SLIGHTLY_LOW_TRUST"
    NEUTRAL = "NEUTRAL_TRUST"
    SLIGHTLY_HIGH = "SLIGHTLY_HIGH_TRUST"
    HIGH = "HIGH_TRUST"
    VERY_HIGH = "VERY_HIGH_TRUST"

class ConfidenceLikert(str, Enum):
    LOW = "LOW_CONFIDENCE"
    MEDIUM = "MEDIUM_CONFIDENCE"
    HIGH = "HIGH_CONFIDENCE"

class TrustConfidenceLikert(BaseModel):
    trust: str = Field(description="Trust assessment on a 7-point Likert scale (STRONGLY_DISAGREE, DISAGREE, SLIGHTLY_DISAGREE, NEUTRAL, SLIGHTLY_AGREE, AGREE, STRONGLY_AGREE)")
    confidence: str = Field(description="Confidence in this assessment on a 3-point Likert scale (LOW_CONFIDENCE, MEDIUM_CONFIDENCE, HIGH_CONFIDENCE)")

class TrustScoresLikertSchema(BaseModel):
    alignment: TrustConfidenceLikert | None = Field(default=None, description="I trust that the player is pursuing goals compatible with my own.")
    information: TrustConfidenceLikert | None = Field(default=None, description="I trust information provided by the player when making game decisions.")
    consistency: TrustConfidenceLikert | None = Field(default=None, description="I trust the player to behave consistently and predictably during the game.")

class LabelLikertSchema(BaseModel):
    trust_scores: TrustScoresLikertSchema = Field(description="The trust scores dimensions")
    reasoning: str = Field(description="A concise text explanation/rationale for these trust scores")

class SinglePlayerLikertLabel(BaseModel):
    player_name: str = Field(description="Name of the player being labeled")
    label: LabelLikertSchema = Field(description="Label containing trust scores and reasoning for this player")

class ReportLabelsLikertArgs(BaseModel):
    labels: list[SinglePlayerLikertLabel] = Field(description="List of trust labels for other players in the game")

    @field_validator('labels', mode='before')
    @classmethod
    def parse_labels_string(cls, v: Any) -> Any:
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                pass
        return v


# Legacy Likert models
class TrustConfidenceLikertLegacy(BaseModel):
    trust: str = Field(description="Trust assessment on a 7-point Likert scale (VERY_LOW_TRUST, LOW_TRUST, SLIGHTLY_LOW_TRUST, NEUTRAL_TRUST, SLIGHTLY_HIGH_TRUST, HIGH_TRUST, VERY_HIGH_TRUST)")
    confidence: str = Field(description="Confidence in this assessment on a 3-point Likert scale (LOW_CONFIDENCE, MEDIUM_CONFIDENCE, HIGH_CONFIDENCE)")

class TrustScoresLikertLegacySchema(BaseModel):
    alignment: TrustConfidenceLikertLegacy | None = Field(default=None, description="Assessment on whether the player's goals are compatible with ours")
    information: TrustConfidenceLikertLegacy | None = Field(default=None, description="Assessment on whether the player gives accurate or useful information")
    consistency: TrustConfidenceLikertLegacy | None = Field(default=None, description="Assessment on whether the player behaves predictably over time")

class LabelLikertLegacySchema(BaseModel):
    trust_scores: TrustScoresLikertLegacySchema = Field(description="The trust scores dimensions")
    reasoning: str = Field(description="A concise text explanation/rationale for these trust scores")

class SinglePlayerLikertLegacyLabel(BaseModel):
    player_name: str = Field(description="Name of the player being labeled")
    label: LabelLikertLegacySchema = Field(description="Label containing trust scores and reasoning for this player")

class ReportLabelsLikertLegacyArgs(BaseModel):
    labels: list[SinglePlayerLikertLegacyLabel] = Field(description="List of trust labels for other players in the game")

    @field_validator('labels', mode='before')
    @classmethod
    def parse_labels_string(cls, v: Any) -> Any:
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                pass
        return v



@dataclass
class LLMCallInfo:
    provider_name: str | None = None
    context: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw_response: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


import contextvars
active_player_name = contextvars.ContextVar("active_player_name", default=None)
active_llm_provider = contextvars.ContextVar("active_llm_provider", default=None)
active_system_prompt = contextvars.ContextVar("active_system_prompt", default=None)
chronology_type = contextvars.ContextVar("chronology_type", default="numeric")
parallel_mode = contextvars.ContextVar("parallel_mode", default=False)


from typing import Literal

FormatterType = Literal["markdown", "json"]


@dataclass
class LLMModelProviders:
    primary: Any
    inner_voice: Any



