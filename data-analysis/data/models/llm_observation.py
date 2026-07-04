"""Per-target trust scores inside an LLM labeling run output."""

from pydantic import BaseModel


class LLMTrustScore(BaseModel):
    """One trust dimension for one target.

    `trust` is always an integer: 1-7 in likert mode (both likert variants),
    1-100 in numeric mode. The likert strings are only present in likert mode.
    """

    trust: int | None = None
    trust_likert: str | None = None
    confidence: int | None = None  # 1-3
    confidence_likert: str | None = None


class LLMTargetLabel(BaseModel):
    alignment: LLMTrustScore | None = None
    strategic: LLMTrustScore | None = None
    consistency: LLMTrustScore | None = None
    reasoning: str | None = None
