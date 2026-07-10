"""Human trust annotations export (`game-<room>-<id>-labels.json`)."""

from pydantic import BaseModel

from data.models.game import GameMeta
from data.models.player import Player


class HumanTrustScore(BaseModel):
    score: int  # 1-7
    confidence: str  # LOW | MEDIUM | HIGH


class HumanTargetLabel(BaseModel):
    player: Player
    reasoning: str | None = None
    alignment: HumanTrustScore | None = None
    information: HumanTrustScore | None = None
    consistency: HumanTrustScore | None = None


class HumanLabelEntry(BaseModel):
    id: str
    created_at: str | None = None
    observer: Player
    targets: list[HumanTargetLabel]


class HumanCheckpoint(BaseModel):
    checkpoint: str  # BEFORE_DISCUSSION | BEFORE_VOTING | AFTER_VOTING
    labels: list[HumanLabelEntry]


class HumanRound(BaseModel):
    round: int
    checkpoints: list[HumanCheckpoint]


class HumanGameLabels(GameMeta):
    rounds: list[HumanRound]
