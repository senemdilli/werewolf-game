"""Scale normalization for trust and confidence scores.

Everything is normalized to [0, 1] so scores from different scales are
comparable in aggregations. Raw values and their scale are always kept
alongside — distribution-shape analyses (e.g. extremeness) must run on the
original ordinal values, not on normalized means.

Observed scales:
- human trust:        integer 1-7
- LLM likert trust:   integer 1-7 (the engine stores the numeric value next to
                      the likert string, for both likert variants)
- LLM numeric trust:  integer 1-100
- human confidence:   LOW | MEDIUM | HIGH
- LLM confidence:     integer 1-3 (LOW/MEDIUM/HIGH likert strings)
"""

from data.models.trust_metric import TrustScale

# Likert string -> 1-7 value, mirroring the labeling engine's own mapping
# (llm-labeling/src/wolf_llm_labeling/labeling.py).
TRUST_LIKERT_VALUES: dict[str, int] = {
    # legacy trust scale
    "VERY_LOW_TRUST": 1,
    "LOW_TRUST": 2,
    "SLIGHTLY_LOW_TRUST": 3,
    "NEUTRAL_TRUST": 4,
    "SLIGHTLY_HIGH_TRUST": 5,
    "HIGH_TRUST": 6,
    "VERY_HIGH_TRUST": 7,
    # agree-disagree scale
    "STRONGLY_DISAGREE": 1,
    "DISAGREE": 2,
    "SLIGHTLY_DISAGREE": 3,
    "NEUTRAL": 4,
    "SLIGHTLY_AGREE": 5,
    "AGREE": 6,
    "STRONGLY_AGREE": 7,
}

CONFIDENCE_VALUES: dict[str, int] = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "LOW_CONFIDENCE": 1,
    "MEDIUM_CONFIDENCE": 2,
    "HIGH_CONFIDENCE": 3,
}

_SCALE_BOUNDS: dict[TrustScale, tuple[int, int]] = {
    TrustScale.SEVEN_POINT: (1, 7),
    TrustScale.NUMERIC_100: (1, 100),
}


def normalize_trust(value: int | None, scale: TrustScale) -> float | None:
    """Map a raw trust score to [0, 1]. Out-of-range values are clamped."""
    if value is None:
        return None
    low, high = _SCALE_BOUNDS[scale]
    clamped = min(max(value, low), high)
    return (clamped - low) / (high - low)


def normalize_confidence(value: int | str | None) -> float | None:
    """Map a raw confidence (1-3 int or LOW/MEDIUM/HIGH string) to [0, 1]."""
    if value is None:
        return None
    if isinstance(value, str):
        mapped = CONFIDENCE_VALUES.get(value.strip().upper())
        if mapped is None:
            return None
        value = mapped
    clamped = min(max(value, 1), 3)
    return (clamped - 1) / 2


def confidence_ordinal(value: int | str | None) -> int | None:
    """Raw confidence as its 1-3 ordinal value."""
    if value is None:
        return None
    if isinstance(value, str):
        return CONFIDENCE_VALUES.get(value.strip().upper())
    return min(max(value, 1), 3)


def infer_trust_scale(trust_scale_mode: str | None, values: list[int]) -> TrustScale:
    """Determine the trust scale of an LLM run.

    Old result files lack `trust_scale_mode`; for those, any score above 7
    means the 1-100 numeric scale was in use.
    """
    if trust_scale_mode == "numeric":
        return TrustScale.NUMERIC_100
    if trust_scale_mode == "likert":
        return TrustScale.SEVEN_POINT
    if any(v > 7 for v in values):
        return TrustScale.NUMERIC_100
    return TrustScale.SEVEN_POINT
