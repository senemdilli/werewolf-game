from wolf_llm_labeling.models import Label, LLMCallInfo, Score, TrustScores, LLMModelProviders
from wolf_llm_labeling.prompts import PromptSet

__all__ = ["Label", "LLMCallInfo", "Score", "TrustScores", "LLMModelProviders", "PromptSet", "label_once"]


def __getattr__(name: str):
    if name == "label_once":
        from wolf_llm_labeling.labeling import label_once

        return label_once
    raise AttributeError(name)

