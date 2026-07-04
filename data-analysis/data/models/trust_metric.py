"""Canonical trust dimensions and measurement scales.

The two sources name their dimensions differently:
- human export:  alignment / information / consistency
- LLM labeling:  alignment / strategic  / consistency

`strategic` is treated as the same dimension as `information` (canonical name:
INFORMATION).
"""

from enum import Enum


class TrustType(str, Enum):
    ALIGNMENT = "alignment"
    INFORMATION = "information"
    CONSISTENCY = "consistency"


# Source-specific key -> canonical trust type
CANONICAL_TRUST_TYPE: dict[str, TrustType] = {
    "alignment": TrustType.ALIGNMENT,
    "information": TrustType.INFORMATION,
    "strategic": TrustType.INFORMATION,
    "consistency": TrustType.CONSISTENCY,
}

HUMAN_TRUST_KEYS = ("alignment", "information", "consistency")
LLM_TRUST_KEYS = ("alignment", "strategic", "consistency")


class TrustScale(str, Enum):
    """Scale the raw trust score was recorded on."""

    SEVEN_POINT = "7pt"         # human labels and LLM likert mode (1-7)
    NUMERIC_100 = "numeric100"  # LLM numeric mode (1-100)


class ConfidenceScale(str, Enum):
    """Scale the raw confidence was recorded on (both sources are 3-level)."""

    THREE_LEVEL = "3level"  # 1=LOW, 2=MEDIUM, 3=HIGH
