"""This class is used to describe LLM configurations"""

from pydantic import BaseModel

class LLMConfig(BaseModel):
    """Configuration schema for an LLM."""

    model_name: str
    temperature: float = 0.0
    base_url: str
    api_key: str