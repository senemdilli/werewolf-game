"""Trust-labeling scaffolding for Werewolf game records."""

from wolf_llm_labeling.models import Label, LLMCallInfo, Score, TrustScores

__all__ = ["Label", "LLMCallInfo", "Score", "TrustScores", "label_once"]


def __getattr__(name: str):
    if name == "label_once":
        from wolf_llm_labeling.labeling import label_once

        return label_once
    raise AttributeError(name)
